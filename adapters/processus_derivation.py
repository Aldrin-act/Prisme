"""Éclatement du processus d'un atelier (`api.etat.EtapeProcessus`) en tâches DSL concrètes à
l'arrivée d'une commande — couche d'ingestion, jamais un axe T-R-C-O (même statut que
`adapters/commande_derivation.py::Commande`).

Un atelier a **un seul** processus, décrit une fois : une suite d'étapes (compétences requises,
ordre via prédécesseurs, durée par pièce). Chaque commande reçoit sa propre copie de ces étapes,
en tâches fraîches préfixées par l'identifiant de la commande, avec une durée multipliée par la
quantité commandée. Les compatibilités se dérivent ensuite des compétences
(`competence_derivation.py`) — la même brique que les imports CSV/JSON, jamais dupliquée ici.
L'échéance, elle, reste dérivée par l'appelant (`api/routes/ingestion.py::ajouter_commande`).
"""

from __future__ import annotations

import re
from typing import NamedTuple

from adapters.competence_derivation import deriver_compatibilites_par_competence
from api.etat import EtapeProcessus
from dsl.schema import CompetenceRequise, Contrainte, InstanceTRCO, Precedence, Ressource, Tache

# Même motif que `dsl/schema/common.py::Identifiant`. Longueur bornée plus bas que les 64
# caractères du DSL : l'id de tâche généré préfixe celui de l'étape par l'id de commande
# (`cmd-xxxxxxxx_`, 13 caractères), qui doit tenir dans la limite du DSL.
_MOTIF_ID_ETAPE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class ErreurProcessus(Exception):
    """Processus mal formé (étape en double, prédécesseur inconnu, cycle...) ou inutilisable dans
    cet atelier (aucune étape réalisable) — toujours une erreur explicite, jamais une commande
    éclatée à moitié en silence."""


class ResultatEclatement(NamedTuple):
    instance: InstanceTRCO
    taches_creees: tuple[str, ...]
    avertissements: tuple[str, ...]


def valider_processus(etapes: tuple[EtapeProcessus, ...]) -> None:
    """Lève `ErreurProcessus` au premier défaut trouvé. Appelée à l'enregistrement du processus
    (`PUT /ingestion/{instance_id}/processus`) : un processus invalide ne doit jamais être stocké
    pour n'échouer qu'à la première commande, des jours plus tard."""
    if not etapes:
        raise ErreurProcessus("le processus doit contenir au moins une étape")

    ids = [e.id for e in etapes]
    doublons = sorted({i for i in ids if ids.count(i) > 1})
    if doublons:
        raise ErreurProcessus(f"identifiant d'étape en double : {doublons}")

    connus = set(ids)
    for etape in etapes:
        if not _MOTIF_ID_ETAPE.match(etape.id):
            raise ErreurProcessus(
                f"identifiant d'étape invalide {etape.id!r} : lettres, chiffres, '_' et '-' "
                "uniquement, 40 caractères au plus"
            )
        if not etape.competences:
            raise ErreurProcessus(f"l'étape {etape.id!r} doit exiger au moins une compétence")
        if etape.duree_par_piece < 1:
            raise ErreurProcessus(f"l'étape {etape.id!r} doit avoir une durée par pièce d'au moins 1")
        inconnus = sorted(set(etape.predecesseurs) - connus)
        if inconnus:
            raise ErreurProcessus(f"l'étape {etape.id!r} référence des étapes inconnues : {inconnus}")
        if etape.id in etape.predecesseurs:
            raise ErreurProcessus(f"l'étape {etape.id!r} ne peut pas se précéder elle-même")

    _verifier_absence_de_cycle(etapes)


def _verifier_absence_de_cycle(etapes: tuple[EtapeProcessus, ...]) -> None:
    """Un cycle (A avant B avant A) rendrait toute commande infaisable : le solveur renverrait
    `None` sans que personne ne comprenne pourquoi. Tri topologique de Kahn."""
    predecesseurs = {e.id: set(e.predecesseurs) for e in etapes}
    restantes = dict(predecesseurs)
    while restantes:
        pretes = [i for i, preds in restantes.items() if not preds & restantes.keys()]
        if not pretes:
            raise ErreurProcessus(f"le processus contient un cycle entre les étapes {sorted(restantes)}")
        for i in pretes:
            del restantes[i]


def _etape_realisable(etape: EtapeProcessus, ressources: list[Ressource]) -> bool:
    """Réalisable dans cet atelier si au moins une ressource couvre *toutes* les compétences de
    l'étape — même critère que `deriver_compatibilites_par_competence`."""
    return any(set(etape.competences) <= set(r.competences) for r in ressources)


def _predecesseurs_effectifs(
    etape_id: str, par_id: dict[str, EtapeProcessus], realisables: set[str], memo: dict[str, set[str]]
) -> set[str]:
    """Prédécesseurs réalisables de `etape_id`, en traversant les étapes ignorées : si B est
    ignorée dans A → B → C, C attend A. Sans ça, sauter une étape du milieu ferait perdre tout
    l'ordre en amont d'elle, et C pourrait démarrer avant A."""
    if etape_id in memo:
        return memo[etape_id]
    effectifs: set[str] = set()
    for predecesseur in par_id[etape_id].predecesseurs:
        if predecesseur in realisables:
            effectifs.add(predecesseur)
        else:
            effectifs |= _predecesseurs_effectifs(predecesseur, par_id, realisables, memo)
    memo[etape_id] = effectifs
    return effectifs


def eclater_processus(
    instance: InstanceTRCO,
    etapes: tuple[EtapeProcessus, ...],
    commande_id: str,
    quantite: int,
) -> ResultatEclatement:
    """Ajoute à `instance` une copie des étapes du processus pour la commande `commande_id` :
    une `Tache` par étape réalisable (id `f"{commande_id}_{etape.id}"`, `nom` repris de l'étape,
    `quantite` renseignée), une `CompetenceRequise` par compétence, une `Precedence` par
    prédécesseur effectif, et les compatibilités dérivées des compétences avec une durée de
    `duree_par_piece × quantite`.

    Une étape qu'aucune ressource de l'atelier ne sait faire est ignorée avec un avertissement
    (§FC4 : signalée, jamais silencieuse) ; si aucune ne l'est, `ErreurProcessus`. `instance`
    n'est jamais mutée : tous ses champs (`unite_temps`, `jours_fermes`...) sont repris tels
    quels dans l'instance renvoyée, à faire persister par l'appelant."""
    if quantite < 1:
        raise ErreurProcessus("la quantité doit être d'au moins 1")
    valider_processus(etapes)

    par_id = {e.id: e for e in etapes}
    realisables = {e.id for e in etapes if _etape_realisable(e, instance.ressources)}
    if not realisables:
        raise ErreurProcessus(
            "aucune étape du processus n'est réalisable dans cet atelier : aucune ressource ne "
            "possède les compétences demandées"
        )

    avertissements = [
        f"étape {e.nom or e.id!r} ignorée : aucune ressource de l'atelier ne possède {list(e.competences)}"
        for e in etapes
        if e.id not in realisables
    ]

    ids_existants = {t.id for t in instance.taches}
    nouvelles_taches: list[Tache] = []
    nouvelles_contraintes: list[Contrainte] = []
    durees: dict[str, int] = {}
    memo: dict[str, set[str]] = {}

    def id_tache(etape_id: str) -> str:
        return f"{commande_id}_{etape_id}"

    for etape in etapes:
        if etape.id not in realisables:
            continue
        tache_id = id_tache(etape.id)
        if tache_id in ids_existants:
            raise ErreurProcessus(f"la tâche {tache_id!r} existe déjà dans l'atelier")
        nouvelles_taches.append(Tache(id=tache_id, nom=etape.nom, quantite=quantite))
        durees[tache_id] = etape.duree_par_piece * quantite
        nouvelles_contraintes.extend(CompetenceRequise(tache=tache_id, competence=c) for c in etape.competences)
        nouvelles_contraintes.extend(
            Precedence(avant=id_tache(p), apres=tache_id)
            for p in sorted(_predecesseurs_effectifs(etape.id, par_id, realisables, memo))
        )

    # Uniquement les contraintes des tâches créées ici : la dérivation exige une durée pour toute
    # tâche à compétence requise qu'on lui passe, y compris celles déjà présentes dans l'atelier.
    compatibilites = deriver_compatibilites_par_competence(nouvelles_contraintes, instance.ressources, durees)

    instance_fusionnee = InstanceTRCO(
        **{
            **dict(instance),
            "taches": [*instance.taches, *nouvelles_taches],
            "contraintes": [*instance.contraintes, *nouvelles_contraintes, *compatibilites],
        }
    )
    return ResultatEclatement(
        instance=instance_fusionnee,
        taches_creees=tuple(t.id for t in nouvelles_taches),
        avertissements=tuple(avertissements),
    )

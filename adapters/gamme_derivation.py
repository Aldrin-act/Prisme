"""Explosion d'une ou plusieurs gammes réutilisables (`api.etat.GammeProduit`) en tâches DSL
concrètes à l'arrivée d'une commande — couche d'ingestion, jamais un axe T-R-C-O (même statut que
`adapters/commande_derivation.py::Commande`, réutilisé ici tel quel, jamais modifié).

Une gamme décrit un gabarit d'étapes (compétences requises, ordre via prédécesseurs) une fois par
produit ; l'explosion instancie ce gabarit en `Tache`/`Precedence`/`CompetenceRequise` fraîches,
préfixées par un identifiant de commande *et* de gamme (une commande peut référencer plusieurs
gammes — plusieurs produits — dans la même requête, voir `traiter_nouvelle_commande` ci-dessous ;
le préfixe de gamme évite toute collision entre deux gammes qui réutiliseraient le même id
d'étape), puis laisse les briques de dérivation déjà existantes (`competence_derivation.py`,
`commande_derivation.py`) calculer compatibilités et échéance — exactement la même séquence que
`traduire()` (`adapters/csv_import/traducteur.py`, `adapters/json_import/traducteur.py`), jamais
dupliquée ici.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from pydantic import ValidationError

from adapters.competence_derivation import completer_durees_par_estimation, deriver_compatibilites_par_competence
from api.etat import GammeProduit
from dsl.schema import CompetenceRequise, Contrainte, InstanceTRCO, Precedence, Ressource, Tache

if TYPE_CHECKING:
    from estimation import EstimateurDuree


class ErreurExplosionGamme(Exception):
    """L'explosion d'une gamme produirait un id de tâche invalide, dupliqué au sein de la gamme
    elle-même, ou déjà présent dans l'instance cible — jamais un écrasement silencieux d'une tâche
    existante. La validation du motif `Identifiant` est déjà faite côté éditeur visuel de gammes
    à la création, mais revérifiée ici (garde-fou en profondeur, même principe que §6.7)."""


class GammeAvecQuantite(NamedTuple):
    """Une entrée de la liste de gammes d'une commande — voir
    `traiter_nouvelle_commande` ci-dessous."""

    gamme: GammeProduit
    quantite: int | None


class ResultatExplosionGammes(NamedTuple):
    """Résultat de `traiter_nouvelle_commande` — l'instance fusionnée, les ids des tâches
    fraîchement explosées (à combiner par l'appelant avec toute tâche choisie directement pour la
    même commande avant de dériver une échéance commune, voir `api/routes/ingestion.py::
    ajouter_commande`), et les avertissements éventuels (§FC4, décision humaine préservée)."""

    instance: InstanceTRCO
    taches_explodees: tuple[str, ...]
    avertissements: tuple[str, ...]


def _etape_realisable(etape_competences: tuple[str, ...], ressources: list[Ressource]) -> bool:
    """Une étape est réalisable dans cet atelier si au moins une de ses ressources couvre *toutes*
    les compétences qu'elle exige — même critère que `adapters/competence_derivation.py::
    deriver_compatibilites_par_competence` (une compatibilité ne se dérive que pour une ressource
    qui couvre l'ensemble des compétences requises, jamais une intersection partielle)."""
    requises = set(etape_competences)
    return any(requises <= set(r.competences) for r in ressources)


def exploser_gamme(
    commande_id: str,
    prefixe_gamme: str,
    quantite: int | None,
    gamme: GammeProduit,
    ressources: list[Ressource],
    ids_taches_existantes: set[str],
) -> tuple[list[Tache], list[Contrainte], list[str]]:
    """Instancie chaque étape *réalisable dans cet atelier* de `gamme` en une `Tache` fraîche (id
    `f"{commande_id}_{prefixe_gamme}_{etape.id}"`, `produit=gamme.produit`) plus une
    `CompetenceRequise` par compétence exigée et une `Precedence` par prédécesseur déclaré —
    plusieurs prédécesseurs pour une même étape expriment une fusion (plusieurs sous-produits qui
    convergent vers une étape commune), sans mécanisme dédié. Une étape dont aucune ressource de
    `ressources` (celles de l'instance cible — l'« atelier ») ne couvre toutes les compétences
    requises est **ignorée** plutôt que de faire échouer toute l'explosion (un atelier ne réalise
    pas forcément toutes les étapes d'une gamme générique) — signalée par un avertissement (§FC4,
    décision humaine préservée), jamais silencieusement. Une précédence référençant une étape
    ignorée est également omise (l'étape suivante n'attend alors plus une étape qui n'aura jamais
    lieu dans cet atelier). `prefixe_gamme` (typiquement l'index de cette gamme dans la liste de la
    requête) distingue les tâches de deux gammes différentes explosées pour la même commande, même
    si elles réutilisent le même id d'étape. `ids_taches_existantes` — les ids déjà présents dans
    l'instance cible (toutes gammes déjà explosées de cette même commande comprises) — pour
    refuser toute collision plutôt que d'écraser une tâche en silence."""
    ids_locaux = {etape.id for etape in gamme.etapes}
    ids_locaux_realisables = {
        etape.id for etape in gamme.etapes if _etape_realisable(etape.competences, ressources)
    }
    if not ids_locaux_realisables:
        raise ErreurExplosionGamme(
            f"aucune étape de la gamme {gamme.produit!r} n'est réalisable dans cet atelier "
            "(compétences requises non couvertes par une ressource de l'instance)"
        )

    avertissements = [
        f"étape {etape.id!r} de la gamme {gamme.produit!r} ignorée : aucune ressource de "
        f"l'atelier ne couvre {list(etape.competences)}"
        for etape in gamme.etapes
        if etape.id not in ids_locaux_realisables
    ]

    taches: list[Tache] = []
    contraintes: list[Contrainte] = []

    for etape in gamme.etapes:
        if etape.id not in ids_locaux_realisables:
            continue
        tache_id = f"{commande_id}_{prefixe_gamme}_{etape.id}"
        try:
            tache = Tache(id=tache_id, produit=gamme.produit, quantite=quantite)
        except ValidationError as erreur:
            raise ErreurExplosionGamme(
                f"id de tâche invalide généré pour l'étape {etape.id!r} : {tache_id!r}"
            ) from erreur
        if tache_id in ids_taches_existantes:
            raise ErreurExplosionGamme(f"la tâche {tache_id!r} existe déjà dans l'instance cible")
        taches.append(tache)

        for competence in etape.competences:
            contraintes.append(CompetenceRequise(tache=tache_id, competence=competence))
        for predecesseur_id in etape.predecesseurs:
            if predecesseur_id not in ids_locaux:
                raise ErreurExplosionGamme(
                    f"l'étape {etape.id!r} référence un prédécesseur inconnu de cette gamme : {predecesseur_id!r}"
                )
            if predecesseur_id not in ids_locaux_realisables:
                continue
            avant = f"{commande_id}_{prefixe_gamme}_{predecesseur_id}"
            contraintes.append(Precedence(avant=avant, apres=tache_id))

    return taches, contraintes, avertissements


def traiter_nouvelle_commande(
    instance: InstanceTRCO,
    gammes: list[GammeAvecQuantite],
    commande_id: str,
    estimateur_duree: EstimateurDuree | None = None,
    index_depart: int = 0,
) -> ResultatExplosionGammes:
    """Fusionne une ou plusieurs gammes (chacune avec sa propre quantité) dans `instance` —
    explosion de chaque gamme (préfixée par son index dans `gammes`, décalé de `index_depart`,
    voir `exploser_gamme`), puis (si un estimateur est fourni) estimation des durées manquantes,
    puis dérivation des compatibilités par compétence. Ne dérive **pas** d'échéance elle-même —
    contrairement à l'ancienne version à une seule gamme : une commande pouvant désormais combiner
    plusieurs gammes *et* des tâches choisies directement, la dérivation d'échéance se fait une
    seule fois, côté appelant (`api/routes/ingestion.py::ajouter_commande`/
    `ajouter_produit_a_commande`), sur l'ensemble complet des tâches de la commande (explosées ici
    + choisies directement).

    `index_depart` (par défaut 0, comportement inchangé pour une commande neuve) : le nombre de
    gammes déjà explosées pour cette même commande lors d'appels précédents — évite toute
    collision de préfixe quand un produit est ajouté après coup à une commande qui en a déjà
    (`ajouter_produit_a_commande`, qui passe `len(commande.gammes)`).

    `instance` n'est jamais mutée : le résultat est une instance neuve, à faire persister par
    l'appelant (`EtatAPI.modifier_instance`)."""
    ids_existants = {t.id for t in instance.taches}
    nouvelles_taches: list[Tache] = []
    nouvelles_contraintes: list[Contrainte] = []
    durees_connues: dict[str, int] = {}
    avertissements: list[str] = []

    for decalage, (gamme, quantite) in enumerate(gammes):
        prefixe_gamme = str(index_depart + decalage)
        taches_gamme, contraintes_gamme, avertissements_gamme = exploser_gamme(
            commande_id, prefixe_gamme, quantite, gamme, instance.ressources, ids_existants
        )
        nouvelles_taches.extend(taches_gamme)
        nouvelles_contraintes.extend(contraintes_gamme)
        avertissements.extend(avertissements_gamme)
        ids_existants |= {t.id for t in taches_gamme}
        ids_realisees = {t.id for t in taches_gamme}
        # Durée déclarée par étape (`EtapeGamme.duree_nominale`) — source primaire, même
        # préséance que `TacheAvecDureeEstimee.duree_estimee_jours` des adaptateurs CSV/JSON :
        # l'estimateur ML ne comble que ce qui reste manquant après elle. Uniquement pour les
        # étapes réellement explosées (une étape ignorée, voir exploser_gamme, n'a pas de tâche).
        durees_connues |= {
            f"{commande_id}_{prefixe_gamme}_{etape.id}": etape.duree_nominale
            for etape in gamme.etapes
            if etape.duree_nominale is not None and f"{commande_id}_{prefixe_gamme}_{etape.id}" in ids_realisees
        }

    taches = [*instance.taches, *nouvelles_taches]
    contraintes = [*instance.contraintes, *nouvelles_contraintes]

    if estimateur_duree is not None:
        durees_connues, avertissements_estimation = completer_durees_par_estimation(
            contraintes, instance.ressources, taches, durees_connues, estimateur_duree
        )
        avertissements.extend(avertissements_estimation)

    compatibilites_derivees = deriver_compatibilites_par_competence(
        contraintes, instance.ressources, durees_connues
    )

    instance_fusionnee = InstanceTRCO(
        taches=taches,
        ressources=instance.ressources,
        contraintes=[*contraintes, *compatibilites_derivees],
        objectifs=instance.objectifs,
        unite_temps=instance.unite_temps,
    )
    return ResultatExplosionGammes(
        instance=instance_fusionnee,
        taches_explodees=tuple(t.id for t in nouvelles_taches),
        avertissements=tuple(avertissements),
    )

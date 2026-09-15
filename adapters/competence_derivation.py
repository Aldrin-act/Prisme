"""Dérivation de compatibilité ressource-tâche à partir des compétences —
partagée entre les adaptateurs d'ingestion qui la proposent (`csv_import`,
`json_import`) plutôt que dupliquée : une ressource est jugée compatible avec
une tâche si `Ressource.competences` couvre *toutes* les compétences exigées
par cette tâche (`CompetenceRequise`), avec la durée estimée de la tâche
(fournie à part, hors DSL — `Tache` n'a délibérément aucun champ de durée,
§4.2, elle dépend de la ressource en vrai FJSP flexible) appliquée telle
quelle à chaque ressource ainsi qualifiée. Même principe que
`adapters/greensig/translator.py` (`equipes_compatibles_pour`/
`duree_heures_pour`) : une durée par tâche, pas par couple, faute de mieux
quand seules des compétences sont déclarées.

Une compatibilité déjà explicite pour un couple (tâche, ressource) l'emporte
toujours sur une dérivation pour ce même couple, plutôt que de produire un
doublon contradictoire (deux durées différentes pour la même paire). Le DSL
lui-même (`dsl/schema/instance.py`, `InstanceTRCO._competences_requises_respectees`)
revérifie ensuite que toute compatibilité pour une tâche à compétences
requises — dérivée ou explicite — les couvre bien toutes ; un garde-fou de
plus, jamais remplacé ici.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from dsl.schema import CompatibiliteRessourceTache, CompetenceRequise, Contrainte, InstanceTRCO, Ressource, Tache

if TYPE_CHECKING:
    from estimation import EstimateurDuree


@dataclass(frozen=True)
class ResultatTraduction:
    """Résultat d'une traduction d'adaptateur (`csv_import`/`json_import`) —
    une instance T-R-C-O plus les avertissements à faire vérifier par un
    humain (§FC4, décision humaine préservée), notamment quand une durée
    manquante a été comblée par un `EstimateurDuree` plutôt que déclarée.
    Même forme que `ResultatComprehension`
    (`adapters/agent_comprehension/agent.py`)."""

    instance: InstanceTRCO
    avertissements: tuple[str, ...] = ()


class CompetenceSansDureeEstimee(Exception):
    """Une tâche exige une compétence mais aucune durée estimée n'est fournie
    pour elle — impossible de dériver sa compatibilité sans savoir combien de
    temps l'opération prend."""

    def __init__(self, tache_id: str) -> None:
        self.tache_id = tache_id
        super().__init__(
            f"durée estimée manquante pour {tache_id!r}, requise pour dériver sa compatibilité par compétence"
        )


def deriver_compatibilites_par_competence(
    contraintes: list[Contrainte],
    ressources: list[Ressource],
    durees_estimees_par_tache: dict[str, int],
) -> list[Contrainte]:
    """Renvoie les `CompatibiliteRessourceTache` dérivées à ajouter aux
    contraintes existantes (jamais les contraintes déjà présentes elles-mêmes).
    Lève `CompetenceSansDureeEstimee` si une tâche exige une compétence sans
    durée estimée connue dans `durees_estimees_par_tache`."""
    competences_requises_par_tache: dict[str, set[str]] = defaultdict(set)
    paires_deja_explicites: set[tuple[str, str]] = set()
    for contrainte in contraintes:
        if isinstance(contrainte, CompetenceRequise):
            competences_requises_par_tache[contrainte.tache].add(contrainte.competence)
        elif isinstance(contrainte, CompatibiliteRessourceTache):
            paires_deja_explicites.add((contrainte.tache, contrainte.ressource))

    derivees: list[Contrainte] = []
    for tache_id, requises in competences_requises_par_tache.items():
        duree = durees_estimees_par_tache.get(tache_id)
        if duree is None:
            raise CompetenceSansDureeEstimee(tache_id)
        for ressource in ressources:
            if (tache_id, ressource.id) in paires_deja_explicites:
                continue
            if requises <= set(ressource.competences):
                derivees.append(CompatibiliteRessourceTache(tache=tache_id, ressource=ressource.id, duree=duree))
    return derivees


def completer_durees_par_estimation(
    contraintes: list[Contrainte],
    ressources: list[Ressource],
    taches: list[Tache],
    durees_connues: dict[str, int],
    estimateur_duree: EstimateurDuree,
) -> tuple[dict[str, int], list[str]]:
    """Comble, via `estimateur_duree`, la durée des tâches à compétence(s)
    requise(s) qui n'ont encore aucune durée connue dans `durees_connues` —
    seulement si au moins une ressource déclarée couvre les compétences
    exigées (sinon rien à estimer : c'est la ressource elle-même qui manque,
    pas seulement sa durée — `CompetenceSansDureeEstimee` se lèvera plus
    loin, comme aujourd'hui). Ne mute jamais `durees_connues` : renvoie un
    nouveau dict complété, et un avertissement par tâche comblée, pour que
    l'appelant les rende visibles (§FC4, décision humaine préservée) plutôt
    que de laisser une estimation se fondre silencieusement dans une donnée
    déclarée."""
    competences_requises_par_tache: dict[str, set[str]] = defaultdict(set)
    for contrainte in contraintes:
        if isinstance(contrainte, CompetenceRequise):
            competences_requises_par_tache[contrainte.tache].add(contrainte.competence)

    taches_par_id = {t.id: t for t in taches}
    durees_completees = dict(durees_connues)
    avertissements: list[str] = []
    for tache_id, requises in competences_requises_par_tache.items():
        if tache_id in durees_completees:
            continue
        tache = taches_par_id.get(tache_id)
        if tache is None:
            continue
        candidates = sorted((r for r in ressources if requises <= set(r.competences)), key=lambda r: r.id)
        if not candidates:
            continue
        estimation = estimateur_duree.estimer(tache, candidates[0])
        durees_completees[tache_id] = estimation.duree_estimee_jours
        avertissements.append(
            f"durée de {tache_id!r} estimée par apprentissage automatique "
            f"({estimation.duree_estimee_jours} j, confiance {estimation.confiance:.2f}) — à valider"
        )
    return durees_completees, avertissements

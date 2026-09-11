"""Métriques comparatives entre scénarios (what-if, `groupe_scenario_id` sur `InstanceTRCO`,
voir `api/etat.py`) — calcul pur sur une instance et un planning déjà produits, jamais
d'exécution ni de solveur ici : `GET /ingestion/{instance_id}/scenarios/comparaison`
(`api/routes/ingestion.py`) rassemble d'abord la dernière exécution connue de chaque instance
du groupe, puis appelle `calculer_metriques` sur chacune.

Trois métriques, dérivées de ce que `Planning`/`InstanceTRCO` portent déjà (rien de nouveau à
demander à l'utilisateur) :
- `makespan` : instant de fin de la dernière opération.
- `taux_utilisation_par_ressource` : part du makespan que chaque ressource a passé occupée.
- `taches_en_retard` : tâches dont la fin dépasse une `Echeance` déclarée pour elles.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from api.etat import durees_par_contrainte
from dsl.schema import Echeance, InstanceTRCO, Planning


@dataclass(frozen=True)
class MetriquesPlanning:
    makespan: int
    taux_utilisation_par_ressource: dict[str, float]
    taches_en_retard: tuple[str, ...]

    def en_dict(self) -> dict[str, object]:
        return {
            "makespan": self.makespan,
            "taux_utilisation_par_ressource": self.taux_utilisation_par_ressource,
            "taches_en_retard": list(self.taches_en_retard),
        }


def fin_par_tache(instance: InstanceTRCO, planning: Planning) -> dict[str, int]:
    """Instant de fin de chaque tâche planifiée (`debut + durée`) — durée résolue depuis la
    `CompatibiliteRessourceTache` réellement choisie par le planning (`operation.tache|
    operation.ressource`), 0 si absente (ne devrait pas arriver sur un planning légal). Factorisé
    hors de `calculer_metriques` : réutilisé aussi par `calculer_statut_commande`."""
    durees = durees_par_contrainte(instance)
    resultat: dict[str, int] = {}
    for operation in planning.operations:
        duree = durees.get(f"{operation.tache}|{operation.ressource}", 0)
        resultat[operation.tache] = operation.debut + duree
    return resultat


def calculer_metriques(instance: InstanceTRCO, planning: Planning) -> MetriquesPlanning:
    """Suppose un planning déjà légal (garde-fou de faisabilité déjà passé en amont, à
    l'exécution — voir `sandbox/runner.py::ResultatExecution.reussi`) : ne revérifie rien,
    calcule seulement des métriques d'observation dessus."""
    durees = durees_par_contrainte(instance)
    fins = fin_par_tache(instance, planning)
    duree_occupee_par_ressource: dict[str, int] = defaultdict(int)
    for operation in planning.operations:
        duree_occupee_par_ressource[operation.ressource] += durees.get(
            f"{operation.tache}|{operation.ressource}", 0
        )

    makespan = max(fins.values(), default=0)

    echeance_par_tache = {c.tache: c.echeance for c in instance.contraintes if isinstance(c, Echeance)}
    taches_en_retard = tuple(
        sorted(
            tache_id
            for tache_id, fin in fins.items()
            if tache_id in echeance_par_tache and fin > echeance_par_tache[tache_id]
        )
    )

    taux_utilisation = {
        ressource_id: round(duree_occupee / makespan * 100, 1) if makespan else 0.0
        for ressource_id, duree_occupee in duree_occupee_par_ressource.items()
    }

    return MetriquesPlanning(
        makespan=makespan,
        taux_utilisation_par_ressource=taux_utilisation,
        taches_en_retard=taches_en_retard,
    )


@dataclass(frozen=True)
class StatutCommande:
    planifiee: bool
    date_fin_prevue: int | None
    en_retard: bool | None
    taches_manquantes: tuple[str, ...]

    def en_dict(self) -> dict[str, object]:
        return {
            "planifiee": self.planifiee,
            "date_fin_prevue": self.date_fin_prevue,
            "en_retard": self.en_retard,
            "taches_manquantes": list(self.taches_manquantes),
        }


def calculer_statut_commande(
    instance: InstanceTRCO, planning: Planning | None, taches: tuple[str, ...], date_limite: int | None
) -> StatutCommande:
    """Statut d'une commande (`CommandeEnregistree`, `api/etat.py`) contre le dernier planning
    réussi de son instance. `planning=None` (jamais exécutée avec succès) ou des tâches encore
    absentes du planning (commande ajoutée après la dernière exécution, réexécution pas encore
    relancée) sont deux vraies raisons pour `planifiee=False` — jamais confondues avec "en
    retard" (`en_retard=None` dans les deux cas : aucun jugement possible sans planning complet
    pour cette commande)."""
    if planning is None:
        return StatutCommande(planifiee=False, date_fin_prevue=None, en_retard=None, taches_manquantes=taches)

    fins = fin_par_tache(instance, planning)
    manquantes = tuple(t for t in taches if t not in fins)
    if manquantes:
        return StatutCommande(planifiee=False, date_fin_prevue=None, en_retard=None, taches_manquantes=manquantes)

    date_fin_prevue = max(fins[t] for t in taches)
    en_retard = date_fin_prevue > date_limite if date_limite is not None else None
    return StatutCommande(
        planifiee=True, date_fin_prevue=date_fin_prevue, en_retard=en_retard, taches_manquantes=()
    )

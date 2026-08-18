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


def calculer_metriques(instance: InstanceTRCO, planning: Planning) -> MetriquesPlanning:
    """Suppose un planning déjà légal (garde-fou de faisabilité déjà passé en amont, à
    l'exécution — voir `sandbox/runner.py::ResultatExecution.reussi`) : ne revérifie rien,
    calcule seulement des métriques d'observation dessus."""
    durees = durees_par_contrainte(instance)
    fin_par_tache: dict[str, int] = {}
    duree_occupee_par_ressource: dict[str, int] = defaultdict(int)
    for operation in planning.operations:
        duree = durees.get(f"{operation.tache}|{operation.ressource}", 0)
        fin_par_tache[operation.tache] = operation.debut + duree
        duree_occupee_par_ressource[operation.ressource] += duree

    makespan = max(fin_par_tache.values(), default=0)

    echeance_par_tache = {c.tache: c.echeance for c in instance.contraintes if isinstance(c, Echeance)}
    taches_en_retard = tuple(
        sorted(
            tache_id
            for tache_id, fin in fin_par_tache.items()
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

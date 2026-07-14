"""Calcul du makespan d'un planning : la fin de sa dernière opération."""

from __future__ import annotations

from dsl.schema import CompatibiliteMachineTache, InstanceTRCO, Planning


def calculer_makespan(instance: InstanceTRCO, planning: Planning) -> int:
    duree = {
        (c.tache, c.ressource): c.duree for c in instance.contraintes if isinstance(c, CompatibiliteMachineTache)
    }
    fins = [
        operation.debut + duree[(operation.tache, operation.ressource)]
        for operation in planning.operations
        if (operation.tache, operation.ressource) in duree
    ]
    return max(fins, default=0)

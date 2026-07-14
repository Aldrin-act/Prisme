"""Calcul du makespan d'un planning : la fin de sa dernière opération."""

from __future__ import annotations

from dsl.schema import InstanceTRCO, Planning


def calculer_makespan(instance: InstanceTRCO, planning: Planning) -> int:
    duree = {tache.id: tache.duree for tache in instance.taches}
    fins = [
        operation.debut + duree[operation.tache]
        for operation in planning.operations
        if operation.tache in duree
    ]
    return max(fins, default=0)

"""Calcul du makespan d'un planning : la fin de sa dernière opération (fin calendaire si l'instance
porte un calendrier ouvré, voir `dsl/calendrier.py`)."""

from __future__ import annotations

from dsl.calendrier import fin_calendaire
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, Planning


def calculer_makespan(instance: InstanceTRCO, planning: Planning) -> int:
    duree = {
        (c.tache, c.ressource): c.duree for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)
    }
    fins = [
        fin_calendaire(instance, operation.debut, duree[(operation.tache, operation.ressource)])
        for operation in planning.operations
        if (operation.tache, operation.ressource) in duree
    ]
    return max(fins, default=0)

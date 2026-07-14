"""Planning : la sortie d'un solveur — chaque tâche affectée à une ressource
à un instant de début (§5.5, canal opérationnel).

Ce n'est pas un axe d'entrée du DSL T-R-C-O : c'est le résultat que le
vérificateur de faisabilité (`validation_engine/feasibility_checker.py`)
confronte à une `InstanceTRCO` pour en juger la légalité (§6.2, §6.7). Il vit
ici, à côté des quatre axes, parce qu'il partage leur vocabulaire
(`Identifiant`) et que le DSL joue aussi un rôle de cadre de validation.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .common import Identifiant


class OperationPlanifiee(BaseModel):
    """Une tâche affectée à une ressource, à un instant de début donné."""

    model_config = ConfigDict(extra="forbid")

    tache: Identifiant
    ressource: Identifiant
    debut: int = Field(ge=0, description="Instant de début, en minutes")


class Planning(BaseModel):
    """Un planning proposé pour une instance T-R-C-O.

    Volontairement permissif : les incohérences (tâche non planifiée,
    planifiée deux fois, référence à une tâche/ressource inconnue, etc.) sont
    du ressort du vérificateur de faisabilité, pas de ce schéma — un planning
    illégal doit produire un `ResultatFaisabilite` diagnostiqué, jamais une
    exception à la construction (c'est le prix à payer pour servir de
    garde-fou de production, §6.7).
    """

    model_config = ConfigDict(extra="forbid")

    operations: list[OperationPlanifiee] = Field(default_factory=list)

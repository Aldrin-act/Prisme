"""C — Contraintes : précédence et compatibilité machine-tâche, le noyau minimal (§3.1, §4).

Une contrainte est un objet discriminé par son champ `type`, pour rester
homogène et extensible : préemptibilité, périmètre de replanification, etc.
(§3.2) viendront s'ajouter à cette union sans toucher aux contraintes
existantes.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import Identifiant


class Precedence(BaseModel):
    """La tâche `avant` doit être terminée avant que `apres` ne commence."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["precedence"] = "precedence"
    avant: Identifiant
    apres: Identifiant

    @model_validator(mode="after")
    def _pas_d_autoreference(self) -> "Precedence":
        if self.avant == self.apres:
            raise ValueError("une tâche ne peut pas se précéder elle-même")
        return self


class CompatibiliteMachineTache(BaseModel):
    """La tâche `tache` ne peut s'exécuter que sur la ressource `ressource`.

    Une tâche compatible avec plusieurs ressources est décrite par plusieurs
    contraintes de ce type (une par ressource compatible), pour garder chaque
    contrainte atomique et homogène (§4.2).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["compatibilite_machine_tache"] = "compatibilite_machine_tache"
    tache: Identifiant
    ressource: Identifiant


Contrainte = Annotated[
    Union[Precedence, CompatibiliteMachineTache],
    Field(discriminator="type"),
]

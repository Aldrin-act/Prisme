"""C — Contraintes : précédence et compatibilité ressource-tâche, le noyau minimal (§3.1, §4).

Une contrainte est un objet discriminé par son champ `type`, pour rester
homogène et extensible : préemptibilité, périmètre de replanification, etc.
(§3.2) viendront s'ajouter à cette union sans toucher aux contraintes
existantes.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import Identifiant


class Precedence(BaseModel):
    """La tâche `avant` doit être terminée avant que `apres` ne commence."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["precedence"] = "precedence"
    avant: Identifiant
    apres: Identifiant

    @model_validator(mode="after")
    def _pas_d_autoreference(self) -> Precedence:
        if self.avant == self.apres:
            raise ValueError("une tâche ne peut pas se précéder elle-même")
        return self


class CompatibiliteRessourceTache(BaseModel):
    """La tâche `tache` peut s'exécuter sur la ressource `ressource`, avec la durée `duree`
    propre à ce couple (tâche, ressource) — deux ressources compatibles pour la même tâche
    peuvent avoir des durées différentes (FJSP flexible).

    Une tâche compatible avec plusieurs ressources est décrite par plusieurs
    contraintes de ce type (une par ressource compatible, chacune portant sa
    propre durée), pour garder chaque contrainte atomique et homogène (§4.2).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["compatibilite_ressource_tache"] = "compatibilite_ressource_tache"
    tache: Identifiant
    ressource: Identifiant
    duree: int = Field(gt=0, description="Durée de l'opération sur cette ressource, en minutes")


Contrainte = Annotated[
    Precedence | CompatibiliteRessourceTache,
    Field(discriminator="type"),
]

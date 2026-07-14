"""R — Ressources : les machines/postes sur lesquels s'exécutent les tâches (§3.1, §4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .common import Identifiant


class Ressource(BaseModel):
    """Une machine ou un poste pouvant exécuter des tâches.

    La compatibilité avec les tâches est une contrainte (axe C) et vit dans
    `Contrainte`, pas ici — voir dsl/schema/contraintes.py.
    """

    model_config = ConfigDict(extra="forbid")

    id: Identifiant
    nom: str | None = None

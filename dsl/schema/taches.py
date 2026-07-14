"""T — Tâches : les opérations à ordonnancer et leur durée (§3.1, §4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .common import Identifiant


class Tache(BaseModel):
    """Une opération à ordonnancer.

    Les relations de précédence et la compatibilité avec les ressources sont
    des règles (axe C) et vivent dans `Contrainte`, pas ici — voir
    dsl/schema/contraintes.py pour le choix de répartition entre les axes.
    """

    model_config = ConfigDict(extra="forbid")

    id: Identifiant
    nom: str | None = None
    duree: int = Field(gt=0, description="Durée de l'opération, en minutes")

"""R — Ressources : les machines/postes sur lesquels s'exécutent les tâches (§3.1, §4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .common import Identifiant


class Ressource(BaseModel):
    """Une machine ou un poste pouvant exécuter des tâches.

    La compatibilité avec les tâches est une contrainte (axe C) et vit dans
    `Contrainte`, pas ici — voir dsl/schema/contraintes.py. `competences` est
    la seule exception délibérée : c'est un attribut propre à la ressource
    (ce qu'elle sait faire), pas une règle reliant deux entités — la règle
    reliant une tâche à une compétence requise est `CompetenceRequise`.
    """

    model_config = ConfigDict(extra="forbid")

    id: Identifiant
    nom: str | None = None
    competences: list[str] = Field(
        default_factory=list,
        description="Compétences détenues par cette ressource — optionnel, liste vide si non renseigné.",
    )

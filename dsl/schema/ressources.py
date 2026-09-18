"""R — Ressources : les ressource/postes sur lesquels s'exécutent les tâches (§3.1, §4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import Identifiant

TypeRessource = Literal["humain", "machine", "equipe"]


class Ressource(BaseModel):
    """Une ressource ou un poste pouvant exécuter des tâches.

    La compatibilité avec les tâches est une contrainte (axe C) et vit dans
    `Contrainte`, pas ici — voir dsl/schema/contraintes.py. `competences` est
    la seule exception délibérée : c'est un attribut propre à la ressource
    (ce qu'elle sait faire), pas une règle reliant deux entités — la règle
    reliant une tâche à une compétence requise est `CompetenceRequise`. Le
    nombre d'opérations qu'elle peut traiter simultanément n'est pas ici non
    plus, volontairement — c'est `ContrainteCapacite` (axe C), absente par
    défaut (capacité implicite de 1, une tâche à la fois).
    """

    model_config = ConfigDict(extra="forbid")

    id: Identifiant
    nom: str | None = None
    type: TypeRessource | None = Field(
        default=None,
        description="Nature de la ressource (humain/machine/equipe) — optionnel, purement "
        "informatif : ni le solveur ni le vérificateur de faisabilité n'en dépendent aujourd'hui.",
    )
    competences: list[str] = Field(
        default_factory=list,
        description="Compétences détenues par cette ressource — optionnel, liste vide si non renseigné.",
    )
    heures_par_jour: int | None = Field(
        default=None,
        ge=1,
        le=24,
        description="Durée de travail quotidienne de cette ressource, en heures (ex. 8 pour une "
        "journée de 8 h) — optionnel. Attribut propre à la ressource, comme `competences` : "
        "l'indisponibilité qui en découle reste une contrainte (axe C), dérivée à l'ingestion en "
        "`ContrainteDisponibiliteRessource` (voir `adapters/heures_travail.py`), jamais lue "
        "directement par le solveur ni par le vérificateur de faisabilité.",
    )

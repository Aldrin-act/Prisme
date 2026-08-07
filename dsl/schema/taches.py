"""T — Tâches : les opérations à ordonnancer (§3.1, §4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import Identifiant

StatutTache = Literal["a_faire", "en_cours", "termine", "bloque"]


class Tache(BaseModel):
    """Une opération à ordonnancer.

    Les relations de précédence et la compatibilité avec les ressources sont
    des règles (axe C) et vivent dans `Contrainte`, pas ici — voir
    dsl/schema/contraintes.py pour le choix de répartition entre les axes.
    Même chose pour l'échéance (`Echeance`) et les compétences requises
    (`CompetenceRequise`) : ce sont des règles, pas des champs de `Tache`.

    La durée n'est pas ici non plus : dans le FJSP flexible, elle dépend de
    la ressource choisie, pas seulement de la tâche — elle vit sur
    `CompatibiliteRessourceTache.duree` (une durée par couple tâche-ressource).
    """

    model_config = ConfigDict(extra="forbid")

    id: Identifiant
    nom: str | None = None
    priorite: int | None = Field(
        default=None,
        ge=1,
        le=5,
        description="Priorité métier, 1 (critique) à 5 (faible) — optionnel. Consommée par le "
        "code généré comme départage uniquement (choisir entre plannings de même valeur "
        "d'objectif), jamais comme un poids dans l'objectif ou une contrainte du DSL lui-même.",
    )
    statut: StatutTache | None = Field(
        default=None,
        description="Statut de suivi métier (a_faire/en_cours/termine/bloque) — optionnel, purement "
        "informatif : ni le solveur ni le vérificateur de faisabilité n'en dépendent aujourd'hui.",
    )
    quantite: int | None = Field(
        default=None,
        ge=1,
        description="Quantité produite par cette tâche (nombre d'unités) — optionnel. Consommée "
        "uniquement par `ContrainteTailleLot` pour une validation statique de lot min/max, "
        "jamais lue par le solveur ni un objectif.",
    )

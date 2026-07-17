"""T — Tâches : les opérations à ordonnancer (§3.1, §4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .common import Identifiant


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
        description="Priorité métier, 1 (critique) à 5 (faible) — optionnel, purement "
        "informatif : aucune contrainte ni objectif n'en dépend aujourd'hui.",
    )

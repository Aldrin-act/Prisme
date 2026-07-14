"""T — Tâches : les opérations à ordonnancer (§3.1, §4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .common import Identifiant


class Tache(BaseModel):
    """Une opération à ordonnancer.

    Les relations de précédence et la compatibilité avec les ressources sont
    des règles (axe C) et vivent dans `Contrainte`, pas ici — voir
    dsl/schema/contraintes.py pour le choix de répartition entre les axes.

    La durée n'est pas ici non plus : dans le FJSP flexible, elle dépend de
    la ressource choisie, pas seulement de la tâche — elle vit sur
    `CompatibiliteMachineTache.duree` (une durée par couple tâche-ressource).
    """

    model_config = ConfigDict(extra="forbid")

    id: Identifiant
    nom: str | None = None

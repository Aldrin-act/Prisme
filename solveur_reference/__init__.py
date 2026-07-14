"""solveur_reference — Solveur CP-SAT écrit à la main pour le noyau minimal.

Étape hors roadmap (§8) mais préalable à l'Étape 4 : prouve la résolubilité
du noyau, calibre la performance attendue, et sert de cas de référence pour
la fidélité sémantique (§6.2 brique 3).
"""

from .solveur import ResultatResolution, resoudre

__all__ = ["ResultatResolution", "resoudre"]

"""diagnostics — Boucle d'amélioration diagnostique (§2, §5.7, PH10-T3)."""

from .attribution import Cause, DiagnosticAttribution, diagnostiquer
from .solveur_sandbox import construire_solveur_sandbox

__all__ = ["Cause", "DiagnosticAttribution", "construire_solveur_sandbox", "diagnostiquer"]

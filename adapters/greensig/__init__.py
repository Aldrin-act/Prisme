"""greensig — Adaptateur pour un ERP réel de gestion d'espaces verts (§5.4), esquisse."""

from .extraction import extraire_payload
from .schema_greensig import (
    CompetenceGreenSIG,
    EquipeGreenSIG,
    OperateurGreenSIG,
    PayloadGreenSIG,
    TacheGreenSIG,
    TypeTacheGreenSIG,
)
from .translator import traduire

__all__ = [
    "CompetenceGreenSIG",
    "EquipeGreenSIG",
    "OperateurGreenSIG",
    "PayloadGreenSIG",
    "TacheGreenSIG",
    "TypeTacheGreenSIG",
    "extraire_payload",
    "traduire",
]

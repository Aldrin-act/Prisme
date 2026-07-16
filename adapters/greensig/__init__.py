"""greensig — Adaptateur pour un ERP réel de gestion d'espaces verts (§5.4), esquisse."""

from .schema_greensig import EquipeGreenSIG, PayloadGreenSIG, TacheGreenSIG, TypeTacheGreenSIG
from .translator import traduire

__all__ = ["EquipeGreenSIG", "PayloadGreenSIG", "TacheGreenSIG", "TypeTacheGreenSIG", "traduire"]

"""tableur — Adaptateur pour le gabarit xlsx d'ingestion T-R-C-O (§5.4)."""

from .traducteur import ErreurFichierInvalide, traduire

__all__ = ["ErreurFichierInvalide", "traduire"]

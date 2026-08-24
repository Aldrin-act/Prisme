"""csv_import — Adaptateur pour l'ingestion T-R-C-O via trois fichiers CSV
séparés (Tâches, Ressources, Contraintes), §5.4."""

from adapters.competence_derivation import ResultatTraduction

from .traducteur import ErreurFichierInvalide, traduire

__all__ = ["ErreurFichierInvalide", "ResultatTraduction", "traduire"]

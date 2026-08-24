"""json_import — Adaptateur pour l'ingestion T-R-C-O via un JSON « brut avec
compétences » (§5.4), version JSON de `adapters/csv_import/`."""

from adapters.competence_derivation import ResultatTraduction

from .traducteur import ErreurPayloadInvalide, InstanceBrute, traduire

__all__ = ["ErreurPayloadInvalide", "InstanceBrute", "ResultatTraduction", "traduire"]

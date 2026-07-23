"""O — Objectifs : ce que le planning doit optimiser (§4).

Module de compatibilité : le contenu réel (types paramétrables + union
discriminée extensible) vit dans `objectifs_parametrables.py`, ce module se
contente de le ré-exporter pour que les imports historiques
(`from dsl.schema.objectifs import MinimiserMakespan`) continuent de
fonctionner sans changement.
"""

from __future__ import annotations

from .objectifs_parametrables import (
    EquilibrerCharge,
    MaximiserUtilisation,
    MinimiserChangements,
    MinimiserMakespan,
    MinimiserRetards,
    Objectif,
)

__all__ = [
    "EquilibrerCharge",
    "MaximiserUtilisation",
    "MinimiserChangements",
    "MinimiserMakespan",
    "MinimiserRetards",
    "Objectif",
]

"""O — Objectifs : ce que le planning doit optimiser (§4). Noyau minimal : makespan seul.

`MinimiserMakespan` porte un champ `type` discriminant même en l'absence
d'autres variantes aujourd'hui, pour que l'ajout d'objectifs futurs
(équilibrage de charge, respect des délais, §3.2) se fasse par extension
plutôt que par refonte — même logique que `Contrainte`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class MinimiserMakespan(BaseModel):
    """Minimiser la date de fin de la dernière opération du planning."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["minimiser_makespan"] = "minimiser_makespan"

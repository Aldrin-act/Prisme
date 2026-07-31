"""Format propriétaire simulé de l'ERP de référence (§5.4, §7).

Volontairement différent du vocabulaire T-R-C-O — c'est tout le sens de la
couche anti-corruption : un ERP réel ne parle jamais de « Tâche » ou de
« Ressource », il a son propre jargon (« opérations », « postes »), sa
propre forme de données, souvent plus pauvre (ici : une seule affectation
poste par opération, pas de choix de routage flexible — un ERP legacy
typique ne modélise pas le FJSP). `translator.py` fait le pont vers
`InstanceTRCO`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class OperationERP(BaseModel):
    """Une opération telle que l'ERP la décrit : un poste unique, une
    opération précédente optionnelle (chaîne simple, pas de DAG complexe)."""

    model_config = ConfigDict(extra="forbid")

    code_operation: str
    duree_jours: int
    poste_id: str
    operation_precedente: str | None = None


class PosteERP(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_poste: str


class PayloadERP(BaseModel):
    """Le payload brut tel qu'il sort de l'ERP — pas encore un `InstanceTRCO`."""

    model_config = ConfigDict(extra="forbid")

    operations: list[OperationERP]
    postes: list[PosteERP]

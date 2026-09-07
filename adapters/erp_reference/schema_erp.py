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

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class OperationERP(BaseModel):
    """Une opération telle que l'ERP la décrit : un poste unique, une
    opération précédente optionnelle (chaîne simple, pas de DAG complexe).

    La durée se déclare d'une seule des deux façons : `duree_jours` (un
    entier direct, déjà dans le référentiel jours du DSL) ou
    `date_debut`/`date_fin` (un intervalle calendaire, certains ERP ne
    tracent que des dates de début/fin d'intervention plutôt qu'une durée) —
    jamais les deux, jamais ni l'un ni l'autre (voir `_duree_declaree_dune_seule_facon`
    ci-dessous). Le calcul jours = date_fin - date_debut reste ici, dans
    l'adaptateur : le DSL ne connaît toujours aucune date calendaire (voir
    `dsl/schema/contraintes.py::Echeance`)."""

    model_config = ConfigDict(extra="forbid")

    code_operation: str
    duree_jours: int | None = None
    date_debut: date | None = None
    date_fin: date | None = None
    poste_id: str
    operation_precedente: str | None = None
    competence_requise: str | None = Field(
        default=None,
        description="Compétence exigée pour cette opération, si l'ERP en trace une — "
        "traduite en CompetenceRequise, jamais en compatibilité (qui reste poste_id, seul lien fort).",
    )

    @model_validator(mode="after")
    def _duree_declaree_dune_seule_facon(self) -> OperationERP:
        dates_fournies = self.date_debut is not None or self.date_fin is not None
        if self.duree_jours is not None and dates_fournies:
            raise ValueError(
                "duree_jours et date_debut/date_fin sont mutuellement exclusifs "
                "(une seule façon de déclarer la durée par opération)"
            )
        if self.duree_jours is None and not dates_fournies:
            raise ValueError("duree_jours ou (date_debut et date_fin) doit être renseigné")
        if dates_fournies and (self.date_debut is None or self.date_fin is None):
            raise ValueError("date_debut et date_fin doivent être fournis ensemble")
        if dates_fournies and self.date_fin < self.date_debut:  # type: ignore[operator]
            raise ValueError("date_fin doit être postérieure ou égale à date_debut")
        return self


class PosteERP(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code_poste: str
    competences: list[str] = Field(
        default_factory=list, description="Compétences détenues par ce poste, si l'ERP en trace."
    )


class PayloadERP(BaseModel):
    """Le payload brut tel qu'il sort de l'ERP — pas encore un `InstanceTRCO`."""

    model_config = ConfigDict(extra="forbid")

    operations: list[OperationERP]
    postes: list[PosteERP]

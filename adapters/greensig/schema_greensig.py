"""Sous-ensemble du schéma GreenSIG (exemple de dump SQL réel, gestion
d'espaces verts) pertinent pour l'ordonnancement — anti-corruption layer
côté payload (§5.4). Volontairement partiel : seules les tables qui
touchent à la planification de tâches sont reprises ici
(`api_planification_tache`, `api_planification_typetache`,
`api_users_equipe`) ; le reste du schéma (arbres, réseau d'irrigation,
réclamations, utilisateurs...) ne concerne pas le FJSP.

`extra="forbid"` suppose qu'une couche requête/ORM en amont (non modélisée
ici) projette déjà exactement ces colonnes — comme pour `PayloadERP`, ce
module décrit le contrat du payload, pas l'accès à la base.

Champs volontairement ignorés (hors scope §4.1 "Minimal viable core" du
DSL) : `priorite`, `date_echeance`, `note_qualite`, `statut`... aucun n'a
d'équivalent en T-R-C-O aujourd'hui.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TypeTacheGreenSIG(BaseModel):
    """Ligne de `api_planification_typetache` — catalogue des types de travaux."""

    model_config = ConfigDict(extra="forbid")

    id: int
    nom_tache: str


class EquipeGreenSIG(BaseModel):
    """Ligne de `api_users_equipe` — l'équipe est la ressource planifiable
    (pas l'opérateur individuel, absent du périmètre minimal)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    nom_equipe: str
    actif: bool


class TacheGreenSIG(BaseModel):
    """Ligne de `api_planification_tache`, dénormalisée avec les équipes qui
    lui sont affectées (jointure sur `api_planification_tache_equipes`) —
    GreenSIG n'a pas de notion de précédence entre tâches dans ce schéma,
    contrairement à `OperationERP.operation_precedente` côté erp_reference.
    """

    model_config = ConfigDict(extra="forbid")

    id: int
    id_type_tache_id: int
    charge_estimee_heures: float | None
    equipes_ids: list[int]
    deleted_at: str | None = None


class PayloadGreenSIG(BaseModel):
    """Extraction brute des tables GreenSIG pertinentes — pas encore un `InstanceTRCO`."""

    model_config = ConfigDict(extra="forbid")

    taches: list[TacheGreenSIG]
    equipes: list[EquipeGreenSIG]
    types_tache: list[TypeTacheGreenSIG]

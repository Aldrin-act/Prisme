"""Sous-ensemble du schéma GreenSIG (exemple de dump SQL réel, gestion
d'espaces verts) pertinent pour l'ordonnancement — anti-corruption layer
côté payload (§5.4). Volontairement partiel : seules les tables qui
touchent à la planification de tâches sont reprises ici
(`api_planification_tache`, `api_planification_typetache`,
`api_users_equipe`, `api_users_operateur`, `api_users_competence`,
`api_users_competenceoperateur`) ; le reste du schéma (arbres, réseau
d'irrigation, réclamations...) ne concerne pas le FJSP.

`operateurs`/`competences` existent pour dériver la compatibilité
tâche-ressource par compétence réelle plutôt que par affectation
historique — la véritable notion FJSP de compatibilité est "qui sait faire
ce travail", pas "qui l'a fait par le passé" (voir `translator.py` et
`mapping/competences_types_tache.py`).

`extra="forbid"` suppose qu'une couche requête/ORM en amont (non modélisée
ici) projette déjà exactement ces colonnes — comme pour `PayloadERP`, ce
module décrit le contrat du payload, pas l'accès à la base.

Champs volontairement ignorés (hors scope §4.1 "Minimal viable core" du
DSL) : `priorite`, `date_echeance`, `note_qualite`, `statut`... aucun n'a
d'équivalent en T-R-C-O aujourd'hui.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


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


class CompetenceGreenSIG(BaseModel):
    """Ligne de `api_users_competence` — catalogue des compétences/qualifications
    techniques. Pas de table reliant directement une compétence à un type de
    tâche dans ce schéma (voir `mapping/competences_types_tache.py`)."""

    model_config = ConfigDict(extra="forbid")

    id: int
    nom_competence: str


class OperateurGreenSIG(BaseModel):
    """Ligne de `api_users_operateur` (uniquement `statut = 'ACTIF'`, filtré
    en amont côté SQL), avec les compétences qu'il détient réellement
    (jointure sur `api_users_competenceoperateur`, `niveau != 'NON'` déjà
    exclu). Sert à dériver la compatibilité équipe-type de tâche par
    compétence plutôt que par affectation historique — voir `translator.py`."""

    model_config = ConfigDict(extra="forbid")

    id: int
    equipe_id: int | None
    competences_ids: list[int]


class PayloadGreenSIG(BaseModel):
    """Extraction brute des tables GreenSIG pertinentes — pas encore un `InstanceTRCO`."""

    model_config = ConfigDict(extra="forbid")

    taches: list[TacheGreenSIG]
    equipes: list[EquipeGreenSIG]
    types_tache: list[TypeTacheGreenSIG]
    operateurs: list[OperateurGreenSIG] = Field(default_factory=list)
    competences: list[CompetenceGreenSIG] = Field(default_factory=list)

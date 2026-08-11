"""Sous-ensemble du schéma de l'API HTTP publique de GreenSIG
(`http://<hôte>/api/public/v1/`, authentification `Authorization: Bearer <clé>`) pertinent pour
l'ordonnancement — variante alternative à `schema_greensig.py` (base Postgres directe),
sélectionnée par `GREENSIG_MODE=api` (voir `service.py`).

Champs volontairement réduits à ceux consommés par `translator_api.py` — même esprit que
`schema_greensig.py`, qui ignore déjà `priorite`/`date_echeance`/`note_qualite` côté DB. Les
réclamations (`reclamations/`) ne sont pas modélisées ici : hors périmètre, décision explicite,
jamais récupérées.

`extra="ignore"` (pas `"forbid"` comme `schema_greensig.py`) : PRISME ne contrôle pas l'évolution
du schéma JSON d'un tiers, contrairement au payload DB où la requête SQL projette exactement les
colonnes attendues — un nouveau champ ajouté côté GreenSIG ne doit jamais faire échouer
l'extraction.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TacheApiGreenSIG(BaseModel):
    """Un élément de `taches/` — `reference` (ex. "PRI-SIT-ELA-12") est déjà conforme au pattern
    `Identifiant` du DSL, utilisée directement comme `Tache.id` par `translator_api.py` (plus
    traçable vers GreenSIG que l'identifiant opaque `T{id}` du chemin DB).

    `equipes` liste des **noms** d'équipe, pas des identifiants numériques (contrairement à
    `TacheGreenSIG.equipes_ids` côté DB) — seule clé de jointure disponible côté API."""

    model_config = ConfigDict(extra="ignore")

    id: int
    reference: str
    type_tache: str
    priorite: int | None = None
    equipes: list[str] = Field(default_factory=list)


class EquipeApiGreenSIG(BaseModel):
    """Un élément de `equipes/` — l'équipe reste la ressource planifiable, comme côté DB."""

    model_config = ConfigDict(extra="ignore")

    id: int
    nom_equipe: str
    actif: bool


class OperateurApiGreenSIG(BaseModel):
    """Un élément de `operateurs/` — sert uniquement à résoudre `AbsenceApiGreenSIG.operateur`
    (un nom) vers l'équipe de l'opérateur absent, par jointure sur `nom_complet`."""

    model_config = ConfigDict(extra="ignore")

    nom_complet: str
    equipe: str | None = None


class AbsenceApiGreenSIG(BaseModel):
    """Un élément de `absences/` — traduite en indisponibilité de l'**équipe** de l'opérateur
    absent (décision explicite, voir docstring de `translator_api.py`), jamais de l'opérateur
    individuel (absent du DSL, qui ne modélise que des `Ressource`)."""

    model_config = ConfigDict(extra="ignore")

    operateur: str
    date_debut: str
    date_fin: str
    statut: str


class JourFerieApiGreenSIG(BaseModel):
    """Un élément de `jours-feries/` — appliqué identiquement à chaque ressource active, même
    mécanisme de "calendrier global" que `ContrainteDisponibiliteRessource` (voir
    `dsl/schema/contraintes.py`)."""

    model_config = ConfigDict(extra="ignore")

    date: str


class PayloadGreenSIGApi(BaseModel):
    """Extraction brute des 5 ressources de l'API pertinentes pour l'ordonnancement — pas encore
    un `InstanceTRCO`, voir `translator_api.py::traduire_api`."""

    model_config = ConfigDict(extra="ignore")

    taches: list[TacheApiGreenSIG]
    equipes: list[EquipeApiGreenSIG]
    operateurs: list[OperateurApiGreenSIG] = Field(default_factory=list)
    absences: list[AbsenceApiGreenSIG] = Field(default_factory=list)
    jours_feries: list[JourFerieApiGreenSIG] = Field(default_factory=list)

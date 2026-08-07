"""C — Contraintes : précédence, compatibilité ressource-tâche, échéance,
compétence requise, capacité, incompatibilité, disponibilité ressource et
taille de lot (§3.1, §4). Les deux premières forment le noyau minimal ; les
autres sont des extensions optionnelles (aucun effet sur une instance qui ne
les utilise pas) — voir `docs/dsl/modele_ingestion_client.md`.

Une contrainte est un objet discriminé par son champ `type`, pour rester
homogène et extensible : d'autres pourront encore s'ajouter à cette union
sans toucher aux contraintes existantes.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import Identifiant


class Precedence(BaseModel):
    """La tâche `avant` doit être terminée avant que `apres` ne commence."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["precedence"] = "precedence"
    avant: Identifiant
    apres: Identifiant

    @model_validator(mode="after")
    def _pas_d_autoreference(self) -> Precedence:
        if self.avant == self.apres:
            raise ValueError("une tâche ne peut pas se précéder elle-même")
        return self


class CompatibiliteRessourceTache(BaseModel):
    """La tâche `tache` peut s'exécuter sur la ressource `ressource`, avec la durée `duree`
    propre à ce couple (tâche, ressource) — deux ressources compatibles pour la même tâche
    peuvent avoir des durées différentes (FJSP flexible).

    Une tâche compatible avec plusieurs ressources est décrite par plusieurs
    contraintes de ce type (une par ressource compatible, chacune portant sa
    propre durée), pour garder chaque contrainte atomique et homogène (§4.2).
    """

    model_config = ConfigDict(extra="forbid")

    type: Literal["compatibilite_ressource_tache"] = "compatibilite_ressource_tache"
    tache: Identifiant
    ressource: Identifiant
    duree: int = Field(gt=0, description="Durée de l'opération sur cette ressource, en jours")


class Echeance(BaseModel):
    """La tâche `tache` doit être terminée au plus tard à l'instant `echeance`
    — même référentiel que `OperationPlanifiee.debut`/`CompatibiliteRessourceTache.duree`
    (jours relatifs à un instant de référence implicite, pas une date
    calendaire : convertir une vraie date en jours reste un problème
    d'adaptateur, comme pour la conversion heures→jours déjà faite dans
    `adapters/greensig/translator.py`)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["echeance"] = "echeance"
    tache: Identifiant
    echeance: int = Field(ge=0, description="Instant limite de fin de la tâche, en jours")


class CompetenceRequise(BaseModel):
    """La tâche `tache` exige la compétence `competence` — toute ressource
    déclarée compatible pour cette tâche (`CompatibiliteRessourceTache`) doit
    la posséder (`Ressource.competences`), vérifié par `InstanceTRCO`. Une
    tâche exigeant plusieurs compétences est décrite par plusieurs
    contraintes de ce type (une par compétence), même granularité atomique
    que `CompatibiliteRessourceTache`.

    Ne remplace pas `CompatibiliteRessourceTache` (seule source de la durée
    par couple tâche-ressource) — ajoute un garde-fou structurel en plus :
    une compatibilité déclarée pour une ressource non qualifiée est rejetée
    à la construction de l'instance, pas laissée passer vers le solveur."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["competence_requise"] = "competence_requise"
    tache: Identifiant
    competence: str = Field(min_length=1)


class ContrainteCapacite(BaseModel):
    """La ressource `ressource` peut traiter jusqu'à `capacite` opérations
    simultanément — sans cette contrainte, une ressource a une capacité
    implicite de 1 (le comportement historique : jamais deux opérations en
    même temps, vérifié par `chevauchement_ressource` dans le vérificateur
    de faisabilité). Avec elle, jusqu'à `capacite` opérations peuvent se
    chevaucher sur cette ressource sans que ce soit une anomalie.

    Une ressource sans `ContrainteCapacite` déclarée n'est pas affectée —
    extension optionnelle, comme `Echeance`/`CompetenceRequise` (§4.2)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["capacite"] = "capacite"
    ressource: Identifiant
    capacite: int = Field(ge=1, description="Nombre d'opérations que cette ressource peut traiter simultanément")


class ContrainteIncompatibilite(BaseModel):
    """Les tâches `tache` et `tache_incompatible` ne peuvent jamais être
    affectées à la même ressource — quelle que soit l'heure, contrairement à
    `chevauchement_ressource` qui n'interdit qu'un chevauchement temporel.
    Relation symétrique (l'ordre des deux tâches n'a pas de sens métier),
    déclarée une seule fois par paire.

    Une tâche non citée dans une `ContrainteIncompatibilite` n'est affectée
    par aucune restriction de ce type — extension optionnelle, comme
    `Echeance`/`CompetenceRequise`/`ContrainteCapacite` (§4.2)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["incompatibilite"] = "incompatibilite"
    tache: Identifiant
    tache_incompatible: Identifiant

    @model_validator(mode="after")
    def _pas_d_autoreference(self) -> ContrainteIncompatibilite:
        if self.tache == self.tache_incompatible:
            raise ValueError("une tâche ne peut pas être incompatible avec elle-même")
        return self


class ContrainteDisponibiliteRessource(BaseModel):
    """La ressource `ressource` est indisponible durant les jours listés dans
    `jours_indisponibles` — aucune opération ne peut s'y dérouler un jour
    indisponible (même référentiel que `Echeance`/`duree` : jours relatifs,
    jamais une date calendaire — convertir un vrai calendrier/jours fériés
    en jours reste un problème d'adaptateur, en amont de l'ingestion).

    Un calendrier global d'atelier (ex. jours fériés communs) s'exprime en
    déclarant cette contrainte identiquement pour chaque ressource de
    l'instance — pas un mécanisme séparé.

    Une ressource sans cette contrainte n'est pas affectée — extension
    optionnelle, comme `Echeance`/`ContrainteCapacite` (§4.2)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["disponibilite_ressource"] = "disponibilite_ressource"
    ressource: Identifiant
    jours_indisponibles: list[int] = Field(
        min_length=1, description="Jours (relatifs) où cette ressource est indisponible"
    )


class ContrainteTailleLot(BaseModel):
    """La tâche `tache` doit produire une quantité (`Tache.quantite`) comprise entre
    `lot_min` et `lot_max` inclus — une validation statique de la donnée d'entrée,
    sans aucun effet sur les décisions d'ordonnancement du solveur (contrairement à
    `Echeance`, qui contraint le *moment* où la tâche se termine ; ici seule la
    *quantité* déclarée est bornée, jamais lue par le solveur ni un objectif).

    Si `Tache.quantite` n'est pas renseignée pour la tâche référencée, cette
    contrainte n'a rien à vérifier et ne produit aucune anomalie — extension
    optionnelle, comme `Echeance`/`ContrainteDisponibiliteRessource` (§4.2)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["taille_lot"] = "taille_lot"
    tache: Identifiant
    lot_min: int = Field(ge=1, description="Quantité minimale attendue pour cette tâche")
    lot_max: int = Field(ge=1, description="Quantité maximale attendue pour cette tâche")

    @model_validator(mode="after")
    def _lot_min_inferieur_ou_egal_lot_max(self) -> ContrainteTailleLot:
        if self.lot_min > self.lot_max:
            raise ValueError("lot_min doit être inférieur ou égal à lot_max")
        return self


Contrainte = Annotated[
    Precedence
    | CompatibiliteRessourceTache
    | Echeance
    | CompetenceRequise
    | ContrainteCapacite
    | ContrainteIncompatibilite
    | ContrainteDisponibiliteRessource
    | ContrainteTailleLot,
    Field(discriminator="type"),
]

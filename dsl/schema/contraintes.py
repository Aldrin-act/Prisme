"""C — Contraintes : précédence, compatibilité ressource-tâche, échéance,
compétence requise, capacité et incompatibilité (§3.1, §4). Les deux
premières forment le noyau minimal ; `Echeance`/`CompetenceRequise`/
`ContrainteCapacite`/`ContrainteIncompatibilite` sont des extensions
optionnelles (aucun effet sur une instance qui ne les utilise pas) — voir
`docs/dsl/modele_ingestion_client.md`.

Une contrainte est un objet discriminé par son champ `type`, pour rester
homogène et extensible : calendrier, etc. pourront encore s'ajouter à cette
union sans toucher aux contraintes existantes.
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


Contrainte = Annotated[
    Precedence
    | CompatibiliteRessourceTache
    | Echeance
    | CompetenceRequise
    | ContrainteCapacite
    | ContrainteIncompatibilite,
    Field(discriminator="type"),
]

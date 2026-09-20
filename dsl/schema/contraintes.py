"""C — Contraintes : précédence, compatibilité ressource-tâche, échéance,
compétence requise, capacité, incompatibilité, disponibilité ressource,
taille de lot, déclaration de matériau et consommation matière (§3.1, §4).
Les deux premières forment le noyau minimal ; les autres sont des extensions
optionnelles (aucun effet sur une instance qui ne les utilise pas) — voir
`docs/dsl/modele_ingestion_client.md`. `DeclarationMateriau`/`ConsommationMatiere`
forment ensemble le mécanisme matières/stock : contrairement à toutes les
autres contraintes ci-dessous (qui relient des entités déjà déclarées dans
`taches`/`ressources`), `DeclarationMateriau` déclare l'entité matériau
elle-même (id + stock) — il n'existe pas d'axe M séparé, un matériau n'est
connu de l'instance qu'à travers cette contrainte.

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
    """La ressource `ressource` est indisponible durant les instants listés dans
    `jours_indisponibles` et/ou durant chaque occurrence du motif récurrent
    `jours_semaine_indisponibles` — aucune opération ne peut s'y dérouler un
    instant indisponible (même référentiel que `Echeance`/`duree` : relatifs à
    `InstanceTRCO.unite_temps` — jours ou heures —, jamais une date calendaire —
    convertir un vrai calendrier/jours fériés reste un problème d'adaptateur,
    en amont de l'ingestion).

    `jours_semaine_indisponibles` exprime un motif qui se répète selon un cycle
    fixé par `InstanceTRCO.unite_temps` (7 en mode jours, 168 en mode heures) à
    partir de l'instant 0 de l'instance (`0` = position 0 du cycle, ..., la
    dernière position = fin du cycle) — pour un vrai "week-end" calendaire,
    c'est à l'adaptateur de savoir quel instant relatif de l'instance
    correspond à quel jour/heure réel, pas au DSL (toujours relatif, jamais
    une date). La borne haute du cycle dépend de `unite_temps` et n'est donc
    vérifiée qu'au niveau de `InstanceTRCO` (`_disponibilite_dans_le_cycle`),
    pas ici — cette contrainte, validée seule, ne garantit qu'une valeur
    positive. Les deux champs se combinent : une ressource peut avoir un motif
    récurrent (repos hebdomadaire) *et* des instants exceptionnels explicites
    (jours fériés), déclarés soit dans la même contrainte, soit dans deux
    contraintes distinctes pour la même ressource (elles s'additionnent,
    jamais un remplacement — même principe que plusieurs
    `CompatibiliteRessourceTache` pour la même tâche, §4.2).

    Un calendrier global d'atelier (ex. jours fériés/week-end communs)
    s'exprime en déclarant cette contrainte identiquement pour chaque
    ressource de l'instance — pas un mécanisme séparé.

    Une ressource sans cette contrainte n'est pas affectée — extension
    optionnelle, comme `Echeance`/`ContrainteCapacite` (§4.2)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["disponibilite_ressource"] = "disponibilite_ressource"
    ressource: Identifiant
    jours_indisponibles: list[int] = Field(
        default_factory=list, description="Jours (relatifs) où cette ressource est indisponible"
    )
    jours_semaine_indisponibles: list[int] | None = Field(
        default=None,
        description="Motif récurrent (cycle de 7 jours ou 168 heures selon InstanceTRCO."
        "unite_temps, depuis l'instant 0 de l'instance) : positions où cette ressource est "
        "indisponible à chaque occurrence du cycle.",
    )

    @model_validator(mode="after")
    def _au_moins_un_mode_de_disponibilite_declare(self) -> ContrainteDisponibiliteRessource:
        if not self.jours_indisponibles and not self.jours_semaine_indisponibles:
            raise ValueError(
                "jours_indisponibles ou jours_semaine_indisponibles doit être renseigné (au moins un jour)"
            )
        return self

    @model_validator(mode="after")
    def _jours_semaine_positifs(self) -> ContrainteDisponibiliteRessource:
        """Borne haute (dépendante de `InstanceTRCO.unite_temps` — 7 ou 168) volontairement
        absente ici : cette contrainte est validée seule, avant assemblage dans l'instance, donc
        ne peut pas connaître l'unité de temps déclarée — voir `InstanceTRCO._disponibilite_dans_le_cycle`."""
        if self.jours_semaine_indisponibles is not None:
            invalides = sorted({j for j in self.jours_semaine_indisponibles if j < 0})
            if invalides:
                raise ValueError(f"jours_semaine_indisponibles doit contenir des valeurs positives : {invalides}")
        return self


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


class ContrainteChangementSerie(BaseModel):
    """Sur la ressource `ressource`, faire suivre immédiatement la tâche `tache_avant` par la
    tâche `tache_apres` (aucune autre tâche intercalée sur cette même ressource) exige un temps
    de changement de série `duree_setup` — un délai supplémentaire entre la fin de `tache_avant`
    et le début de `tache_apres`, distinct de leurs durées propres
    (`CompatibiliteRessourceTache`). Modélise un changement d'outillage, un nettoyage entre
    lots, etc.

    Contrainte dirigée et propre à cette ressource : `tache_avant` → `tache_apres` uniquement
    dans ce sens — si l'ordre inverse a aussi un coût (pas forcément le même), déclarer une
    seconde contrainte symétrique avec sa propre durée.

    Sans effet si `tache_avant`/`tache_apres` ne se retrouvent jamais consécutives sur
    `ressource` dans le planning proposé : cette contrainte n'impose aucun ordre entre les deux
    (ça reste le rôle de `Precedence`) — seulement un coût *si* le solveur choisit de les
    enchaîner ainsi sur cette ressource. Une ressource/paire non citée n'est affectée par aucune
    contrainte de ce type — extension optionnelle, comme `Echeance`/`ContrainteCapacite` (§4.2)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["changement_serie"] = "changement_serie"
    ressource: Identifiant
    tache_avant: Identifiant
    tache_apres: Identifiant
    duree_setup: int = Field(
        gt=0,
        description="Délai (jours) entre la fin de tache_avant et le début de tache_apres sur cette ressource",
    )

    @model_validator(mode="after")
    def _pas_d_autoreference(self) -> ContrainteChangementSerie:
        if self.tache_avant == self.tache_apres:
            raise ValueError("une tâche ne peut pas nécessiter un changement de série vers elle-même")
        return self


class DeclarationMateriau(BaseModel):
    """Déclare un matériau (matière première/composant consommable) avec son stock de départ —
    la seule façon dont un `materiau` existe pour l'instance : contrairement à `Tache`/`Ressource`,
    il n'y a pas de liste top-level dédiée, cette contrainte *est* l'entité.

    Aucun réapprovisionnement dans ce v1 : `stock_initial` couvre tout l'horizon de planification.
    Une instance sans `DeclarationMateriau` n'est affectée par aucune vérification de stock —
    extension optionnelle, comme `Echeance`/`ContrainteCapacite` (§4.2)."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["declaration_materiau"] = "declaration_materiau"
    materiau: Identifiant
    stock_initial: float = Field(ge=0, description="Stock disponible au début de l'horizon de planification")
    unite: str | None = Field(
        default=None,
        description="Unité de mesure du stock/de la consommation (ex. kg, litres, unités) — "
        "optionnel, purement informatif : ni le solveur ni le vérificateur de faisabilité n'en "
        "dépendent.",
    )


class ConsommationMatiere(BaseModel):
    """La tâche `tache` consomme `quantite` unités du matériau `materiau` (déclaré par une
    `DeclarationMateriau` de la même instance) — prélevées sur son stock au moment où la tâche
    commence.

    Contrainte **dure** : le solveur ne doit jamais produire un planning où, à un instant
    donné, le cumul des consommations dépasse le stock disponible du matériau (vérifié par
    `validation_engine/feasibility_checker.py`, respecté côté solveur généré par un
    compteur de stock dans le décodeur — voir `generation/prompts/generation_solveur.md`).
    Aucune notion de réapprovisionnement dans ce v1 : `stock_initial` couvre tout l'horizon.

    Une tâche consommant plusieurs matériaux est décrite par plusieurs contraintes de ce
    type (une par matériau), même granularité atomique que `CompatibiliteRessourceTache`."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["consommation_matiere"] = "consommation_matiere"
    tache: Identifiant
    materiau: Identifiant
    quantite: float = Field(gt=0, description="Quantité de matériau prélevée par cette tâche")


Contrainte = Annotated[
    Precedence
    | CompatibiliteRessourceTache
    | Echeance
    | CompetenceRequise
    | ContrainteCapacite
    | ContrainteIncompatibilite
    | ContrainteDisponibiliteRessource
    | ContrainteTailleLot
    | ContrainteChangementSerie
    | DeclarationMateriau
    | ConsommationMatiere,
    Field(discriminator="type"),
]

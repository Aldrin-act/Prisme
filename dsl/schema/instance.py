"""Instance T-R-C-O complète : le payload canonique échangé avec les ERP (§4, §5.4).

Agrège les quatre axes et applique le garde-fou amont (§6.7) : identifiants
uniques par axe, toute contrainte ne référence que des tâches ou ressources
réellement déclarées dans l'instance, toute tâche est couverte par au moins
une contrainte `CompatibiliteRessourceTache` (la durée, désormais propre à
chaque couple tâche-ressource, n'existe que là — une tâche sans aucune
compatibilité déclarée n'aurait donc aucune durée connue), et toute
compatibilité déclarée pour une tâche ayant des `CompetenceRequise` porte sur
une ressource réellement qualifiée. Un payload qui échoue cette validation
est rejeté avant d'atteindre le solveur.

Cas particulier des matériaux (`DeclarationMateriau`/`ConsommationMatiere`,
`dsl/schema/contraintes.py`) : contrairement à `Tache`/`Ressource`, il n'y a pas
de liste top-level dédiée — un matériau n'existe pour l'instance qu'à travers sa
`DeclarationMateriau` (elle-même une `Contrainte`), donc son identifiant unique
et les références vers lui sont vérifiés ici en scannant `contraintes`, pas un
axe séparé.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contraintes import (
    CompatibiliteRessourceTache,
    CompetenceRequise,
    ConsommationMatiere,
    Contrainte,
    ContrainteCapacite,
    ContrainteChangementSerie,
    ContrainteDisponibiliteRessource,
    ContrainteIncompatibilite,
    ContrainteTailleLot,
    DeclarationMateriau,
    Echeance,
    Precedence,
)
from .objectifs import Objectif
from .ressources import Ressource
from .taches import Tache


class InstanceTRCO(BaseModel):
    """Un payload T-R-C-O : une instance complète à planifier."""

    model_config = ConfigDict(extra="forbid")

    taches: list[Tache] = Field(min_length=1)
    ressources: list[Ressource] = Field(min_length=1)
    contraintes: list[Contrainte] = Field(default_factory=list)
    objectifs: list[Objectif] = Field(min_length=1)
    # Unité de temps des entiers `duree`/`echeance`/`debut`/`duree_setup` portés par cette
    # instance — "jours" par défaut (toute instance/solveur existant reste inchangé). Affecte la
    # longueur du cycle hebdomadaire de `ContrainteDisponibiliteRessource.jours_semaine_
    # indisponibles` (7 en jours, 168 en heures, voir `_disponibilite_dans_le_cycle` ci-dessous)
    # et l'affichage frontend (`api/unite_duree.py`) — jamais interprété par le reste du DSL/le
    # solveur généré, qui restent des entiers génériques quelle que soit l'unité déclarée.
    unite_temps: Literal["jours", "heures"] = "jours"
    # Jours de la semaine fermés par défaut, consommés uniquement par la correction post-solveur
    # (`validation_engine/jours_non_ouvres.py`, appelée depuis `sandbox/runner.py` juste avant le
    # garde-fou de faisabilité) — jamais lu par le solveur généré ni par `feasibility_checker.py`.
    # Convention JS `Date.getDay()` (0=dimanche..6=samedi), pas celle de Python `date.weekday()`
    # (0=lundi..6=dimanche) : choisie pour rester cohérente avec le formulaire d'ingestion
    # (`ingestion-dialog.tsx`, `NOMS_JOURS_SEMAINE_COURTS`) qui la déclare. Par défaut samedi+
    # dimanche (`[0, 6]`) — un champ d'instance ordinaire, jamais une `Contrainte` : ne change
    # jamais `structure_contraintes`, donc ne peut jamais invalider un solveur déjà enregistré.
    jours_fermes: list[int] = Field(default_factory=lambda: [0, 6])

    @model_validator(mode="after")
    def _jours_fermes_valides(self) -> InstanceTRCO:
        invalides = sorted({j for j in self.jours_fermes if not (0 <= j <= 6)})
        if invalides:
            raise ValueError(f"jours_fermes doit contenir des valeurs entre 0 (dimanche) et 6 (samedi) : {invalides}")
        return self

    @model_validator(mode="after")
    def _identifiants_uniques_par_axe(self) -> InstanceTRCO:
        ids_taches = [t.id for t in self.taches]
        if len(ids_taches) != len(set(ids_taches)):
            raise ValueError("identifiants de tâches dupliqués")

        ids_ressources = [r.id for r in self.ressources]
        if len(ids_ressources) != len(set(ids_ressources)):
            raise ValueError("identifiants de ressources dupliqués")

        return self

    @model_validator(mode="after")
    def _contraintes_referencent_des_entites_declarees(self) -> InstanceTRCO:
        ids_taches = {t.id for t in self.taches}
        ids_ressources = {r.id for r in self.ressources}

        # Les matériaux n'ont pas de liste top-level dédiée (contrairement à taches/ressources) :
        # un matériau n'existe pour l'instance qu'à travers sa DeclarationMateriau, elle-même une
        # Contrainte — l'unicité de ses identifiants se vérifie donc ici, pas dans
        # `_identifiants_uniques_par_axe` ci-dessus.
        ids_materiaux_declares = [c.materiau for c in self.contraintes if isinstance(c, DeclarationMateriau)]
        if len(ids_materiaux_declares) != len(set(ids_materiaux_declares)):
            raise ValueError("identifiants de matériaux dupliqués")
        ids_materiaux = set(ids_materiaux_declares)

        for contrainte in self.contraintes:
            if isinstance(contrainte, Precedence):
                for id_tache in (contrainte.avant, contrainte.apres):
                    if id_tache not in ids_taches:
                        raise ValueError(f"précédence référence une tâche inconnue : {id_tache!r}")
            elif isinstance(contrainte, CompatibiliteRessourceTache):
                if contrainte.tache not in ids_taches:
                    raise ValueError(f"compatibilité référence une tâche inconnue : {contrainte.tache!r}")
                if contrainte.ressource not in ids_ressources:
                    raise ValueError(f"compatibilité référence une ressource inconnue : {contrainte.ressource!r}")
            elif isinstance(contrainte, Echeance):
                if contrainte.tache not in ids_taches:
                    raise ValueError(f"échéance référence une tâche inconnue : {contrainte.tache!r}")
            elif isinstance(contrainte, CompetenceRequise):
                if contrainte.tache not in ids_taches:
                    raise ValueError(f"compétence requise référence une tâche inconnue : {contrainte.tache!r}")
            elif isinstance(contrainte, ContrainteCapacite):
                if contrainte.ressource not in ids_ressources:
                    raise ValueError(f"capacité référence une ressource inconnue : {contrainte.ressource!r}")
            elif isinstance(contrainte, ContrainteIncompatibilite):
                for id_tache in (contrainte.tache, contrainte.tache_incompatible):
                    if id_tache not in ids_taches:
                        raise ValueError(f"incompatibilité référence une tâche inconnue : {id_tache!r}")
            elif isinstance(contrainte, ContrainteDisponibiliteRessource):
                if contrainte.ressource not in ids_ressources:
                    raise ValueError(f"disponibilité référence une ressource inconnue : {contrainte.ressource!r}")
            elif isinstance(contrainte, ContrainteTailleLot):
                if contrainte.tache not in ids_taches:
                    raise ValueError(f"taille de lot référence une tâche inconnue : {contrainte.tache!r}")
            elif isinstance(contrainte, ContrainteChangementSerie):
                if contrainte.ressource not in ids_ressources:
                    raise ValueError(
                        f"changement de série référence une ressource inconnue : {contrainte.ressource!r}"
                    )
                for id_tache in (contrainte.tache_avant, contrainte.tache_apres):
                    if id_tache not in ids_taches:
                        raise ValueError(f"changement de série référence une tâche inconnue : {id_tache!r}")
            elif isinstance(contrainte, ConsommationMatiere):
                if contrainte.tache not in ids_taches:
                    raise ValueError(f"consommation de matière référence une tâche inconnue : {contrainte.tache!r}")
                if contrainte.materiau not in ids_materiaux:
                    raise ValueError(
                        f"consommation de matière référence un matériau inconnu : {contrainte.materiau!r}"
                    )

        return self

    @model_validator(mode="after")
    def _disponibilite_dans_le_cycle(self) -> InstanceTRCO:
        """`ContrainteDisponibiliteRessource` est validée seule (avant assemblage dans
        l'instance) et ne peut donc pas connaître `unite_temps` — elle ne borne que `>= 0`. La
        vraie borne haute du cycle hebdomadaire (7 jours ou 168 heures) ne peut être vérifiée
        qu'ici, une fois `unite_temps` connu."""
        longueur_cycle = 7 if self.unite_temps == "jours" else 168
        for contrainte in self.contraintes:
            if not isinstance(contrainte, ContrainteDisponibiliteRessource):
                continue
            if contrainte.jours_semaine_indisponibles is None:
                continue
            invalides = sorted({j for j in contrainte.jours_semaine_indisponibles if j >= longueur_cycle})
            if invalides:
                raise ValueError(
                    f"jours_semaine_indisponibles de {contrainte.ressource!r} doit contenir des "
                    f"valeurs entre 0 et {longueur_cycle - 1} (cycle de {longueur_cycle} en mode "
                    f"{self.unite_temps!r}) : {invalides}"
                )
        return self

    @model_validator(mode="after")
    def _chaque_tache_a_au_moins_une_ressource_compatible(self) -> InstanceTRCO:
        ids_avec_compatibilite = {c.tache for c in self.contraintes if isinstance(c, CompatibiliteRessourceTache)}
        ids_sans_compatibilite = sorted(t.id for t in self.taches if t.id not in ids_avec_compatibilite)
        if ids_sans_compatibilite:
            raise ValueError(
                f"tâche(s) sans aucune contrainte de compatibilité ressource-tâche déclarée : "
                f"{ids_sans_compatibilite!r}"
            )
        return self

    @model_validator(mode="after")
    def _competences_requises_respectees(self) -> InstanceTRCO:
        """Si une tâche a des `CompetenceRequise`, toute `CompatibiliteRessourceTache`
        déclarée pour elle doit référencer une ressource dont `competences` couvre
        ces exigences — sans effet si aucune `CompetenceRequise` n'est déclarée."""
        competences_requises_par_tache: dict[str, set[str]] = defaultdict(set)
        for contrainte in self.contraintes:
            if isinstance(contrainte, CompetenceRequise):
                competences_requises_par_tache[contrainte.tache].add(contrainte.competence)

        if not competences_requises_par_tache:
            return self

        competences_par_ressource = {r.id: set(r.competences) for r in self.ressources}

        for contrainte in self.contraintes:
            if not isinstance(contrainte, CompatibiliteRessourceTache):
                continue
            requises = competences_requises_par_tache.get(contrainte.tache)
            if not requises:
                continue
            manquantes = requises - competences_par_ressource.get(contrainte.ressource, set())
            if manquantes:
                raise ValueError(
                    f"compatibilité déclarée entre {contrainte.tache!r} et {contrainte.ressource!r} "
                    f"sans les compétences requises : {sorted(manquantes)!r}"
                )

        return self

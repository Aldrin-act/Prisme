"""json_import — Adaptateur pour l'ingestion T-R-C-O via un JSON « brut avec
compétences » (§5.4) : la version JSON de `adapters/csv_import/` — mêmes
principes, mêmes noms de champs DSL, seule différence de forme (un seul
payload structuré plutôt que trois fichiers).

Plutôt que de déclarer chaque `compatibilite_ressource_tache` à la main, une
ressource porte des compétences (`Ressource.competences`, déjà un champ réel
du DSL) et une tâche les exige (`CompetenceRequise`, déjà un type de
contrainte réel du DSL) — la seule différence avec une instance T-R-C-O
canonique est que chaque tâche peut porter ici une durée estimée
(`duree_estimee_jours`), absente du DSL lui-même (`Tache` n'a
délibérément aucun champ de durée, §4.2 — elle dépend de la ressource en
vrai FJSP flexible) mais nécessaire pour dériver une compatibilité. La
dérivation elle-même est partagée avec `adapters/csv_import/`, voir
`adapters/competence_derivation.py`.

Un payload sans aucune `CompetenceRequise` ni `duree_estimee_jours` est une
instance T-R-C-O tout à fait ordinaire, ingérée sans transformation — cet
adaptateur est un sur-ensemble strict du format canonique, jamais un format
concurrent : le remplace donc sans rien casser pour qui l'utilisait déjà tel quel.

Commandes (`adapters/commande_derivation.py`) : un champ optionnel `commandes` relie des tâches
à une commande cliente et une date limite — pure métadonnée de traçabilité d'ingestion, dérive
une `Echeance` par tâche liée (sauf si déjà explicite pour cette tâche), le solveur ne voit
jamais la notion de "commande" elle-même (§5.3, vocabulaire DSL fini).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from adapters.commande_derivation import Commande, deriver_echeances_par_commande
from adapters.competence_derivation import (
    CompetenceSansDureeEstimee,
    ResultatTraduction,
    completer_durees_par_estimation,
    deriver_compatibilites_par_competence,
)
from dsl.schema import Contrainte, InstanceTRCO, MinimiserMakespan, Objectif, Ressource, Tache

if TYPE_CHECKING:
    from estimation import EstimateurDuree


class ErreurPayloadInvalide(Exception):
    """Payload structurellement invalide (champ manquant, type incorrect) ou
    durée estimée manquante pour une dérivation par compétence — distinct
    d'une instance lue mais invalide au sens du DSL final (ça, c'est une
    ValidationError Pydantic, même garde-fou que les autres canaux)."""


class TacheAvecDureeEstimee(Tache):
    """`Tache` (mêmes champs, mêmes contraintes) plus une durée estimée
    optionnelle, seulement nécessaire si cette tâche exige une compétence
    (`CompetenceRequise`) sans compatibilité explicite déjà déclarée."""

    duree_estimee_jours: int | None = Field(default=None, gt=0)


class CommandeBrute(BaseModel):
    """Une commande cliente, telle qu'acceptée par ce payload — voir
    `adapters/commande_derivation.py::Commande` pour la sémantique complète."""

    model_config = ConfigDict(extra="forbid")

    id: str
    taches: list[str] = Field(min_length=1)
    client: str | None = None
    date_limite: int | None = Field(default=None, ge=0)


class InstanceBrute(BaseModel):
    """Format accepté par cet adaptateur — un sur-ensemble de `InstanceTRCO` :
    mêmes `ressources`/`contraintes`/`objectifs`, mais `taches` peut porter
    une durée estimée par tâche, et `commandes` (optionnel) relie des tâches
    à une commande cliente pour en dériver des `Echeance`."""

    model_config = ConfigDict(extra="forbid")

    taches: list[TacheAvecDureeEstimee]
    ressources: list[Ressource]
    contraintes: list[Contrainte] = Field(default_factory=list)
    objectifs: list[Objectif] = Field(default_factory=lambda: [MinimiserMakespan()])
    commandes: list[CommandeBrute] = Field(default_factory=list)


def traduire(payload: dict[str, Any], estimateur_duree: EstimateurDuree | None = None) -> ResultatTraduction:
    """Traduit un payload JSON « brut avec compétences » en instance T-R-C-O.
    Lève `ErreurPayloadInvalide` si la structure ne correspond pas au format
    attendu (y compris une durée estimée manquante pour une dérivation, si
    `estimateur_duree` n'est pas fourni ou ne peut rien estimer) ;
    `pydantic.ValidationError` si l'instance finale, compatibilités dérivées
    comprises, reste invalide au sens du DSL (id dupliqué, référence
    inconnue, tâche sans compatibilité...).

    `estimateur_duree` (optionnel, `estimation.EstimateurDuree`) comble, via apprentissage
    automatique (`estimation/`), la durée des tâches à compétence requise qui n'en ont
    aucune de connue — jamais silencieusement : chaque durée ainsi comblée ajoute un
    avertissement au `ResultatTraduction` renvoyé (§FC4, décision humaine préservée)."""
    try:
        brute = InstanceBrute.model_validate(payload)
    except ValidationError as erreur:
        raise ErreurPayloadInvalide(str(erreur)) from erreur

    taches = [
        Tache(id=t.id, nom=t.nom, priorite=t.priorite, statut=t.statut, quantite=t.quantite, produit=t.produit)
        for t in brute.taches
    ]
    durees_estimees = {t.id: t.duree_estimee_jours for t in brute.taches if t.duree_estimee_jours is not None}

    avertissements: list[str] = []
    if estimateur_duree is not None:
        durees_estimees, avertissements = completer_durees_par_estimation(
            brute.contraintes, brute.ressources, taches, durees_estimees, estimateur_duree
        )

    try:
        compatibilites_derivees = deriver_compatibilites_par_competence(
            brute.contraintes, brute.ressources, durees_estimees
        )
    except CompetenceSansDureeEstimee as erreur:
        raise ErreurPayloadInvalide(f"{erreur} (champ taches[].duree_estimee_jours)") from erreur

    commandes = [
        Commande(id=c.id, taches=tuple(c.taches), client=c.client, date_limite=c.date_limite)
        for c in brute.commandes
    ]
    echeances_derivees = deriver_echeances_par_commande(commandes, brute.contraintes)

    instance = InstanceTRCO(
        taches=taches,
        ressources=brute.ressources,
        contraintes=[*brute.contraintes, *compatibilites_derivees, *echeances_derivees],
        objectifs=brute.objectifs,
    )
    return ResultatTraduction(instance=instance, avertissements=tuple(avertissements))

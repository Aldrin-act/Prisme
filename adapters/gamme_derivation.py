"""Explosion d'une gamme réutilisable (`api.etat.GammeProduit`) en tâches DSL concrètes à
l'arrivée d'une commande — couche d'ingestion, jamais un axe T-R-C-O (même statut que
`adapters/commande_derivation.py::Commande`, réutilisé ici tel quel, jamais modifié).

Une gamme décrit un gabarit d'étapes (compétences requises, ordre via prédécesseurs) une fois par
produit ; l'explosion instancie ce gabarit en `Tache`/`Precedence`/`CompetenceRequise` fraîches,
préfixées par un identifiant de commande pour rester uniques dans l'instance cible, puis laisse les
briques de dérivation déjà existantes (`competence_derivation.py`, `commande_derivation.py`)
calculer compatibilités et échéance — exactement la même séquence que `traduire()`
(`adapters/csv_import/traducteur.py`, `adapters/json_import/traducteur.py`), jamais dupliquée ici.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from adapters.commande_derivation import Commande, deriver_echeances_par_commande
from adapters.competence_derivation import (
    ResultatTraduction,
    completer_durees_par_estimation,
    deriver_compatibilites_par_competence,
)
from api.etat import GammeProduit
from dsl.schema import CompetenceRequise, Contrainte, InstanceTRCO, Precedence, Tache

if TYPE_CHECKING:
    from estimation import EstimateurDuree


class ErreurExplosionGamme(Exception):
    """L'explosion d'une gamme produirait un id de tâche invalide, dupliqué au sein de la gamme
    elle-même, ou déjà présent dans l'instance cible — jamais un écrasement silencieux d'une tâche
    existante. La validation du motif `Identifiant` est déjà faite côté éditeur visuel de gammes
    à la création, mais revérifiée ici (garde-fou en profondeur, même principe que §6.7)."""


def exploser_gamme(
    commande_id: str, quantite: int | None, gamme: GammeProduit, ids_taches_existantes: set[str]
) -> tuple[list[Tache], list[Contrainte]]:
    """Instancie chaque étape de `gamme` en une `Tache` fraîche (id `f"{commande_id}_{etape.id}"`,
    `produit=gamme.produit`) plus une `CompetenceRequise` par compétence exigée et une
    `Precedence` par prédécesseur déclaré — plusieurs prédécesseurs pour une même étape expriment
    une fusion (plusieurs sous-produits qui convergent vers une étape commune), sans mécanisme
    dédié. `ids_taches_existantes` — les ids déjà présents dans l'instance cible — pour refuser
    toute collision plutôt que d'écraser une tâche en silence."""
    ids_locaux = {etape.id for etape in gamme.etapes}
    taches: list[Tache] = []
    contraintes: list[Contrainte] = []

    for etape in gamme.etapes:
        tache_id = f"{commande_id}_{etape.id}"
        try:
            tache = Tache(id=tache_id, produit=gamme.produit, quantite=quantite)
        except ValidationError as erreur:
            raise ErreurExplosionGamme(
                f"id de tâche invalide généré pour l'étape {etape.id!r} : {tache_id!r}"
            ) from erreur
        if tache_id in ids_taches_existantes:
            raise ErreurExplosionGamme(f"la tâche {tache_id!r} existe déjà dans l'instance cible")
        taches.append(tache)

        for competence in etape.competences:
            contraintes.append(CompetenceRequise(tache=tache_id, competence=competence))
        for predecesseur_id in etape.predecesseurs:
            if predecesseur_id not in ids_locaux:
                raise ErreurExplosionGamme(
                    f"l'étape {etape.id!r} référence un prédécesseur inconnu de cette gamme : {predecesseur_id!r}"
                )
            contraintes.append(Precedence(avant=f"{commande_id}_{predecesseur_id}", apres=tache_id))

    return taches, contraintes


def traiter_nouvelle_commande(
    instance: InstanceTRCO,
    gamme: GammeProduit,
    commande_id: str,
    quantite: int | None,
    date_limite: int | None,
    estimateur_duree: EstimateurDuree | None = None,
) -> ResultatTraduction:
    """Fusionne une nouvelle commande (produit + quantité + échéance, résolus via `gamme`) dans
    `instance` — même séquence de dérivation que `traduire()` des adaptateurs CSV/JSON, réutilisée
    sans modification : explosion de la gamme, puis (si un estimateur est fourni) estimation des
    durées manquantes, puis dérivation des compatibilités par compétence, puis dérivation de
    l'échéance depuis la commande (`Commande` construit ici dynamiquement, jamais reçu d'un
    payload — même type que `commande_derivation.py`, inchangé). `instance` n'est jamais mutée :
    le résultat est une instance neuve, à faire persister par l'appelant
    (`EtatAPI.modifier_instance`) — aucune primitive de fusion n'existe ni n'est nécessaire côté
    état, cette fonction *est* la fusion."""
    ids_existants = {t.id for t in instance.taches}
    nouvelles_taches, nouvelles_contraintes = exploser_gamme(commande_id, quantite, gamme, ids_existants)

    taches = [*instance.taches, *nouvelles_taches]
    contraintes = [*instance.contraintes, *nouvelles_contraintes]

    # Durée déclarée par étape (`EtapeGamme.duree_nominale`) — source primaire, même
    # préséance que `TacheAvecDureeEstimee.duree_estimee_jours` des adaptateurs CSV/JSON :
    # l'estimateur ML ne comble que ce qui reste manquant après elle.
    durees_connues: dict[str, int] = {
        f"{commande_id}_{etape.id}": etape.duree_nominale
        for etape in gamme.etapes
        if etape.duree_nominale is not None
    }
    avertissements: list[str] = []
    if estimateur_duree is not None:
        durees_connues, avertissements = completer_durees_par_estimation(
            contraintes, instance.ressources, taches, durees_connues, estimateur_duree
        )

    compatibilites_derivees = deriver_compatibilites_par_competence(
        contraintes, instance.ressources, durees_connues
    )

    commande = Commande(
        id=commande_id,
        taches=tuple(t.id for t in nouvelles_taches),
        client=gamme.client_id,
        date_limite=date_limite,
    )
    echeances_derivees = deriver_echeances_par_commande([commande], contraintes)

    instance_fusionnee = InstanceTRCO(
        taches=taches,
        ressources=instance.ressources,
        contraintes=[*contraintes, *compatibilites_derivees, *echeances_derivees],
        objectifs=instance.objectifs,
    )
    return ResultatTraduction(instance_fusionnee, tuple(avertissements))

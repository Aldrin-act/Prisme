"""Point d'entrée unique de l'agent de supervision (§2, MT7) — la seule
implémentation de « détecter (LLM) + dédupliquer + rédiger (LLM) + persister », appelée à la
fois par la route manuelle (`POST /supervision/analyser`) et par la boucle
périodique (`supervision/planificateur.py`) : jamais deux implémentations de
ce cycle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from api.etat import ActionSuggeree, EtatAPI, PropositionSupervision, TypeSignal
from solver_store.registry import Registre
from supervision.agent import FaitSignal, proposer_actions
from supervision.detecteurs import (
    SignalCommandeEnRetard,
    SignalDetecte,
    SignalEchecsRepetes,
    SignalInstanceAReplanifier,
    SignalSignatureOrpheline,
    detecter_commandes_en_retard,
    detecter_signaux,
)

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

_ACTION_PAR_SIGNAL: dict[TypeSignal, ActionSuggeree] = {
    "signature_orpheline": "regenerer_solveur",
    "instance_a_replanifier": "executer",
    "echecs_repetes": "diagnostiquer",
    # Aucune route système ne rattrape un retard déjà constaté par le planning actuel — purement
    # informatif, voir supervision/detecteurs.py::detecter_commandes_en_retard.
    "commande_en_retard": "aucune",
}

_RESUME_REPLI: dict[TypeSignal, str] = {
    "signature_orpheline": (
        "Aucun solveur actif ne correspond à la structure actuelle de cette instance — "
        "une régénération est nécessaire avant toute exécution."
    ),
    "instance_a_replanifier": (
        "Un solveur compatible existe déjà mais cette instance n'a jamais été exécutée, ou a été "
        "modifiée depuis sa dernière exécution — une exécution permettrait d'obtenir un planning à jour."
    ),
    "echecs_repetes": (
        "Plusieurs exécutions récentes de cette instance ont échoué — "
        "un diagnostic permettrait d'en identifier la cause."
    ),
    "commande_en_retard": (
        "Cette commande finira après sa date limite d'après le planning actuel de son instance — "
        "à traiter côté client/planification, aucune action système ne peut rattraper ce retard."
    ),
}

_PRIORITE_REPLI: Literal["moyenne"] = "moyenne"


@dataclass(frozen=True)
class _SignalUnifie:
    type_signal: TypeSignal
    instance_id: str
    structure_contraintes: str
    signature_objectifs: str
    execution_ids: tuple[str, ...]
    details: tuple[str, ...]
    description: str
    # Uniquement pour commande_en_retard — distingue plusieurs commandes en retard sur une même
    # instance, qui sans ça partageraient la même référence/le même dédoublonnage.
    commande_id: str | None = None

    @property
    def identifiant_reference(self) -> str:
        return self.commande_id if self.commande_id is not None else self.instance_id


def _reference(type_signal: TypeSignal, identifiant: str) -> str:
    return f"{type_signal}:{identifiant}"


def _unifier_signature_orpheline(signal: SignalSignatureOrpheline) -> _SignalUnifie:
    return _SignalUnifie(
        type_signal="signature_orpheline",
        instance_id=signal.instance_id,
        structure_contraintes=signal.structure_contraintes,
        signature_objectifs=signal.signature_objectifs,
        execution_ids=(),
        details=(f"structure={signal.structure_contraintes!r}", f"objectifs={signal.signature_objectifs!r}"),
        description=(
            f"Aucun solveur actif ne correspond à la signature actuelle de cette instance "
            f"(contraintes : {signal.structure_contraintes} ; objectifs : {signal.signature_objectifs})."
        ),
    )


def _unifier_instance_a_replanifier(signal: SignalInstanceAReplanifier) -> _SignalUnifie:
    if signal.raison == "jamais_executee":
        raison_texte = "mais elle n'a jamais été exécutée"
    else:
        raison_texte = (
            "mais elle a été modifiée depuis sa dernière exécution — le planning actuel ne "
            "reflète plus son contenu"
        )
    return _SignalUnifie(
        type_signal="instance_a_replanifier",
        instance_id=signal.instance_id,
        structure_contraintes=signal.structure_contraintes,
        signature_objectifs=signal.signature_objectifs,
        execution_ids=(),
        details=(f"solveur_disponible={signal.id_solveur_disponible}", f"raison={signal.raison}"),
        description=(
            f"Solveur {signal.id_solveur_disponible} disponible et compatible avec cette instance, {raison_texte}."
        ),
    )


def _unifier_echecs_repetes(signal: SignalEchecsRepetes) -> _SignalUnifie:
    return _SignalUnifie(
        type_signal="echecs_repetes",
        instance_id=signal.instance_id,
        structure_contraintes=signal.structure_contraintes,
        signature_objectifs=signal.signature_objectifs,
        execution_ids=signal.execution_ids,
        details=(f"solveur={signal.id_solveur}", f"executions_en_echec={len(signal.execution_ids)}"),
        description=(
            f"Les {len(signal.execution_ids)} dernières exécutions de cette instance "
            f"(solveur {signal.id_solveur}) ont toutes échoué."
        ),
    )


def _unifier_commande_en_retard(signal: SignalCommandeEnRetard) -> _SignalUnifie:
    return _SignalUnifie(
        type_signal="commande_en_retard",
        instance_id=signal.instance_id,
        # Structure/objectifs non pertinents pour ce signal (pas une question de compatibilité
        # solveur/instance) — vides plutôt qu'un placeholder trompeur.
        structure_contraintes="",
        signature_objectifs="",
        execution_ids=(),
        details=(f"date_fin_prevue={signal.date_fin_prevue}", f"date_limite={signal.date_limite}"),
        description=(
            f"La commande {signal.commande_id} finira au jour {signal.date_fin_prevue} d'après le "
            f"planning actuel de son instance, après sa date limite ({signal.date_limite})."
        ),
        commande_id=signal.commande_id,
    )


def _unifier(signal: SignalDetecte) -> _SignalUnifie:
    if isinstance(signal, SignalSignatureOrpheline):
        return _unifier_signature_orpheline(signal)
    if isinstance(signal, SignalInstanceAReplanifier):
        return _unifier_instance_a_replanifier(signal)
    if isinstance(signal, SignalCommandeEnRetard):
        return _unifier_commande_en_retard(signal)
    return _unifier_echecs_repetes(signal)


def analyser_et_proposer(
    etat: EtatAPI, registre: Registre, modele: BaseChatModel, client_id: str
) -> list[PropositionSupervision]:
    """Détecte les signaux — un appel LLM pour les trois signaux solveur/instance/exécution
    (`supervision.detecteurs.detecter_signaux`, ne peut plus être évité même si rien de nouveau ne
    sera finalement proposé : c'est justement ce que la détection sert à établir), plus une
    détection déterministe sans LLM pour les commandes en retard
    (`detecter_commandes_en_retard`) — écarte ceux déjà couverts par une proposition en attente,
    fait rédiger/prioriser le reste par un second appel LLM (`proposer_actions`, un seul appel
    jamais un par signal), puis persiste. Ce second appel reste évité quand tout ce qui a été
    détecté était déjà en attente."""
    signaux = [_unifier(s) for s in detecter_signaux(etat, registre, modele, client_id)]
    signaux += [_unifier(s) for s in detecter_commandes_en_retard(etat, client_id)]

    # `commande_id` fait partie de la clé : sans lui, une seule commande en retard sur une
    # instance couvrirait indéfiniment toutes les *autres* commandes en retard de la même
    # instance (jamais reproposées) — `None` pour les trois autres signaux, sans effet sur leur
    # comportement (toujours dédupliqués par (type_signal, instance_id) seuls).
    deja_en_attente = {
        (p["type_signal"], p["instance_id"], p.get("commande_id"))
        for p in etat.lister_propositions(client_id=client_id, en_attente_seulement=True)
    }
    nouveaux = [s for s in signaux if (s.type_signal, s.instance_id, s.commande_id) not in deja_en_attente]
    if not nouveaux:
        return []

    faits = tuple(
        FaitSignal(reference=_reference(s.type_signal, s.identifiant_reference), description=s.description)
        for s in nouveaux
    )
    resultat = proposer_actions(modele, faits)
    propositions_llm = {p.reference: p for p in resultat.propositions}

    proposition_ids: list[str] = []
    for signal in nouveaux:
        reference = _reference(signal.type_signal, signal.identifiant_reference)
        proposition_llm = propositions_llm.get(reference)
        # Le signal déjà détecté et validé (`detecter_signaux`) fait foi — si l'appel LLM de
        # rédaction a ignoré ou déformé cette référence, on ne le perd jamais, on retombe sur un
        # résumé canné plutôt que de le laisser passer silencieusement.
        resume = proposition_llm.resume if proposition_llm is not None else _RESUME_REPLI[signal.type_signal]
        priorite = proposition_llm.priorite if proposition_llm is not None else _PRIORITE_REPLI

        proposition_id = etat.enregistrer_proposition(
            client_id=client_id,
            type_signal=signal.type_signal,
            action_suggeree=_ACTION_PAR_SIGNAL[signal.type_signal],
            resume=resume,
            priorite=priorite,
            details=signal.details,
            instance_id=signal.instance_id,
            execution_ids=signal.execution_ids,
            structure_contraintes=signal.structure_contraintes,
            signature_objectifs=signal.signature_objectifs,
            commande_id=signal.commande_id,
        )
        proposition_ids.append(proposition_id)

    return [etat.recuperer_proposition(pid) for pid in proposition_ids]

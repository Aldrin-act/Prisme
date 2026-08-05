"""Point d'entrée unique de l'agent de supervision (§2, MT7) — la seule
implémentation de « détecter + dédupliquer + LLM + persister », appelée à la
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
    SignalEchecsRepetes,
    SignalInstanceAReplanifier,
    SignalSignatureOrpheline,
    detecter_echecs_repetes,
    detecter_signature_et_replanification,
)

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

_ACTION_PAR_SIGNAL: dict[TypeSignal, ActionSuggeree] = {
    "signature_orpheline": "regenerer_solveur",
    "instance_a_replanifier": "executer",
    "echecs_repetes": "diagnostiquer",
}

_RESUME_REPLI: dict[TypeSignal, str] = {
    "signature_orpheline": (
        "Aucun solveur actif ne correspond à la structure actuelle de cette instance — "
        "une régénération est nécessaire avant toute exécution."
    ),
    "instance_a_replanifier": (
        "Un solveur compatible existe déjà mais cette instance n'a pas encore été exécutée — "
        "une exécution permettrait d'obtenir un planning à jour."
    ),
    "echecs_repetes": (
        "Plusieurs exécutions récentes de cette instance ont échoué — "
        "un diagnostic permettrait d'en identifier la cause."
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


def _reference(type_signal: TypeSignal, instance_id: str) -> str:
    return f"{type_signal}:{instance_id}"


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
    return _SignalUnifie(
        type_signal="instance_a_replanifier",
        instance_id=signal.instance_id,
        structure_contraintes=signal.structure_contraintes,
        signature_objectifs=signal.signature_objectifs,
        execution_ids=(),
        details=(f"solveur_disponible={signal.id_solveur_disponible}",),
        description=(
            f"Solveur {signal.id_solveur_disponible} disponible et compatible avec cette instance, "
            "mais elle n'a jamais été exécutée."
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


def analyser_et_proposer(
    etat: EtatAPI, registre: Registre, modele: BaseChatModel, client_id: str
) -> list[PropositionSupervision]:
    """Détecte les 3 signaux, écarte ceux déjà couverts par une proposition
    en attente, fait rédiger/prioriser le reste par l'agent LLM (un seul
    appel, jamais un par signal), puis persiste. Retourne `[]` sans jamais
    appeler le LLM si rien de nouveau n'est détecté."""
    orphelines, a_replanifier = detecter_signature_et_replanification(etat, registre, client_id)
    echecs = detecter_echecs_repetes(etat, client_id)

    signaux = [
        *(_unifier_signature_orpheline(s) for s in orphelines),
        *(_unifier_instance_a_replanifier(s) for s in a_replanifier),
        *(_unifier_echecs_repetes(s) for s in echecs),
    ]

    deja_en_attente = {
        (p["type_signal"], p["instance_id"])
        for p in etat.lister_propositions(client_id=client_id, en_attente_seulement=True)
    }
    nouveaux = [s for s in signaux if (s.type_signal, s.instance_id) not in deja_en_attente]
    if not nouveaux:
        return []

    faits = tuple(
        FaitSignal(reference=_reference(s.type_signal, s.instance_id), description=s.description) for s in nouveaux
    )
    resultat = proposer_actions(modele, faits)
    propositions_llm = {p.reference: p for p in resultat.propositions}

    proposition_ids: list[str] = []
    for signal in nouveaux:
        reference = _reference(signal.type_signal, signal.instance_id)
        proposition_llm = propositions_llm.get(reference)
        # Le détecteur Python fait foi — si le LLM a ignoré ou déformé cette
        # référence, on ne perd jamais le signal détecté, on retombe sur un
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
        )
        proposition_ids.append(proposition_id)

    return [etat.recuperer_proposition(pid) for pid in proposition_ids]

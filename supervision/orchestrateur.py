"""Point d'entrée unique de l'agent de supervision (§2, MT7) — la seule
implémentation de « détecter (LLM) + dédupliquer + rédiger (LLM) + persister », appelée à la
fois par la route manuelle (`POST /supervision/analyser`) et par la boucle
périodique (`supervision/planificateur.py`) : jamais deux implémentations de
ce cycle.

Le cycle travaille **atelier par atelier** (`analyser_instance`) : chaque instance a sa propre
détection, sa propre rédaction et ses propres propositions, sans jamais voir les données d'un
autre atelier. `analyser_et_proposer` (niveau client) n'est qu'une boucle sur ses ateliers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from api.etat import (
    ActionSuggeree,
    EtatAPI,
    PropositionSupervision,
    TypeSignal,
    signature_objectifs,
    structure_contraintes,
)
from solver_store.registry import Registre
from supervision.adequation import evaluer_solveur, solveur_a_evaluer
from supervision.agent import FaitSignal, proposer_actions
from supervision.detecteurs import (
    SignalCommandeEnRetard,
    SignalDetecte,
    SignalEchecsRepetes,
    SignalInstanceAReplanifier,
    SignalInstanceJugeeInfaisable,
    SignalSignatureOrpheline,
    SignalSolveurARegenerer,
    detecter_commandes_en_retard,
    detecter_signaux_instance,
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
    "solveur_a_regenerer": "regenerer_solveur",
    # Informatif : ni régénérer (le solveur n'est pas mis en cause) ni exécuter (il répondrait encore
    # « aucune solution ») — un humain vérifie les données de l'atelier.
    "instance_jugee_infaisable": "aucune",
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
    "solveur_a_regenerer": (
        "Le solveur de cet atelier ne correspond plus à l'instance actuelle (contraintes, objectifs ou "
        "algorithme) — une régénération est recommandée."
    ),
    "instance_jugee_infaisable": (
        "Le solveur ne trouve aucune solution pour cet atelier dans son état actuel. Cela peut venir des "
        "données (échéances impossibles, stock insuffisant...) autant que du solveur : vérifiez les données "
        "avant d'envisager une régénération."
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


def _unifier_solveur_a_regenerer(signal: SignalSolveurARegenerer) -> _SignalUnifie:
    evaluation = signal.evaluation
    # Un détail par argument bloquant (preuves comprises) — c'est ce qui justifie la proposition,
    # relu par l'humain avant d'accepter la régénération.
    details = [f"solveur={evaluation.id_solveur}"]
    for constat in evaluation.constats:
        if constat.verdict != "bloquant":
            continue
        details.append(f"{constat.sujet} : {constat.argument}")
        details.extend(f"  preuve : {preuve}" for preuve in constat.preuves)
    return _SignalUnifie(
        type_signal="solveur_a_regenerer",
        instance_id=signal.instance_id,
        structure_contraintes=signal.structure_contraintes,
        signature_objectifs=signal.signature_objectifs,
        execution_ids=(),
        details=tuple(details),
        description=(
            f"Le solveur {evaluation.id_solveur} n'est plus adapté à cet atelier, pour ces raisons : "
            + " ; ".join(evaluation.raisons())
            + "."
        ),
    )


def _unifier_instance_jugee_infaisable(signal: SignalInstanceJugeeInfaisable) -> _SignalUnifie:
    return _SignalUnifie(
        type_signal="instance_jugee_infaisable",
        instance_id=signal.instance_id,
        structure_contraintes=signal.structure_contraintes,
        signature_objectifs=signal.signature_objectifs,
        execution_ids=(),
        details=(f"solveur={signal.id_solveur}", "essai=aucune solution trouvée"),
        description=(
            f"Essai réel du solveur {signal.id_solveur} sur l'instance actuelle de cet atelier : aucune "
            "solution trouvée. Cause possible côté données (échéances impossibles, stock insuffisant...) "
            "autant que côté solveur — à vérifier par un humain, pas une raison de régénérer à elle seule."
        ),
    )


def _unifier(signal: SignalDetecte) -> _SignalUnifie:
    if isinstance(signal, SignalInstanceJugeeInfaisable):
        return _unifier_instance_jugee_infaisable(signal)
    if isinstance(signal, SignalSolveurARegenerer):
        return _unifier_solveur_a_regenerer(signal)
    if isinstance(signal, SignalSignatureOrpheline):
        return _unifier_signature_orpheline(signal)
    if isinstance(signal, SignalInstanceAReplanifier):
        return _unifier_instance_a_replanifier(signal)
    if isinstance(signal, SignalCommandeEnRetard):
        return _unifier_commande_en_retard(signal)
    return _unifier_echecs_repetes(signal)


def analyser_instance(
    etat: EtatAPI,
    registre: Registre,
    modele: BaseChatModel,
    instance_id: str,
    id_solveur: str | None = None,
) -> list[PropositionSupervision]:
    """Cycle complet pour **un seul atelier** (instance) : vérifie d'abord si son solveur doit
    être régénéré (`supervision/adequation.py` — contraintes, objectifs, meilleur algorithme), puis
    détection LLM limitée à ses propres
    données (`detecter_signaux_instance`), commandes en retard de cet atelier seulement (sans LLM,
    `detecter_commandes_en_retard`), écarte ce qui est déjà couvert par une proposition en attente
    sur cet atelier, fait rédiger/prioriser le reste par un second appel LLM (un seul pour tout
    l'atelier, jamais un par signal), puis persiste. La rédaction est évitée quand rien de nouveau
    n'a été détecté pour cet atelier. Lève `KeyError` si l'instance n'existe pas.

    `id_solveur` : analyse du couple (atelier, solveur) — voir `detecter_signaux_instance`, qui
    lève `SolveurHorsAtelier` si ce solveur n'appartient pas à l'atelier."""
    client_id, instance = etat.recuperer_instance(instance_id)
    detectes = list(detecter_signaux_instance(etat, registre, modele, instance_id, id_solveur))

    # Faut-il régénérer le solveur ? Seulement sur argument bloquant (essai réel, lecture du code,
    # Benchmarker — supervision/adequation.py), jamais parce qu'une contrainte a simplement été
    # ajoutée ou retirée. Si oui, une ré-exécution avec ce même solveur n'a plus de sens :
    # `instance_a_replanifier` est retiré au profit de la régénération, pour ne jamais proposer
    # deux actions contradictoires.
    solveur = solveur_a_evaluer(registre, client_id, instance_id, id_solveur)
    if solveur is not None:
        evaluation = evaluer_solveur(etat, registre, modele, instance_id, solveur)
        if evaluation.instance_jugee_infaisable:
            detectes.append(
                SignalInstanceJugeeInfaisable(
                    instance_id=instance_id,
                    client_id=client_id,
                    id_solveur=solveur.id,
                    structure_contraintes=structure_contraintes(instance),
                    signature_objectifs=signature_objectifs(instance),
                )
            )
        if evaluation.a_regenerer:
            detectes = [s for s in detectes if not isinstance(s, SignalInstanceAReplanifier)]
            detectes.append(
                SignalSolveurARegenerer(
                    instance_id=instance_id,
                    client_id=client_id,
                    evaluation=evaluation,
                    structure_contraintes=structure_contraintes(instance),
                    signature_objectifs=signature_objectifs(instance),
                )
            )

    signaux = [_unifier(s) for s in detectes]
    signaux += [_unifier(s) for s in detecter_commandes_en_retard(etat, client_id, instance_id=instance_id)]

    # `commande_id` fait partie de la clé : sans lui, une seule commande en retard sur l'atelier
    # couvrirait indéfiniment toutes ses *autres* commandes en retard (jamais reproposées) —
    # `None` pour les trois autres signaux, dédupliqués par (type_signal, instance_id) seuls.
    deja_en_attente = {
        (p["type_signal"], p["instance_id"], p.get("commande_id"))
        for p in etat.lister_propositions(client_id=client_id, en_attente_seulement=True)
        if p["instance_id"] == instance_id
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
        # Le signal déjà détecté et validé fait foi — si l'appel LLM de rédaction a ignoré ou
        # déformé cette référence, on ne le perd jamais, on retombe sur un résumé canné.
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


def analyser_et_proposer(
    etat: EtatAPI, registre: Registre, modele: BaseChatModel, client_id: str
) -> list[PropositionSupervision]:
    """Tous les ateliers d'un client, **l'un après l'autre** (`analyser_instance`) — chaque
    atelier a sa propre détection et sa propre rédaction, jamais un appel LLM partagé entre
    ateliers. Aucun appel LLM si le client n'a aucune instance."""
    propositions: list[PropositionSupervision] = []
    for info in etat.lister_instances(client_id=client_id):
        propositions.extend(analyser_instance(etat, registre, modele, info["instance_id"]))
    return propositions

"""Boucle d'amélioration diagnostique (§2, §5.7, PH10-T3) : quand un planning
produit en production est jugé mauvais — KPI dégradés et/ou signal humain —
attribue la cause par élimination, dans un ordre précis, avant toute action :

1. **Code fautif ?** Le solveur candidat est rejoué sur le banc synthétique à
   vérité terrain connue (Étape 3). S'il échoue déjà là où l'optimum est
   prouvé par construction, le bug est dans le code, indépendamment de toute
   donnée de production.
2. **Données corrompues ?** Si le code est sain sur la vérité terrain, la
   faisabilité (Étape 2) du planning réellement produit sur l'instance de
   production est vérifiée. Une violation ici, alors que le code passe la
   vérité terrain, pointe vers des données d'entrée corrompues ou
   incohérentes plutôt qu'un bug général.
3. **Spécification DSL mal comprise ?** Si le code est sain et les données
   propres, le solveur est confronté aux cas de référence sémantiques
   (Étape 4/PH4-T3, §6.2 brique 3). Un échec ici — planning légal et même
   optimal, mais pour le mauvais problème — révèle une mauvaise traduction
   métier→DSL (ex. sens d'une précédence), pas un bug de code.

Ne s'arrête jamais sur "aucune cause identifiée" sans le dire explicitement :
un KPI dégradé sans qu'aucune des trois briques ne l'explique signale un
angle mort du DSL actuel (une notion métier non modélisée), à investiguer
avec un humain.

Ce module ne fait jamais qu'un diagnostic et une proposition — **jamais une
action automatique** : `humain_decide` dans le verdict rappelle que
l'application d'une correction reste une décision humaine (fil directeur du
projet, §2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dsl.schema import InstanceTRCO, Planning
from validation_engine.cascade import Solveur, evaluer_fidelite_reference, evaluer_optimalite_banc
from validation_engine.feasibility_checker import verifier_faisabilite

Cause = Literal["code", "donnees", "specification_dsl", "aucune"]

_PROPOSITIONS: dict[Cause, str] = {
    "code": (
        "Le solveur échoue déjà sur des instances à vérité terrain connue (banc synthétique, "
        "Étape 3) : le bug est dans le code, indépendamment des données de production. "
        "Proposition : revenir à la dernière version du solveur enregistrée dans le store "
        "(solver_store/) qui passait la cascade, ou relancer une génération."
    ),
    "donnees": (
        "Le solveur est sain sur la vérité terrain, mais produit un planning illégal sur les "
        "données de production. Proposition : valider/nettoyer les données d'entrée (garde-fou "
        "amont, §6.7) avant toute nouvelle exécution."
    ),
    "specification_dsl": (
        "Le solveur est sain sur la vérité terrain et sur les données de production, mais "
        "échoue sur un cas de référence sémantique : planning légal, mauvais problème. "
        "Proposition : revoir la traduction métier→DSL avec le client (sens d'une précédence, "
        "choix de ressource, durée par ressource...)."
    ),
    "aucune": (
        "Aucune des trois briques n'explique le signal reçu : le planning peut être correct au "
        "regard du DSL actuel tout en heurtant un critère métier non modélisé. "
        "Proposition : investigation humaine, sans cause automatiquement attribuable."
    ),
}


@dataclass(frozen=True)
class DiagnosticAttribution:
    """Le verdict d'attribution : quelle cause, pourquoi, et une proposition —
    jamais une action déclenchée automatiquement."""

    cause: Cause
    motif_declenchement: str
    details: tuple[str, ...]
    proposition: str
    humain_decide: bool = True


def diagnostiquer(
    solveur: Solveur,
    instance_production: InstanceTRCO,
    planning_production: Planning,
    motif_declenchement: str,
) -> DiagnosticAttribution:
    """Attribue la cause d'un planning de production jugé mauvais, par
    élimination dans l'ordre code → données → spécification DSL.

    `motif_declenchement` documente le signal qui a déclenché ce diagnostic
    (KPI dégradé, signalement humain, ou les deux — §2) ; il est reporté tel
    quel dans le verdict, jamais interprété ici.
    """
    verdict_banc = evaluer_optimalite_banc(solveur)
    if not verdict_banc.reussi:
        return DiagnosticAttribution(
            cause="code",
            motif_declenchement=motif_declenchement,
            details=tuple(f"{echec.nom} : {'; '.join(echec.details)}" for echec in verdict_banc.echecs),
            proposition=_PROPOSITIONS["code"],
        )

    verdict_donnees = verifier_faisabilite(instance_production, planning_production)
    if not verdict_donnees.legal:
        return DiagnosticAttribution(
            cause="donnees",
            motif_declenchement=motif_declenchement,
            details=tuple(violation.message for violation in verdict_donnees.violations),
            proposition=_PROPOSITIONS["donnees"],
        )

    verdict_fidelite = evaluer_fidelite_reference(solveur)
    if not verdict_fidelite.reussi:
        return DiagnosticAttribution(
            cause="specification_dsl",
            motif_declenchement=motif_declenchement,
            details=tuple(f"{echec.nom} : {'; '.join(echec.details)}" for echec in verdict_fidelite.echecs),
            proposition=_PROPOSITIONS["specification_dsl"],
        )

    return DiagnosticAttribution(
        cause="aucune",
        motif_declenchement=motif_declenchement,
        details=(),
        proposition=_PROPOSITIONS["aucune"],
    )

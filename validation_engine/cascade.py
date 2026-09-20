"""Cascade de validation (§6.2, §6.3) : assemble les trois briques dans
l'ordre où elles doivent être construites et interrogées — faisabilité →
optimalité sur banc synthétique → fidélité sur cas de référence — parce que
chacune dépend de la précédente (le banc et les cas de référence *appellent*
la faisabilité pour filtrer les plannings légaux, §6.3). Prend n'importe
quel solveur candidat (le solveur de référence aujourd'hui, le futur code
généré demain) et rend, par instance testée, un verdict diagnostique : quelle
brique échoue et pourquoi — jamais un simple vrai/faux.

Répartition volontaire des deux briques de qualité : l'optimalité (brique 2)
ne porte que sur le banc synthétique, seul endroit où l'optimum est prouvé
par construction (§6.4) ; la fidélité (brique 3) ne porte que sur les cas de
référence, seul endroit où un humain a validé une réponse précise (§6.2
brique 3). Un même défaut peut donc, selon où il se manifeste, être classé
« optimalite » ou « fidelite » — ce n'est pas une ambiguïté, c'est le
découpage des responsabilités entre les deux bancs.

`tolerance_relative` et `comparer_affectation` existent pour les heuristiques
recommandées par l'agent Benchmarker (§5.6) : les valeurs par défaut sont strictes
(exactitude requise) ; un algorithme approché — tout algorithme généré par PRISME,
qui n'a plus de moteur exact — est jugé sur la qualité de son makespan à une tolérance explicite près, sans
exiger l'affectation tâche→ressource exacte d'un cas écrit à la main pour un
autre algorithme. `evaluer_cascade` reste agnostique de *quel* algorithme a
produit le solveur — c'est à l'appelant (`generation/graph.py`,
via `generation.agents.benchmarker.parametres_cascade_pour_algorithme`, qui
connaît la recommandation du Benchmarker) de choisir ces deux valeurs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from dsl.schema import InstanceTRCO, Planning
from validation_engine.feasibility_checker import verifier_faisabilite
from validation_engine.makespan import calculer_makespan
from validation_engine.reference_cases import CasReference, charger_cas_reference
from validation_engine.synthetic_bench import InstanceSynthetique, generer_catalogue

Solveur = Callable[[InstanceTRCO], Planning | None]

Brique = Literal["faisabilite", "optimalite", "fidelite"]


@dataclass(frozen=True)
class DiagnosticInstance:
    """Le verdict pour une instance : quelle brique échoue, et pourquoi (jamais un simple booléen)."""

    nom: str
    brique_en_echec: Brique | None
    details: tuple[str, ...]

    @property
    def reussi(self) -> bool:
        return self.brique_en_echec is None


@dataclass(frozen=True)
class VerdictCascade:
    diagnostics: tuple[DiagnosticInstance, ...]

    @property
    def reussi(self) -> bool:
        return all(diagnostic.reussi for diagnostic in self.diagnostics)

    @property
    def echecs(self) -> tuple[DiagnosticInstance, ...]:
        return tuple(diagnostic for diagnostic in self.diagnostics if not diagnostic.reussi)


def _diagnostiquer_faisabilite(
    nom: str, instance: InstanceTRCO, planning: Planning | None
) -> DiagnosticInstance | None:
    """Brique 1. `None` si elle passe ; sinon le diagnostic de l'échec."""
    if planning is None:
        return DiagnosticInstance(nom, "faisabilite", ("le solveur n'a produit aucun planning",))
    verdict = verifier_faisabilite(instance, planning)
    if not verdict.legal:
        return DiagnosticInstance(nom, "faisabilite", tuple(v.message for v in verdict.violations))
    return None


def evaluer_un_cas_de_banc(
    solveur: Solveur, cas: InstanceSynthetique, tolerance_relative: float = 0.0
) -> DiagnosticInstance:
    """Brique 2 sur une instance du banc synthétique : le solveur retrouve-t-il
    l'optimum connu par construction (Étape 3), à `tolerance_relative` près ?
    """
    planning = solveur(cas.instance)
    echec_faisabilite = _diagnostiquer_faisabilite(cas.nom, cas.instance, planning)
    if echec_faisabilite is not None:
        return echec_faisabilite

    assert planning is not None
    makespan = calculer_makespan(cas.instance, planning)
    plafond_tolere = cas.optimum * (1 + tolerance_relative)
    if makespan > plafond_tolere:
        return DiagnosticInstance(
            cas.nom,
            "optimalite",
            (f"makespan {makespan} > optimum connu {cas.optimum} (tolérance {tolerance_relative:.0%})",),
        )
    return DiagnosticInstance(cas.nom, None, ())


def evaluer_optimalite_banc(solveur: Solveur, tolerance_relative: float = 0.0) -> VerdictCascade:
    """Brique 2 sur tout le catalogue du banc synthétique (§6.4)."""
    return VerdictCascade(
        tuple(evaluer_un_cas_de_banc(solveur, cas, tolerance_relative) for cas in generer_catalogue())
    )


def evaluer_un_cas_reference(
    solveur: Solveur,
    cas: CasReference,
    tolerance_relative: float = 0.0,
    comparer_affectation: bool = True,
) -> DiagnosticInstance:
    """Brique 3 sur un cas de référence : le solveur retombe-t-il sur le
    planning attendu, écrit à la main pour la fidélité sémantique (§6.2
    brique 3) ? Comparaison volontairement partielle — même affectation
    tâche→ressource et même makespan que le planning attendu, pas l'égalité
    horaire stricte, puisque plusieurs plannings différemment chronométrés
    peuvent être également valides.

    `comparer_affectation` et `tolerance_relative` existent pour les
    heuristiques recommandées par l'agent Benchmarker
    (`generation/agents/benchmarker.py`) : un algorithme approché (génétique,
    ACO, recuit simulé, tabou, heuristiques de dispatching) n'a aucune raison
    de reproduire l'affectation exacte écrite à la main pour ce cas — seule
    la qualité du makespan compte alors, à `tolerance_relative` près. Les
    valeurs par défaut restent strictes (les deux critères).
    """
    planning = solveur(cas.instance)
    echec_faisabilite = _diagnostiquer_faisabilite(cas.nom, cas.instance, planning)
    if echec_faisabilite is not None:
        return echec_faisabilite

    assert planning is not None
    makespan_obtenu = calculer_makespan(cas.instance, planning)
    makespan_attendu = calculer_makespan(cas.instance, cas.planning_attendu)

    ecarts: list[str] = []
    if comparer_affectation:
        affectation_obtenue = {operation.tache: operation.ressource for operation in planning.operations}
        affectation_attendue = {
            operation.tache: operation.ressource for operation in cas.planning_attendu.operations
        }
        ecarts.extend(
            f"tâche {tache!r} : ressource attendue {ressource_attendue!r}, "
            f"obtenue {affectation_obtenue.get(tache)!r}"
            for tache, ressource_attendue in affectation_attendue.items()
            if affectation_obtenue.get(tache) != ressource_attendue
        )

    plafond_tolere = makespan_attendu * (1 + tolerance_relative)
    if makespan_obtenu > plafond_tolere:
        ecarts.append(
            f"makespan attendu {makespan_attendu} (tolérance {tolerance_relative:.0%}), obtenu {makespan_obtenu}"
        )

    if ecarts:
        return DiagnosticInstance(cas.nom, "fidelite", tuple(ecarts))
    return DiagnosticInstance(cas.nom, None, ())


def evaluer_fidelite_reference(
    solveur: Solveur, tolerance_relative: float = 0.0, comparer_affectation: bool = True
) -> VerdictCascade:
    """Brique 3 sur tout le catalogue de cas de référence (§6.2 brique 3)."""
    return VerdictCascade(
        tuple(
            evaluer_un_cas_reference(solveur, cas, tolerance_relative, comparer_affectation)
            for cas in charger_cas_reference()
        )
    )


def evaluer_cascade(
    solveur: Solveur, tolerance_relative: float = 0.0, comparer_affectation: bool = True
) -> VerdictCascade:
    """Les trois briques bout à bout (§6.3) : faisabilité → optimalité → fidélité.

    Par défaut (`tolerance_relative=0.0`, `comparer_affectation=True`) le
    comportement est celui, strict, d'un solveur exact — inchangé
    pour tous les appelants existants. Un algorithme approché recommandé par
    l'agent Benchmarker doit être évalué avec une tolérance non nulle et
    `comparer_affectation=False` (voir `generation/graph.py`,
    seul endroit qui connaît quel algorithme a produit le solveur candidat)."""
    verdict_banc = evaluer_optimalite_banc(solveur, tolerance_relative)
    verdict_reference = evaluer_fidelite_reference(solveur, tolerance_relative, comparer_affectation)
    return VerdictCascade(verdict_banc.diagnostics + verdict_reference.diagnostics)

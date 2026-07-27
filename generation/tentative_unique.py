"""Une tentative de génération unique, sans boucle (Étape 4) — jugée par la
cascade complète de l'Étape 5. Distinct de `generation.graph`
(Étape 6, pipeline multi-agents avec boucle de réparation Reviewer/Debugger) :
ce module reste le mode simple, tir unique, sans agents ni réparation.
"""

from __future__ import annotations

from dataclasses import dataclass

from generation.agents.client_llm import AppelLLM
from generation.agents.generateur import generer_code_solveur
from generation.executer import ErreurExecutionGeneree, executer_code_genere
from generation.validation_statique import ResultatValidationStatique, valider_code_genere
from validation_engine.cascade import VerdictCascade, evaluer_cascade


@dataclass(frozen=True)
class ResultatTentative:
    """Le devenir complet d'une tentative : code, validation statique,
    erreur d'exécution éventuelle, verdict de la cascade éventuel."""

    code_source: str
    validation_statique: ResultatValidationStatique
    erreur_execution: str | None
    verdict_cascade: VerdictCascade | None

    @property
    def reussi(self) -> bool:
        return (
            self.validation_statique.valide
            and self.erreur_execution is None
            and self.verdict_cascade is not None
            and self.verdict_cascade.reussi
        )


def tenter_generation_unique(appel_llm: AppelLLM) -> ResultatTentative:
    """Génère, valide statiquement, exécute, puis juge par la cascade —
    sans jamais laisser une erreur inattendue du code généré interrompre la
    mesure (§6.6 : le code peut échouer, la mesure doit survivre)."""
    brut = generer_code_solveur(appel_llm)
    validation = valider_code_genere(brut.code_source)
    if not validation.valide:
        return ResultatTentative(brut.code_source, validation, None, None)

    try:
        solveur = executer_code_genere(brut.code_source)
    except ErreurExecutionGeneree as erreur:
        return ResultatTentative(brut.code_source, validation, str(erreur), None)

    try:
        verdict = evaluer_cascade(solveur)
    except Exception as erreur:  # le code généré peut lever n'importe quoi à l'exécution
        return ResultatTentative(brut.code_source, validation, str(erreur), None)

    return ResultatTentative(brut.code_source, validation, None, verdict)

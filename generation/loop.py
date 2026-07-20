"""Boucle de réparation bornée (Étape 6, §6.6) — permet au Debugger de faire
plusieurs tentatives de correction (max 3) plutôt qu'une seule.

Cette boucle s'exécute après le Développeur et avant l'Optimiseur :
- Le Reviewer relit le code à chaque itération
- Le Debugger corrige les bugs détectés (Reviewer OU validation)
- La validation complète (statique → exécution → cascade) vérifie le code
- Si succès : on sort de la boucle
- Si échec : on recommence (max 3 fois)

Distinction avec `pipeline_multi_agents.py` (ancienne version sans boucle) :
- Sans boucle : Debugger 1 seule fois, puis échec si validation échoue
- Avec boucle : Debugger jusqu'à 3 fois, avec feedback de la validation

§6.6 : "La boucle doit rester **bornée** (max tentatives, puis échec honnête
à un humain), **offline** (à la génération, jamais per-exécution), et
**diagnostique** (nomme quelle contrainte est violée)."
"""

from __future__ import annotations

from dataclasses import dataclass

from generation.agents import debugger, reviewer
from generation.agents.client_llm import AppelLLM
from generation.agents.reviewer import ResultatRevue
from generation.executer import ErreurExecutionGeneree, executer_code_genere
from generation.validation_statique import ResultatValidationStatique, valider_code_genere
from validation_engine.cascade import VerdictCascade, evaluer_cascade


# Constante : nombre max de tentatives de réparation
MAX_TENTATIVES_REPARATION = 3


@dataclass(frozen=True)
class TentativeReparation:
    """Une tentative de correction dans la boucle."""

    numero: int  # 1, 2, 3
    code_candidat: str
    revue: ResultatRevue
    validation_statique: ResultatValidationStatique | None
    erreur_execution: str | None
    verdict_cascade: VerdictCascade | None
    reussi: bool


@dataclass(frozen=True)
class ResultatBoucleReparation:
    """Résultat de la boucle de réparation."""

    code_initial: str
    tentatives: tuple[TentativeReparation, ...]
    code_final: str
    reussi: bool
    nombre_tentatives: int

    # Derniers résultats (pour reporting)
    derniere_revue: ResultatRevue
    derniere_validation_statique: ResultatValidationStatique | None
    derniere_erreur_execution: str | None
    dernier_verdict_cascade: VerdictCascade | None


def _valider_completement(code: str) -> tuple[ResultatValidationStatique, str | None, VerdictCascade | None]:
    """Valide le code en 3 passes : statique → exécution → cascade.

    Retourne :
    - validation_statique
    - erreur_execution (None si OK)
    - verdict_cascade (None si échec avant)
    """
    validation = valider_code_genere(code)
    if not validation.valide:
        return validation, None, None

    try:
        solveur = executer_code_genere(code)
    except ErreurExecutionGeneree as erreur:
        return validation, str(erreur), None

    try:
        verdict = evaluer_cascade(solveur)
    except Exception as erreur:  # le code généré peut lever n'importe quoi
        return validation, str(erreur), None

    return validation, None, verdict


def boucle_reparation_bornee(appel_llm: AppelLLM, code_initial: str) -> ResultatBoucleReparation:
    """Exécute la boucle de réparation bornée (max 3 tentatives).

    Workflow :
    1. Reviewer relit le code
    2. Si approuvé → Validation
       - Si succès → STOP (succès)
       - Si échec → Debugger avec erreur de validation → retry
    3. Si rejeté → Debugger avec commentaires Reviewer → retry
    4. Répéter jusqu'à succès ou MAX_TENTATIVES

    Args:
        appel_llm: Client LLM pour appeler Reviewer et Debugger
        code_initial: Code à réparer (du Développeur)

    Returns:
        ResultatBoucleReparation avec historique complet des tentatives
    """
    code_candidat = code_initial
    tentatives: list[TentativeReparation] = []

    for numero_tentative in range(1, MAX_TENTATIVES_REPARATION + 1):
        # 1. Reviewer relit le code actuel
        revue = reviewer.relire_code(appel_llm, code_candidat)

        if revue.approuve:
            # 2a. Code approuvé → Validation complète
            validation, erreur_exec, verdict = _valider_completement(code_candidat)

            reussi = validation.valide and erreur_exec is None and verdict is not None and verdict.reussi

            tentative = TentativeReparation(
                numero=numero_tentative,
                code_candidat=code_candidat,
                revue=revue,
                validation_statique=validation,
                erreur_execution=erreur_exec,
                verdict_cascade=verdict,
                reussi=reussi,
            )
            tentatives.append(tentative)

            if reussi:
                # Succès ! On sort de la boucle
                return ResultatBoucleReparation(
                    code_initial=code_initial,
                    tentatives=tuple(tentatives),
                    code_final=code_candidat,
                    reussi=True,
                    nombre_tentatives=numero_tentative,
                    derniere_revue=revue,
                    derniere_validation_statique=validation,
                    derniere_erreur_execution=erreur_exec,
                    dernier_verdict_cascade=verdict,
                )

            # 2b. Validation échouée → Construire message d'erreur pour Debugger
            if not validation.valide:
                erreur_detaillee = f"Validation statique échouée : {validation.raison}"
            elif erreur_exec is not None:
                erreur_detaillee = f"Erreur d'exécution : {erreur_exec}"
            elif verdict is None:
                erreur_detaillee = "La validation cascade n'a pas pu être exécutée"
            else:
                # Verdict existe mais échec → diagnostic cascade
                erreur_detaillee = f"Validation cascade échouée : {verdict.resumer()}"

            # Dernière tentative ? Pas de correction, on arrête
            if numero_tentative >= MAX_TENTATIVES_REPARATION:
                break

            # Debugger corrige avec feedback de la validation
            correction = debugger.corriger_code(appel_llm, code_candidat, erreur_detaillee)
            code_candidat = correction.code_source

        else:
            # 3. Code rejeté par Reviewer → Debugger avec commentaires
            tentative = TentativeReparation(
                numero=numero_tentative,
                code_candidat=code_candidat,
                revue=revue,
                validation_statique=None,  # Pas validé car rejeté par Reviewer
                erreur_execution=None,
                verdict_cascade=None,
                reussi=False,
            )
            tentatives.append(tentative)

            # Dernière tentative ? Pas de correction, on arrête
            if numero_tentative >= MAX_TENTATIVES_REPARATION:
                break

            # Debugger corrige avec commentaires du Reviewer
            correction = debugger.corriger_code(appel_llm, code_candidat, revue.commentaires)
            code_candidat = correction.code_source

    # Échec après MAX_TENTATIVES
    derniere = tentatives[-1]
    return ResultatBoucleReparation(
        code_initial=code_initial,
        tentatives=tuple(tentatives),
        code_final=code_candidat,
        reussi=False,
        nombre_tentatives=len(tentatives),
        derniere_revue=derniere.revue,
        derniere_validation_statique=derniere.validation_statique,
        derniere_erreur_execution=derniere.erreur_execution,
        dernier_verdict_cascade=derniere.verdict_cascade,
    )

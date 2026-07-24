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

`boucle_reparation_bornee_stream` est la vraie implémentation — elle yield
un évènement `EvenementEtape` après chaque sous-étape (Reviewer, Validation,
Debugger), pour qu'un pipeline de plusieurs minutes ne soit pas une attente
aveugle côté appelant (voir `api/routes/generation.py`, streaming SSE).
`boucle_reparation_bornee` reste la version bloquante, pour les appelants
qui ne veulent que le résultat final (scripts/)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from generation.agents import debugger, reviewer
from generation.agents.client_llm import construire_appel_llm_pour_agent
from generation.agents.reviewer import ResultatRevue
from generation.executer import ErreurExecutionGeneree, executer_code_genere
from generation.validation_statique import ResultatValidationStatique, valider_code_genere
from validation_engine.cascade import VerdictCascade, evaluer_cascade

# Constante : nombre max de tentatives de réparation
MAX_TENTATIVES_REPARATION = 3

EvenementEtape = dict[str, str]  # {"agent": ..., "statut": "en_cours"|"termine"|"echec", "resume": ...}


def etape(agent: str, statut: str, resume: str) -> EvenementEtape:
    return {"agent": agent, "statut": statut, "resume": resume}


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


def boucle_reparation_bornee_stream(code_initial: str) -> Iterator[EvenementEtape | ResultatBoucleReparation]:
    """Version streaming — yield un `EvenementEtape` après chaque sous-étape
    (Reviewer, Validation, Debugger) de chaque tentative ; le tout dernier
    élément produit est toujours le `ResultatBoucleReparation` final.

    Reviewer et Debugger construisent chacun leur propre client LLM via
    `construire_appel_llm_pour_agent` (§5.6) — le fournisseur optimal par
    agent, pas un client partagé imposé par l'appelant.
    """
    code_candidat = code_initial
    tentatives: list[TentativeReparation] = []

    for numero_tentative in range(1, MAX_TENTATIVES_REPARATION + 1):
        nom_reviewer = f"reviewer (tentative {numero_tentative}/{MAX_TENTATIVES_REPARATION})"
        nom_validation = f"validation (tentative {numero_tentative}/{MAX_TENTATIVES_REPARATION})"
        nom_debugger = f"debugger (tentative {numero_tentative}/{MAX_TENTATIVES_REPARATION})"

        # 1. Reviewer relit le code actuel
        yield etape(nom_reviewer, "en_cours", "Relecture critique du code...")
        revue = reviewer.relire_code(construire_appel_llm_pour_agent("reviewer"), code_candidat)
        yield etape(
            nom_reviewer,
            "termine" if revue.approuve else "echec",
            "Code approuvé" if revue.approuve else f"{len(revue.problemes)} problème(s) relevé(s) par le reviewer",
        )

        if revue.approuve:
            # 2a. Code approuvé → Validation complète
            yield etape(nom_validation, "en_cours", "Validation statique → exécution → cascade complète...")
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

            yield etape(
                nom_validation,
                "termine" if reussi else "echec",
                "Cascade de validation au vert" if reussi else "Cascade de validation en échec",
            )

            if reussi:
                # Succès ! On sort de la boucle
                yield ResultatBoucleReparation(
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
                return

            # 2b. Validation échouée → Construire message d'erreur pour Debugger
            if not validation.valide:
                # ResultatValidationStatique n'a pas de champ `raison`, mais
                # `violations` (tuple[str, ...]) — même bug que resumer() plus
                # bas, corrigé ici.
                erreur_detaillee = "Validation statique échouée : " + "; ".join(validation.violations)
            elif erreur_exec is not None:
                erreur_detaillee = f"Erreur d'exécution : {erreur_exec}"
            elif verdict is None:
                erreur_detaillee = "La validation cascade n'a pas pu être exécutée"
            else:
                # Verdict existe mais échec → diagnostic cascade (VerdictCascade
                # n'a pas de méthode resumer() — on construit le résumé ici,
                # à partir des diagnostics en échec, chacun nommant sa brique).
                details_echecs = "; ".join(
                    f"[{d.brique_en_echec}] {d.nom} : {'; '.join(d.details)}" for d in verdict.echecs
                )
                erreur_detaillee = f"Validation cascade échouée : {details_echecs}"

            # Dernière tentative ? Pas de correction, on arrête
            if numero_tentative >= MAX_TENTATIVES_REPARATION:
                break

            # Debugger corrige avec feedback de la validation
            yield etape(nom_debugger, "en_cours", "Correction du code d'après le diagnostic de validation...")
            correction = debugger.corriger_code(
                construire_appel_llm_pour_agent("debugger"), code_candidat, erreur_detaillee
            )
            yield etape(nom_debugger, "termine", "Code corrigé")
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
            yield etape(nom_debugger, "en_cours", "Correction du code d'après les commentaires du reviewer...")
            correction = debugger.corriger_code(
                construire_appel_llm_pour_agent("debugger"), code_candidat, revue.commentaires
            )
            yield etape(nom_debugger, "termine", "Code corrigé")
            code_candidat = correction.code_source

    # Échec après MAX_TENTATIVES
    derniere = tentatives[-1]
    yield ResultatBoucleReparation(
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


def boucle_reparation_bornee(code_initial: str) -> ResultatBoucleReparation:
    """Version bloquante — ne renvoie que le résultat final, sans les
    évènements intermédiaires. Voir `boucle_reparation_bornee_stream`."""
    resultat: ResultatBoucleReparation | None = None
    for item in boucle_reparation_bornee_stream(code_initial):
        if isinstance(item, ResultatBoucleReparation):
            resultat = item
    assert resultat is not None  # boucle_reparation_bornee_stream yield toujours un résultat final
    return resultat

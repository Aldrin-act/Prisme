"""Pipeline multi-agents AVEC boucle de réparation (Étape 6 implémentée).

Différence avec `pipeline_multi_agents.py` (version sans boucle) :
- SANS boucle : Reviewer → Debugger 1 fois → Validation → Stop si échec
- AVEC boucle : Reviewer → Debugger → Validation → [Retry jusqu'à 3 fois]

Cette version remplace l'appel unique au Debugger par un appel à
`loop.boucle_reparation_bornee()` qui gère la boucle complète.

Workflow complet :
1. Orchestrateur (planification)
2. Analyste (spécification)
3. Architecte (conception)
4. Développeur (code initial)
5. Testeur (tests pytest)
6. ** BOUCLE DE RÉPARATION (max 3 tentatives) **
   - Reviewer
   - Debugger (si bugs détectés)
   - Validation (statique → exécution → cascade)
   - Retry si échec
7. Optimiseur (si succès)
8. Documentation

§6.6 : La boucle reste **bornée** (3 tentatives max), **offline** (génération),
et **diagnostique** (feedback précis de la validation).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from generation.agents import (
    analyste,
    architecte,
    documentation,
    optimiseur,
    orchestrateur,
    testeur,
)
from generation.agents.client_llm import AppelLLM, construire_appel_llm_pour_agent
from generation.agents.generateur import generer_code_depuis_plan
from generation.agents.optimiseur import ResultatOptimisation
from generation.agents.orchestrateur import EtapePlan
from generation.executer import ErreurExecutionGeneree, executer_code_genere
from generation.loop import EvenementEtape, ResultatBoucleReparation, boucle_reparation_bornee_stream, etape
from generation.validation_statique import ResultatValidationStatique, valider_code_genere
from validation_engine.cascade import VerdictCascade, evaluer_cascade


@dataclass(frozen=True)
class _ResultatValidationComplete:
    """Validation complète : statique → exécution → cascade."""

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


def _valider_completement(code: str) -> _ResultatValidationComplete:
    validation = valider_code_genere(code)
    if not validation.valide:
        return _ResultatValidationComplete(validation, None, None)

    try:
        solveur = executer_code_genere(code)
    except ErreurExecutionGeneree as erreur:
        return _ResultatValidationComplete(validation, str(erreur), None)

    try:
        verdict = evaluer_cascade(solveur)
    except Exception as erreur:
        return _ResultatValidationComplete(validation, str(erreur), None)

    return _ResultatValidationComplete(validation, None, verdict)


@dataclass(frozen=True)
class ResultatPipelineAvecBoucle:
    """Résultat du pipeline multi-agents avec boucle de réparation.

    Champs supplémentaires par rapport à `ResultatPipelineMultiAgents` :
    - `boucle_reparation` : Historique complet des tentatives (3 max)
    - Pas de `code_corrige` unique, mais un historique dans la boucle
    """

    plan_orchestrateur: tuple[EtapePlan, ...]
    specification: str
    plan_technique: str
    code_genere: str
    tests_generes: str

    # Boucle de réparation (nouveau !)
    boucle_reparation: ResultatBoucleReparation

    # Code final (après boucle)
    code_final: str
    validation_statique: ResultatValidationStatique | None
    erreur_execution: str | None
    verdict_cascade: VerdictCascade | None

    # Optimisation (si succès)
    optimisation: ResultatOptimisation | None
    code_optimise_adopte: bool

    # Documentation
    documentation: str | None

    @property
    def reussi(self) -> bool:
        return (
            self.validation_statique is not None
            and self.validation_statique.valide
            and self.erreur_execution is None
            and self.verdict_cascade is not None
            and self.verdict_cascade.reussi
        )


def tenter_generation_avec_boucle_stream() -> Iterator[EvenementEtape | ResultatPipelineAvecBoucle]:
    """Version streaming du pipeline complet — yield un `EvenementEtape`
    après chaque agent (et chaque sous-étape de la boucle de réparation,
    voir `generation.loop.boucle_reparation_bornee_stream`) ; le tout
    dernier élément produit est toujours le `ResultatPipelineAvecBoucle`
    final. Consommée par `api/routes/generation.py` pour le streaming SSE —
    un pipeline à 8 agents + jusqu'à 3 tentatives de réparation peut prendre
    plusieurs minutes, une attente aveugle n'est pas acceptable.

    Chaque agent construit son propre client LLM via
    `construire_appel_llm_pour_agent(nom)` (§5.6, `config_fournisseurs.py`) —
    le fournisseur optimal par agent, jamais un client partagé imposé par
    l'appelant (un unique client partagé enverrait silencieusement chaque
    étape au fournisseur d'un seul agent, ignorant la répartition par
    fournisseur optimisée par tâche).
    """
    # 1. Orchestrateur
    yield etape("orchestrateur", "en_cours", "Planification de la mission...")
    plan = orchestrateur.planifier(construire_appel_llm_pour_agent("orchestrateur"))
    yield etape("orchestrateur", "termine", f"{len(plan.plan)} étape(s) planifiée(s)")

    # 2. Analyste
    yield etape("analyste", "en_cours", "Analyse de la mission...")
    analyse = analyste.analyser_mission(construire_appel_llm_pour_agent("analyste"))
    yield etape("analyste", "termine", "Spécification technique produite")

    # 3. Architecte
    yield etape("architecte", "en_cours", "Conception du modèle...")
    conception = architecte.concevoir_modele(construire_appel_llm_pour_agent("architecte"), analyse)
    yield etape("architecte", "termine", "Plan technique produit")

    # 4. Développeur
    yield etape("developpeur", "en_cours", "Rédaction du code du solveur...")
    brut = generer_code_depuis_plan(construire_appel_llm_pour_agent("generateur"), conception.en_texte())
    yield etape("developpeur", "termine", f"{len(brut.code_source.splitlines())} ligne(s) de code générées")

    # 5. Testeur
    yield etape("testeur", "en_cours", "Génération des tests...")
    tests = testeur.generer_tests(construire_appel_llm_pour_agent("testeur"), brut.code_source)
    yield etape("testeur", "termine", "Tests générés")

    # 6. BOUCLE DE RÉPARATION (Étape 6) — max 3 tentatives, chaque sous-étape
    # (reviewer/validation/debugger) est elle-même streamée.
    boucle: ResultatBoucleReparation | None = None
    for item in boucle_reparation_bornee_stream(brut.code_source):
        if isinstance(item, ResultatBoucleReparation):
            boucle = item
        else:
            yield item
    assert boucle is not None  # boucle_reparation_bornee_stream yield toujours un résultat final

    if not boucle.reussi:
        # Échec après 3 tentatives → Retour avec échec
        yield ResultatPipelineAvecBoucle(
            plan_orchestrateur=plan.plan,
            specification=analyse.en_texte(),
            plan_technique=conception.en_texte(),
            code_genere=brut.code_source,
            tests_generes=tests.code_tests,
            boucle_reparation=boucle,
            code_final=boucle.code_final,
            validation_statique=boucle.derniere_validation_statique,
            erreur_execution=boucle.derniere_erreur_execution,
            verdict_cascade=boucle.dernier_verdict_cascade,
            optimisation=None,
            code_optimise_adopte=False,
            documentation=None,
        )
        return

    # Succès après boucle → On continue avec l'Optimiseur
    code_candidat = boucle.code_final

    # 7. Optimiseur (si succès)
    yield etape("optimiseur", "en_cours", "Recherche d'optimisations...")
    optimisation = optimiseur.optimiser_code(construire_appel_llm_pour_agent("optimiseur"), code_candidat)
    code_final = code_candidat
    code_optimise_adopte = False
    resultat_final = _valider_completement(code_candidat)

    if optimisation.proposee and optimisation.code_source:
        resultat_opt = _valider_completement(optimisation.code_source)
        if resultat_opt.reussi:
            code_final = optimisation.code_source
            code_optimise_adopte = True
            resultat_final = resultat_opt
    yield etape(
        "optimiseur", "termine", "Optimisation adoptée" if code_optimise_adopte else "Code initial conservé"
    )

    # 8. Documentation
    yield etape("documentation", "en_cours", "Rédaction de la documentation...")
    doc = documentation.documenter_code(construire_appel_llm_pour_agent("documentation"), code_final)
    yield etape("documentation", "termine", "Documentation produite")

    yield ResultatPipelineAvecBoucle(
        plan_orchestrateur=plan.plan,
        specification=analyse.en_texte(),
        plan_technique=conception.en_texte(),
        code_genere=brut.code_source,
        tests_generes=tests.code_tests,
        boucle_reparation=boucle,
        code_final=code_final,
        validation_statique=resultat_final.validation_statique,
        erreur_execution=resultat_final.erreur_execution,
        verdict_cascade=resultat_final.verdict_cascade,
        optimisation=optimisation,
        code_optimise_adopte=code_optimise_adopte,
        documentation=doc.en_texte(),
    )


def tenter_generation_avec_boucle(appel_llm: AppelLLM | None = None) -> ResultatPipelineAvecBoucle:
    """Version bloquante — ne renvoie que le résultat final, sans les
    évènements intermédiaires. `appel_llm` : obsolète, ignoré (voir
    `tenter_generation_avec_boucle_stream`). Voir cette dernière pour le
    streaming SSE (`api/routes/generation.py`)."""
    resultat: ResultatPipelineAvecBoucle | None = None
    for item in tenter_generation_avec_boucle_stream():
        if isinstance(item, ResultatPipelineAvecBoucle):
            resultat = item
    assert resultat is not None  # tenter_generation_avec_boucle_stream yield toujours un résultat final
    return resultat

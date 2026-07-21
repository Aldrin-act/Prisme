"""Pipeline de génération multi-agents (§5.6) — enchaîne les 10 agents de
`generation/agents/` : Orchestrateur → Analyste → Architecte → **Benchmarker**
→ Développeur → Testeur → Reviewer → [Debugger si besoin] → validation
complète → Optimiseur → Documentation.

**Nouveau** : L'agent Benchmarker (ajouté après Architecte) analyse une instance
exemple et recommande le meilleur algorithme (CP-SAT, GA, ACO, Tabu, etc.) selon
les caractéristiques (taille, contraintes, flexibilité). Le Développeur génère
ensuite le code adapté à l'algorithme recommandé.

Reste une **tentative unique bornée**, pas une boucle générale (Étape 6,
toujours non construite) : le Debugger n'intervient qu'une fois, s'il le
faut, jamais en boucle jusqu'à succès. L'ordre d'exécution est câblé ici en
Python, jamais décidé dynamiquement par la réponse de l'Orchestrateur — voir
sa docstring dans `generation/agents/orchestrateur.py`.

À la différence de `generation.tentative_unique` (Étape 4, un seul agent),
c'est ici que vivent les 9 agents supplémentaires demandés pour le pipeline
complet ; les deux chemins restent disponibles indépendamment.
"""

from __future__ import annotations

from dataclasses import dataclass

from generation.agents import (
    analyste,
    architecte,
    benchmarker,
    debugger,
    documentation,
    optimiseur,
    orchestrateur,
    reviewer,
    testeur,
)
from generation.agents.client_llm import AppelLLM
from generation.agents.generateur import generer_code_depuis_plan
from generation.agents.optimiseur import ResultatOptimisation
from generation.agents.orchestrateur import EtapePlan
from generation.agents.reviewer import ResultatRevue
from generation.executer import ErreurExecutionGeneree, executer_code_genere
from generation.validation_statique import ResultatValidationStatique, valider_code_genere
from validation_engine.cascade import VerdictCascade, evaluer_cascade


@dataclass(frozen=True)
class _ResultatValidationComplete:
    """Même chaîne validation statique → exécution → cascade que
    `generation.tentative_unique`, factorisée ici pour être appelée deux
    fois (code du Développeur/Debugger, puis code de l'Optimiseur)."""

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
    except Exception as erreur:  # le code généré peut lever n'importe quoi à l'exécution
        return _ResultatValidationComplete(validation, str(erreur), None)

    return _ResultatValidationComplete(validation, None, verdict)


def _creer_instance_exemple_defaut() -> dict:
    """Crée une petite instance par défaut (10 tâches, 5 ressources) pour le
    Benchmarker lorsqu'aucune instance exemple n'est fournie. Cette instance
    sera typiquement reconnue comme 'petite' et orientera vers CP-SAT."""
    return {
        "taches": [{"id": f"T{i}"} for i in range(1, 11)],
        "ressources": [{"id": f"R{i}"} for i in range(1, 6)],
        "contraintes": [
            {
                "type": "compatibilite_ressource_tache",
                "tache": f"T{i}",
                "ressource": f"R{((i - 1) % 5) + 1}",
                "duree": 30,
            }
            for i in range(1, 11)
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


@dataclass(frozen=True)
class ResultatPipelineMultiAgents:
    """Le devenir complet d'une tentative multi-agents — la sortie de
    chaque agent, plus le verdict final. `tests_generes` n'est **jamais**
    exécuté par ce pipeline (voir `generation.agents.testeur`) ; seul
    `verdict_cascade` fait autorité sur l'acceptation du solveur."""

    plan_orchestrateur: tuple[EtapePlan, ...]
    specification: str
    plan_technique: str
    algorithme_recommande: str  # Nouveau : algorithme choisi par Benchmarker
    justification_algorithme: str  # Nouveau : raison du choix
    parametres_algorithme: dict  # Nouveau : paramètres suggérés
    code_genere: str
    tests_generes: str
    revue: ResultatRevue
    code_corrige: str | None
    code_final: str
    validation_statique: ResultatValidationStatique
    erreur_execution: str | None
    verdict_cascade: VerdictCascade | None
    optimisation: ResultatOptimisation | None
    code_optimise_adopte: bool
    documentation: str | None

    @property
    def reussi(self) -> bool:
        return (
            self.validation_statique.valide
            and self.erreur_execution is None
            and self.verdict_cascade is not None
            and self.verdict_cascade.reussi
        )


def tenter_generation_multi_agents(
    appel_llm: AppelLLM, instance_exemple: dict | None = None
) -> ResultatPipelineMultiAgents:
    """Une tentative complète à travers les 10 agents — bornée : le Debugger
    n'intervient qu'une fois, jamais en boucle jusqu'à succès (§6.6, comme
    `tentative_unique.tenter_generation_unique`).

    Args:
        appel_llm: Client LLM
        instance_exemple: Instance T-R-C-O exemple (dict) pour le Benchmarker.
            Si None, utilise une petite instance par défaut (10 tâches).
    """
    plan = orchestrateur.planifier(appel_llm)
    analyse = analyste.analyser_mission(appel_llm)
    conception = architecte.concevoir_modele(appel_llm, analyse)

    # Nouveau : Benchmarker choisit l'algorithme optimal
    if instance_exemple is None:
        # Instance par défaut : petite (10 tâches) → CP-SAT
        instance_exemple = _creer_instance_exemple_defaut()

    resultat_benchmark = benchmarker.benchmarker_algorithmes(appel_llm, instance_exemple)
    algo = resultat_benchmark.recommandation.algorithme
    justification = resultat_benchmark.recommandation.raison
    parametres = resultat_benchmark.recommandation.parametres_suggeres

    # Générer code avec l'algorithme recommandé
    brut = generer_code_depuis_plan(
        appel_llm, conception.en_texte(), algorithme=algo, parametres=parametres
    )
    tests = testeur.generer_tests(appel_llm, brut.code_source)
    revue = reviewer.relire_code(appel_llm, brut.code_source)

    code_corrige: str | None = None
    code_candidat = brut.code_source
    if not revue.approuve:
        correction = debugger.corriger_code(appel_llm, code_candidat, revue.commentaires)
        code_corrige = correction.code_source
        code_candidat = code_corrige

    resultat = _valider_completement(code_candidat)

    if not resultat.reussi:
        return ResultatPipelineMultiAgents(
            plan_orchestrateur=plan.plan,
            specification=analyse.en_texte(),
            plan_technique=conception.en_texte(),
            algorithme_recommande=algo,
            justification_algorithme=justification,
            parametres_algorithme=parametres,
            code_genere=brut.code_source,
            tests_generes=tests.code_tests,
            revue=revue,
            code_corrige=code_corrige,
            code_final=code_candidat,
            validation_statique=resultat.validation_statique,
            erreur_execution=resultat.erreur_execution,
            verdict_cascade=resultat.verdict_cascade,
            optimisation=None,
            code_optimise_adopte=False,
            documentation=None,
        )

    # Cascade réussie : l'Optimiseur peut proposer une amélioration, mais
    # elle n'est adoptée que si elle repasse elle-même toute la validation —
    # jamais sur la seule parole de l'agent (voir generation/agents/optimiseur.py).
    optimisation = optimiseur.optimiser_code(appel_llm, code_candidat)
    code_final = code_candidat
    code_optimise_adopte = False
    resultat_final = resultat
    if optimisation.proposee and optimisation.code_source:
        resultat_opt = _valider_completement(optimisation.code_source)
        if resultat_opt.reussi:
            code_final = optimisation.code_source
            code_optimise_adopte = True
            resultat_final = resultat_opt

    doc = documentation.documenter_code(appel_llm, code_final)

    return ResultatPipelineMultiAgents(
        plan_orchestrateur=plan.plan,
        specification=analyse.en_texte(),
        plan_technique=conception.en_texte(),
        algorithme_recommande=algo,
        justification_algorithme=justification,
        parametres_algorithme=parametres,
        code_genere=brut.code_source,
        tests_generes=tests.code_tests,
        revue=revue,
        code_corrige=code_corrige,
        code_final=code_final,
        validation_statique=resultat_final.validation_statique,
        erreur_execution=resultat_final.erreur_execution,
        verdict_cascade=resultat_final.verdict_cascade,
        optimisation=optimisation,
        code_optimise_adopte=code_optimise_adopte,
        documentation=doc.en_texte(),
    )

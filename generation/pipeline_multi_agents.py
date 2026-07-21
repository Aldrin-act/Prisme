"""Pipeline de génération multi-agents (§5.6) — enchaîne les 10 agents de
`generation/agents/` : Orchestrateur → Analyste → **Benchmarker** → Architecte
→ Développeur → Testeur → Reviewer → [Debugger si besoin] → validation
complète → **[Boucle de réparation Étape 6]** → Optimiseur → Documentation.

**Benchmarker avant Architecte** (et non l'inverse) : il analyse une instance
exemple et recommande le meilleur algorithme (CP-SAT, GA, ACO, Tabu, etc.)
selon les caractéristiques (taille, contraintes, flexibilité) — il ne dépend
que de l'instance, jamais du plan de l'Architecte. L'Architecte reçoit cette
recommandation et conçoit une structure adaptée à *cet* algorithme (modèle
CP-SAT classique, ou encodage/opérateurs pour un algorithme alternatif) ; le
Développeur suit ce plan. Un algorithme non-CP-SAT est jugé par la cascade
avec une tolérance explicite sur le makespan et sans exiger l'affectation
tâche→ressource exacte des cas de référence — voir
`_parametres_cascade_pour_algorithme` ci-dessous et
`validation_engine/cascade.py` (`tolerance_relative`, `comparer_affectation`).

**Étape 6 implémentée** : Boucle de réparation limitée (max 3 tentatives) — si le
code généré échoue à l'exécution (erreur runtime), le Debugger est rappelé
automatiquement avec le message d'erreur pour corriger le code. La boucle s'arrête
en cas de succès, d'erreur de validation statique (non réparable), ou après 3
tentatives. Le Debugger intervient aussi une fois si le Reviewer rejette le code
initial. L'ordre d'exécution est câblé ici en Python, jamais décidé dynamiquement
par la réponse de l'Orchestrateur — voir sa docstring dans
`generation/agents/orchestrateur.py`.

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
from generation.agents.client_llm import AppelLLM, construire_appel_llm_pour_agent
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


# Seul CP-SAT est jugé à l'identique (exactitude requise) ; tout autre
# algorithme recommandé par le Benchmarker est approché par nature (§5.6,
# generation/prompts/generation_solveur.md) et n'a aucune raison de retomber
# exactement sur l'optimum du banc synthétique ni sur l'affectation
# tâche→ressource écrite à la main pour les cas de référence.
_ALGORITHMES_EXACTS = frozenset({"cp_sat"})
_TOLERANCE_MAKESPAN_ALGORITHME_APPROCHE = 0.10  # 10 % au-dessus de l'optimum/de la référence


def _parametres_cascade_pour_algorithme(algorithme: str) -> tuple[float, bool]:
    """Renvoie `(tolerance_relative, comparer_affectation)` à passer à
    `evaluer_cascade` selon l'algorithme choisi par le Benchmarker."""
    if algorithme in _ALGORITHMES_EXACTS:
        return 0.0, True
    return _TOLERANCE_MAKESPAN_ALGORITHME_APPROCHE, False


def _valider_completement(code: str, algorithme: str) -> _ResultatValidationComplete:
    validation = valider_code_genere(code)
    if not validation.valide:
        return _ResultatValidationComplete(validation, None, None)

    try:
        solveur = executer_code_genere(code)
    except ErreurExecutionGeneree as erreur:
        return _ResultatValidationComplete(validation, str(erreur), None)

    tolerance_relative, comparer_affectation = _parametres_cascade_pour_algorithme(algorithme)
    try:
        verdict = evaluer_cascade(solveur, tolerance_relative, comparer_affectation)
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
    appel_llm: AppelLLM | None = None, instance_exemple: dict | None = None
) -> ResultatPipelineMultiAgents:
    """Une tentative complète à travers les 10 agents — bornée : le Debugger
    n'intervient qu'une fois, jamais en boucle jusqu'à succès (§6.6, comme
    `tentative_unique.tenter_generation_unique`).

    Args:
        appel_llm: Client LLM (obsolète, ignoré — chaque agent utilise son fournisseur optimal).
            Conservé pour rétrocompatibilité uniquement.
        instance_exemple: Instance T-R-C-O exemple (dict) pour le Benchmarker.
            Si None, utilise une petite instance par défaut (10 tâches).

    Note:
        Depuis la configuration optimale par agent (config_fournisseurs.py), chaque
        agent utilise automatiquement le fournisseur LLM le mieux adapté à sa tâche.
    """
    # Chaque agent utilise son fournisseur optimal (config_fournisseurs.py)
    plan = orchestrateur.planifier(construire_appel_llm_pour_agent("orchestrateur"))
    analyse = analyste.analyser_mission(construire_appel_llm_pour_agent("analyste"))

    # Le Benchmarker choisit l'algorithme optimal AVANT l'Architecte : il ne
    # dépend que des caractéristiques de l'instance, jamais du plan technique,
    # et l'Architecte a besoin de savoir pour quel algorithme concevoir sa
    # structure (voir docstring du module).
    if instance_exemple is None:
        # Instance par défaut : petite (10 tâches) → CP-SAT
        instance_exemple = _creer_instance_exemple_defaut()

    resultat_benchmark = benchmarker.benchmarker_algorithmes(
        construire_appel_llm_pour_agent("benchmarker"), instance_exemple
    )
    algo = resultat_benchmark.recommandation.algorithme
    justification = resultat_benchmark.recommandation.raison
    parametres = resultat_benchmark.recommandation.parametres_suggeres

    conception = architecte.concevoir_modele(
        construire_appel_llm_pour_agent("architecte"), analyse, algorithme=algo, parametres=parametres
    )

    # Générer code avec l'algorithme recommandé
    brut = generer_code_depuis_plan(
        construire_appel_llm_pour_agent("generateur"),
        conception.en_texte(),
        algorithme=algo,
        parametres=parametres,
    )
    tests = testeur.generer_tests(construire_appel_llm_pour_agent("testeur"), brut.code_source)
    revue = reviewer.relire_code(construire_appel_llm_pour_agent("reviewer"), brut.code_source)

    code_corrige: str | None = None
    code_candidat = brut.code_source
    if not revue.approuve:
        correction = debugger.corriger_code(
            construire_appel_llm_pour_agent("debugger"), code_candidat, revue.commentaires
        )
        code_corrige = correction.code_source
        code_candidat = code_corrige

    # Boucle de réparation (Étape 6) - max 3 tentatives si erreur d'exécution
    # OU échec de la cascade (faisabilité/optimalité/fidélité) sans exception —
    # ce second cas (ex. contrainte dure seulement pénalisée dans la fitness
    # d'un algorithme non-CP-SAT au lieu d'être respectée par construction)
    # donnait auparavant un échec immédiat sans même essayer le Debugger.
    MAX_TENTATIVES_REPARATION = 3
    tentative = 0
    historique_corrections = []

    while tentative < MAX_TENTATIVES_REPARATION:
        resultat = _valider_completement(code_candidat, algo)

        # Succès ou échec de validation statique (non réparable) → sortie
        if resultat.reussi or not resultat.validation_statique.valide:
            break

        tentative += 1
        if tentative >= MAX_TENTATIVES_REPARATION:
            # Limite atteinte, on sort avec l'échec
            break

        if resultat.erreur_execution is not None:
            resume_echec = resultat.erreur_execution
            probleme = (
                f"Erreur d'exécution (tentative {tentative}/{MAX_TENTATIVES_REPARATION}) :\n\n"
                f"{resume_echec}\n\n"
                f"Code actuel a échoué à l'exécution. Analyse l'erreur et corrige le code."
            )
        else:
            # Pas d'erreur d'exécution, mais la cascade échoue quand même :
            # donner le détail par instance (quelle brique, pourquoi), jamais
            # un simple "ça a échoué".
            assert resultat.verdict_cascade is not None
            resume_echec = "\n".join(
                f"- {d.nom} [{d.brique_en_echec}] : {'; '.join(d.details)}"
                for d in resultat.verdict_cascade.echecs
            )
            probleme = (
                f"Échec de la cascade de validation (tentative {tentative}/{MAX_TENTATIVES_REPARATION}), "
                f"le code s'exécute sans erreur mais produit un planning incorrect :\n\n"
                f"{resume_echec}\n\n"
                f"Si la brique en échec est 'faisabilite' pour un algorithme non-CP-SAT : vérifie que "
                f"les contraintes dures (précédence, compatibilité ressource-tâche, non-chevauchement "
                f"d'une ressource) sont respectées par construction du planning (décodeur), jamais par "
                f"une simple pénalité dans une fitness/un score qui laisserait passer une violation. "
                f"Si c'est 'optimalite' ou 'fidelite' : améliore la qualité du planning produit."
            )

        # Appeler le Debugger pour corriger
        correction = debugger.corriger_code(
            construire_appel_llm_pour_agent("debugger"), code_candidat, probleme
        )

        historique_corrections.append({
            "tentative": tentative,
            "erreur": resume_echec[:200],
            "code_avant": code_candidat[:200],
            "cause": correction.cause,
        })

        code_candidat = correction.code_source
        code_corrige = code_candidat  # Mémoriser la dernière correction

    # resultat contient maintenant le dernier résultat de validation
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
    optimisation = optimiseur.optimiser_code(construire_appel_llm_pour_agent("optimiseur"), code_candidat)
    code_final = code_candidat
    code_optimise_adopte = False
    resultat_final = resultat
    if optimisation.proposee and optimisation.code_source:
        resultat_opt = _valider_completement(optimisation.code_source, algo)
        if resultat_opt.reussi:
            code_final = optimisation.code_source
            code_optimise_adopte = True
            resultat_final = resultat_opt

    doc = documentation.documenter_code(construire_appel_llm_pour_agent("documentation"), code_final)

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

"""Agent Debugger (pipeline multi-agents, §5.6) — corrige le code face à un
problème précis (revue défavorable, échec de validation statique,
d'exécution ou de cascade). Appelé jusqu'à `generation.graph.MAX_TENTATIVES_REPARATION`
fois par tentative de génération (boucle de réparation bornée, Étape 6). Doit
rester algorithme-agnostique comme l'Architecte/le Développeur : le code à
corriger peut implémenter n'importe quel algorithme choisi par le Benchmarker
(tabou, recuit simulé, génétique...).

`corriger_code` (le chemin historique, cascade/reviewer) suppose toujours que
le solveur a tort — vrai par construction, la cascade juge contre une vérité
terrain déterministe (banc synthétique, cas de référence), jamais contre du
texte produit par un LLM. `corriger_solveur_ou_tests` (§6.6bis) sert
uniquement le chemin déclenché par un échec des tests sandbox de l'agent
Testeur : ces tests-là sont eux-mêmes écrits par un LLM et peuvent être
fautifs, donc ce second chemin laisse le Debugger désigner et corriger l'un
des deux modules (solveur ou tests), jamais une simple supposition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.base import ErreurReponseAgentInvalide, charger_mission  # noqa: F401 — réexporté (tests)
from generation.agents.client_llm import invoquer_agent_structure
from generation.agents.memory import AUCUNE_TENTATIVE

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "debugger.md"
CHEMIN_PROMPT_TESTS_SANDBOX = Path(__file__).resolve().parents[1] / "prompts" / "debugger_tests_sandbox.md"

_PROMPT_SYSTEME = (
    "Tu es un développeur Python expert en débogage de modèles d'optimisation combinatoire "
    "(métaheuristiques d'ordonnancement — génétique, ACO, recuit simulé, "
    "tabou, dispatching). Tu réponds toujours en JSON strict, jamais en texte libre."
)


class _SchemaCorrection(BaseModel):
    code: str = Field(description="Module Python corrigé, complet.")
    # Aide au diagnostic/audit (pourquoi le Debugger a changé le code) —
    # jamais bloquant si le LLM l'omet malgré la consigne.
    cause: str | None = Field(default=None, description="Cause identifiée du problème.")
    correctif: str | None = Field(default=None, description="Ce qui a été modifié dans le code, en une phrase.")


@dataclass(frozen=True)
class ResultatCorrection:
    reponse_brute: str
    code_source: str
    cause: str
    correctif: str = ""


def _contexte_generation(plan_technique: str, algorithme: str | None) -> str:
    """Plan de l'Architecte + algorithme du Benchmarker, pour le Debugger — sans eux, il ne
    pouvait ni vérifier « n'utilise jamais un autre algorithme que celui du plan » (mission
    commune), ni juger un test « au vu du plan technique » (`debugger_tests_sandbox.md`)."""
    algo = algorithme or "non précisé"
    plan = plan_technique or "non fourni"
    return (
        f"Algorithme imposé : **{algo}** — ne change jamais d'algorithme en corrigeant "
        f"(la validation applique une tolérance propre à cet algorithme).\n\n{plan}"
    )


def corriger_code(
    modele: BaseChatModel,
    code_source: str,
    probleme: str,
    *,
    historique: str = "",
    plan_technique: str = "",
    algorithme: str | None = None,
) -> ResultatCorrection:
    """`historique` : résumé des tentatives de correction précédentes DE
    CETTE MÊME génération (voir `generation/graph.py::_noeud_debugger`) —
    mémoire bornée à la boucle de réparation en cours (jamais persistée
    au-delà, jamais partagée entre deux instances/générations différentes),
    pour éviter de rejouer un correctif déjà tenté et déjà en échec. Passée
    directement en contexte de prompt plutôt que via un outil : contrairement
    au registre de l'Analyste ou à la recherche web du Benchmarker, cette
    information n'a rien d'externe — `EtatGeneration` la connaît déjà en
    entier avant même l'appel, aucune requête à faire pour l'obtenir."""
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(
        mission=charger_mission(),
        contexte_generation=_contexte_generation(plan_technique, algorithme),
        code=code_source,
        probleme=probleme,
        historique=historique or AUCUNE_TENTATIVE,
    )

    donnees, reponse_brute = invoquer_agent_structure(
        modele, _SchemaCorrection, [SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)]
    )
    return ResultatCorrection(
        reponse_brute=reponse_brute,
        code_source=donnees.code,
        cause=donnees.cause or "non précisée",
        correctif=donnees.correctif or "",
    )


class _SchemaCorrectionTestsSandbox(BaseModel):
    cible: Literal["solveur", "tests"] = Field(
        description="Lequel des deux modules ci-dessous a réellement été corrigé."
    )
    code: str = Field(description="Module Python du solveur, corrigé ou inchangé, complet.")
    tests: str = Field(description="Module de tests, corrigé ou inchangé, complet.")
    cause: str | None = Field(default=None, description="Cause identifiée du problème.")
    correctif: str | None = Field(default=None, description="Ce qui a été modifié, en une phrase.")


@dataclass(frozen=True)
class ResultatCorrectionTestsSandbox:
    reponse_brute: str
    cible: Literal["solveur", "tests"]
    code_source: str
    tests_source: str
    cause: str
    correctif: str = ""


def corriger_solveur_ou_tests(
    modele: BaseChatModel,
    code_source: str,
    code_tests: str,
    probleme: str,
    *,
    historique: str = "",
    plan_technique: str = "",
    algorithme: str | None = None,
) -> ResultatCorrectionTestsSandbox:
    """Chemin dédié aux échecs de tests sandbox (§6.6bis, voir docstring
    module) : contrairement à `corriger_code`, le Debugger reçoit aussi le
    module de tests et doit désigner lequel des deux est réellement fautif —
    jamais les deux à la fois sauf certitude (voir
    `prompts/debugger_tests_sandbox.md`). `historique` : voir `corriger_code`."""
    gabarit = CHEMIN_PROMPT_TESTS_SANDBOX.read_text(encoding="utf-8")
    prompt = gabarit.format(
        mission=charger_mission(),
        contexte_generation=_contexte_generation(plan_technique, algorithme),
        code=code_source,
        tests=code_tests,
        probleme=probleme,
        historique=historique or AUCUNE_TENTATIVE,
    )

    messages = [SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)]
    donnees, reponse_brute = invoquer_agent_structure(modele, _SchemaCorrectionTestsSandbox, messages)
    return ResultatCorrectionTestsSandbox(
        reponse_brute=reponse_brute,
        cible=donnees.cible,
        code_source=donnees.code,
        tests_source=donnees.tests,
        cause=donnees.cause or "non précisée",
        correctif=donnees.correctif or "",
    )

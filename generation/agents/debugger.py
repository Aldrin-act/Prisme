"""Agent Debugger (pipeline multi-agents, §5.6) — corrige le code face à un
problème précis (revue défavorable, échec de validation statique,
d'exécution ou de cascade). Appelé jusqu'à `generation.graph.MAX_TENTATIVES_REPARATION`
fois par tentative de génération (boucle de réparation bornée, Étape 6). Doit
rester algorithme-agnostique comme l'Architecte/le Développeur : le code à
corriger peut implémenter n'importe quel algorithme choisi par le Benchmarker
(cp_sat ou une heuristique), jamais uniquement CP-SAT."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.base import ErreurReponseAgentInvalide, charger_mission, extraire_texte_brut
from generation.agents.client_llm import _avec_retry, methode_sortie_structuree

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "debugger.md"

_PROMPT_SYSTEME = (
    "Tu es un développeur Python expert en débogage de modèles d'optimisation combinatoire "
    "(CP-SAT/OR-Tools et métaheuristiques d'ordonnancement — génétique, ACO, recuit simulé, "
    "tabou, dispatching). Tu réponds toujours en JSON strict, jamais en texte libre."
)


class _SchemaCorrection(BaseModel):
    code: str = Field(description="Module Python corrigé, complet.")
    # Aide au diagnostic/audit (pourquoi le Debugger a changé le code) —
    # jamais bloquant si le LLM l'omet malgré la consigne.
    cause: str | None = Field(default=None, description="Cause identifiée du problème.")


@dataclass(frozen=True)
class ResultatCorrection:
    reponse_brute: str
    code_source: str
    cause: str


def corriger_code(modele: BaseChatModel, code_source: str, probleme: str) -> ResultatCorrection:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), code=code_source, probleme=probleme)

    structure = modele.with_structured_output(
        _SchemaCorrection, include_raw=True, method=methode_sortie_structuree(modele)
    )
    sortie = _avec_retry(structure.invoke)([SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)])
    reponse_brute = extraire_texte_brut(sortie["raw"])
    if sortie["parsing_error"] is not None:
        raise ErreurReponseAgentInvalide(
            f"réponse non conforme au schéma reçue de l'agent : {reponse_brute[:200]!r}"
        ) from sortie["parsing_error"]

    donnees = sortie["parsed"]
    return ResultatCorrection(
        reponse_brute=reponse_brute,
        code_source=donnees.code,
        cause=donnees.cause or "non précisée",
    )

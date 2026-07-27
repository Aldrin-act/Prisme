"""Agent Orchestrateur (pipeline multi-agents, §5.6) — produit un plan
d'exécution JSON nommant l'instruction de chaque agent pour cette mission.

Rôle volontairement limité à la **trace/documentation** du déroulement, pas
à un vrai routage dynamique : la mission de PRISME est fixe (toujours
"écrire resoudre() pour le noyau minimal T-R-C-O"), il n'y a donc qu'un seul
ordre d'exécution valide. `generation.graph` appelle les 8
autres agents (dont le Benchmarker, exécuté avant l'Architecte) dans un
ordre câblé en Python, jamais décidé au vol par la réponse de cet agent — un
plan mal formé ou incomplet ne doit jamais faire échouer le pipeline. Voir
aussi generation/README.md."""

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

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "orchestrateur.md"

_PROMPT_SYSTEME = (
    "Tu es un chef de projet technique qui planifie le travail d'une équipe d'agents spécialisés. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


class _SchemaEtapePlan(BaseModel):
    agent: str = Field(description="Nom de l'agent responsable de cette étape.")
    instruction: str = Field(description="Instruction donnée à cet agent.")


class _SchemaOrchestration(BaseModel):
    plan: list[_SchemaEtapePlan] = Field(description="Plan d'exécution, une entrée par agent/étape.")


@dataclass(frozen=True)
class EtapePlan:
    agent: str
    instruction: str


@dataclass(frozen=True)
class ResultatOrchestration:
    reponse_brute: str
    plan: tuple[EtapePlan, ...]


def planifier(modele: BaseChatModel) -> ResultatOrchestration:
    prompt = CHEMIN_PROMPT.read_text(encoding="utf-8").format(mission=charger_mission())

    structure = modele.with_structured_output(
        _SchemaOrchestration, include_raw=True, method=methode_sortie_structuree(modele)
    )
    sortie = _avec_retry(structure.invoke)([SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)])
    reponse_brute = extraire_texte_brut(sortie["raw"])
    if sortie["parsing_error"] is not None:
        raise ErreurReponseAgentInvalide(
            f"réponse non conforme au schéma reçue de l'agent : {reponse_brute[:200]!r}"
        ) from sortie["parsing_error"]

    donnees = sortie["parsed"]
    plan = tuple(EtapePlan(agent=etape.agent, instruction=etape.instruction) for etape in donnees.plan)
    return ResultatOrchestration(reponse_brute=reponse_brute, plan=plan)

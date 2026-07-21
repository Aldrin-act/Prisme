"""Agent Orchestrateur (pipeline multi-agents, §5.6) — produit un plan
d'exécution JSON nommant l'instruction de chaque agent pour cette mission.

Rôle volontairement limité à la **trace/documentation** du déroulement, pas
à un vrai routage dynamique : la mission de PRISME est fixe (toujours
"écrire resoudre() pour le noyau minimal T-R-C-O"), il n'y a donc qu'un seul
ordre d'exécution valide. `generation.pipeline_multi_agents` appelle les 9
autres agents (dont le Benchmarker, exécuté avant l'Architecte) dans un
ordre câblé en Python, jamais décidé au vol par la réponse de cet agent — un
plan mal formé ou incomplet ne doit jamais faire échouer le pipeline. Voir
aussi generation/README.md."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission, extraire_json
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "orchestrateur.md"

_PROMPT_SYSTEME = (
    "Tu es un chef de projet technique qui planifie le travail d'une équipe d'agents spécialisés. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


@dataclass(frozen=True)
class EtapePlan:
    agent: str
    instruction: str


@dataclass(frozen=True)
class ResultatOrchestration:
    reponse_brute: str
    plan: tuple[EtapePlan, ...]


def planifier(appel_llm: AppelLLM) -> ResultatOrchestration:
    prompt = CHEMIN_PROMPT.read_text(encoding="utf-8").format(mission=charger_mission())
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    donnees = extraire_json(reponse)
    plan = tuple(EtapePlan(agent=etape["agent"], instruction=etape["instruction"]) for etape in donnees["plan"])
    return ResultatOrchestration(reponse_brute=reponse, plan=plan)

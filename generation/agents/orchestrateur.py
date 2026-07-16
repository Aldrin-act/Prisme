"""Agent Orchestrateur (pipeline multi-agents, §5.6) — produit un plan
d'exécution nommant l'instruction de chaque agent pour cette mission.

Rôle volontairement limité à la **trace/documentation** du déroulement, pas
à un vrai routage dynamique : la mission de PRISME est fixe (toujours
"écrire resoudre() pour le noyau minimal T-R-C-O"), il n'y a donc qu'un seul
ordre d'exécution valide. `generation.pipeline_multi_agents` appelle les 8
autres agents dans un ordre câblé en Python, jamais décidé au vol par la
réponse de cet agent — un plan mal formé ou incomplet ne doit jamais faire
échouer le pipeline. Voir aussi generation/README.md."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "orchestrateur.md"

_PROMPT_SYSTEME = "Tu es un chef de projet technique qui planifie le travail d'une équipe d'agents spécialisés."


@dataclass(frozen=True)
class ResultatOrchestration:
    reponse_brute: str
    plan: str


def planifier(appel_llm: AppelLLM) -> ResultatOrchestration:
    prompt = CHEMIN_PROMPT.read_text(encoding="utf-8").format(mission=charger_mission())
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    return ResultatOrchestration(reponse_brute=reponse, plan=reponse.strip())

"""Agent Documentation (pipeline multi-agents, §5.6) — rédige une courte
documentation du module final, destinée au canal d'audit (§5.1) : consultée
sur demande humaine explicite, jamais mêlée à la réponse opérationnelle."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "documentation.md"

_PROMPT_SYSTEME = "Tu es un rédacteur technique spécialisé en documentation de modèles d'optimisation."


@dataclass(frozen=True)
class ResultatDocumentation:
    reponse_brute: str
    documentation: str


def documenter_code(appel_llm: AppelLLM, code_source: str) -> ResultatDocumentation:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), code=code_source)
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    return ResultatDocumentation(reponse_brute=reponse, documentation=reponse.strip())

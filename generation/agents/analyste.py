"""Agent Analyste (pipeline multi-agents, §5.6) — transforme la mission en
spécification technique (entrées, sorties, contraintes à couvrir), sans
écrire de code. Première étape du pipeline, avant l'agent Architecte.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "analyste.md"

_PROMPT_SYSTEME = "Tu es un analyste technique spécialisé en ordonnancement (FJSP) et en modélisation."


@dataclass(frozen=True)
class ResultatAnalyse:
    reponse_brute: str
    specification: str


def analyser_mission(appel_llm: AppelLLM) -> ResultatAnalyse:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission())
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    return ResultatAnalyse(reponse_brute=reponse, specification=reponse.strip())

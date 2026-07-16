"""Agent Debugger (pipeline multi-agents, §5.6) — corrige le code face à un
problème précis (revue défavorable, échec de validation statique,
d'exécution ou de cascade). Une seule passe par tentative dans
`generation.pipeline_multi_agents` (borné, pas une boucle générale à
tentatives illimitées — celle-ci reste l'Étape 6, non construite)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission, extraire_bloc_code
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "debugger.md"

_PROMPT_SYSTEME = "Tu es un développeur Python expert en débogage de modèles d'optimisation combinatoire (CP-SAT)."


@dataclass(frozen=True)
class ResultatCorrection:
    reponse_brute: str
    code_source: str


def corriger_code(appel_llm: AppelLLM, code_source: str, probleme: str) -> ResultatCorrection:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), code=code_source, probleme=probleme)
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    return ResultatCorrection(reponse_brute=reponse, code_source=extraire_bloc_code(reponse))

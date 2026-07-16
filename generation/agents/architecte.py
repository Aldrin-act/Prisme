"""Agent Architecte (pipeline multi-agents, §5.6) — planifie la structure
interne du module CP-SAT (variables, contraintes, fonctions internes
éventuelles) à partir de la spécification de l'agent Analyste. Le contrat
impose un seul module/une seule fonction publique `resoudre()` : pas de
découpage en plusieurs fichiers, contrairement à un agent architecte
"logiciel" généraliste — voir le prompt pour cette adaptation explicite.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "architecte.md"

_PROMPT_SYSTEME = "Tu es un architecte logiciel spécialisé en modélisation de contraintes (CP-SAT, OR-Tools)."


@dataclass(frozen=True)
class ResultatConception:
    reponse_brute: str
    plan_technique: str


def concevoir_modele(appel_llm: AppelLLM, specification: str) -> ResultatConception:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), specification=specification)
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    return ResultatConception(reponse_brute=reponse, plan_technique=reponse.strip())

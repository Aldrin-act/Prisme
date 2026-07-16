"""Agent Optimiseur (pipeline multi-agents, §5.6) — propose une amélioration
sur du code déjà validé par la cascade. `generation.pipeline_multi_agents`
ne l'adopte que si le code optimisé repasse lui-même intégralement la
validation statique, l'exécution et la cascade — jamais en confiance
aveugle sur la seule parole de l'agent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission, extraire_bloc_code
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "optimiseur.md"

_PROMPT_SYSTEME = "Tu es un ingénieur performance spécialisé en modèles CP-SAT et en code Python sobre."

_MARQUEUR_PROPOSEE = "OPTIMISATION: PROPOSEE"


@dataclass(frozen=True)
class ResultatOptimisation:
    reponse_brute: str
    proposee: bool
    code_source: str | None
    notes: str


def optimiser_code(appel_llm: AppelLLM, code_source: str) -> ResultatOptimisation:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), code=code_source)
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)

    premiere_ligne, _, reste = reponse.strip().partition("\n")
    proposee = _MARQUEUR_PROPOSEE in premiere_ligne
    if not proposee:
        return ResultatOptimisation(reponse_brute=reponse, proposee=False, code_source=None, notes=reste.strip())

    code_optimise = extraire_bloc_code(reste)
    return ResultatOptimisation(
        reponse_brute=reponse, proposee=True, code_source=code_optimise, notes=reste.strip()
    )

"""Agent Optimiseur — propose une amélioration sur du code déjà validé par la
cascade. N'est plus appelé par le pipeline actif (`generation/graph.py`,
voir son docstring) — orphelin, conservé tel quel. Un appelant ne devrait
adopter le code optimisé que s'il repasse lui-même intégralement la
validation statique, l'exécution et la cascade — jamais en confiance
aveugle sur la seule parole de l'agent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission, extraire_json
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "optimiseur.md"

_PROMPT_SYSTEME = (
    "Tu es un ingénieur performance spécialisé en modèles CP-SAT et en code Python sobre. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


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
    donnees = extraire_json(reponse)
    proposee = bool(donnees.get("optimisation_proposee", False))
    return ResultatOptimisation(
        reponse_brute=reponse,
        proposee=proposee,
        code_source=donnees.get("code") if proposee else None,
        notes=donnees.get("notes", ""),
    )

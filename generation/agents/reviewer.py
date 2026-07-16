"""Agent Reviewer (pipeline multi-agents, §5.6) — relit le code avant la
validation automatique. Son verdict est consultatif : c'est la cascade
(`validation_engine/cascade.py`) qui tranche réellement l'acceptation d'un
solveur, jamais cet avis seul — voir `generation.pipeline_multi_agents`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission, extraire_json
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "reviewer.md"

_PROMPT_SYSTEME = (
    "Tu es un relecteur de code Python expert en optimisation combinatoire et en revue de sécurité. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)

_VERDICT_APPROUVE = "APPROUVE"


@dataclass(frozen=True)
class ResultatRevue:
    reponse_brute: str
    approuve: bool
    commentaires: str


def relire_code(appel_llm: AppelLLM, code_source: str) -> ResultatRevue:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), code=code_source)
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    donnees = extraire_json(reponse)
    # Défaut prudent : toute valeur autre que "APPROUVE" (y compris une
    # valeur inattendue, un LLM peu fidèle au format) est traitée comme "à
    # corriger" plutôt que d'approuver à tort — la cascade reste de toute
    # façon l'arbitre final.
    approuve = donnees.get("verdict") == _VERDICT_APPROUVE
    return ResultatRevue(reponse_brute=reponse, approuve=approuve, commentaires=donnees.get("commentaires", ""))

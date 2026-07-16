"""Agent Reviewer (pipeline multi-agents, §5.6) — relit le code avant la
validation automatique. Son verdict est consultatif : c'est la cascade
(`validation_engine/cascade.py`) qui tranche réellement l'acceptation d'un
solveur, jamais cet avis seul — voir `generation.pipeline_multi_agents`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "reviewer.md"

_PROMPT_SYSTEME = "Tu es un relecteur de code Python expert en optimisation combinatoire et en revue de sécurité."

_MARQUEUR_APPROUVE = "VERDICT: APPROUVE"
_MARQUEUR_A_CORRIGER = "VERDICT: A_CORRIGER"


@dataclass(frozen=True)
class ResultatRevue:
    reponse_brute: str
    approuve: bool
    commentaires: str


def relire_code(appel_llm: AppelLLM, code_source: str) -> ResultatRevue:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), code=code_source)
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)

    premiere_ligne, _, reste = reponse.strip().partition("\n")
    # Défaut prudent : si le marqueur attendu est absent (LLM peu fidèle au
    # format demandé), on traite comme "à corriger" plutôt que d'approuver
    # à tort — la cascade reste de toute façon l'arbitre final.
    approuve = _MARQUEUR_APPROUVE in premiere_ligne and _MARQUEUR_A_CORRIGER not in premiere_ligne
    return ResultatRevue(reponse_brute=reponse, approuve=approuve, commentaires=reste.strip())

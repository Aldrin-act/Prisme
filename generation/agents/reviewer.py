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
    problemes: tuple[str, ...]

    @property
    def commentaires(self) -> str:
        """Rendu texte des problèmes relevés, pour les appelants historiques
        (scripts/, generation/loop.py, generation/pipeline_avec_boucle.py)
        qui consomment une chaîne plutôt que la liste structurée `problemes`
        — la migration du prompt Reviewer vers un format liste (voir
        prompts/reviewer.md) n'a pas besoin de tous les mettre à jour."""
        if not self.problemes:
            return "aucun problème relevé"
        return "\n".join(f"- {probleme}" for probleme in self.problemes)


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
    problemes = tuple(donnees.get("problemes") or [])
    return ResultatRevue(reponse_brute=reponse, approuve=approuve, problemes=problemes)

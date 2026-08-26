"""Agent Reviewer (pipeline multi-agents, §5.6) — relit le code avant la
validation automatique. Son verdict est consultatif : c'est la cascade
(`validation_engine/cascade.py`) qui tranche réellement l'acceptation d'un
solveur, jamais cet avis seul.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.base import ErreurReponseAgentInvalide, charger_mission  # noqa: F401 — réexporté (tests)
from generation.agents.client_llm import invoquer_agent_structure

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "reviewer.md"

_PROMPT_SYSTEME = (
    "Tu es un relecteur de code Python expert en optimisation combinatoire et en revue de sécurité. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)

_VERDICT_APPROUVE = "APPROUVE"


class _SchemaRevue(BaseModel):
    # Optionnel, comme l'ancien `donnees.get("verdict")` : une réponse qui
    # omet le champ (LLM peu fidèle au format) ne doit jamais faire échouer
    # la validation du schéma — elle doit seulement être traitée comme
    # "à corriger" (voir `relire_code` ci-dessous), pas comme un échec de
    # parsing distinct.
    verdict: str | None = Field(default=None, description='"APPROUVE" ou toute autre valeur si à corriger.')
    problemes: list[str] | None = Field(default=None, description="Problèmes relevés, le cas échéant.")


@dataclass(frozen=True)
class ResultatRevue:
    reponse_brute: str
    approuve: bool
    problemes: tuple[str, ...]

    @property
    def commentaires(self) -> str:
        """Rendu texte des problèmes relevés, pour les appelants historiques
        (scripts/, generation/graph.py) qui consomment une chaîne plutôt que
        la liste structurée `problemes` — la migration du prompt Reviewer
        vers un format liste (voir prompts/reviewer.md) n'a pas besoin de
        tous les mettre à jour."""
        if not self.problemes:
            return "aucun problème relevé"
        return "\n".join(f"- {probleme}" for probleme in self.problemes)


def relire_code(modele: BaseChatModel, code_source: str) -> ResultatRevue:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), code=code_source)

    donnees, reponse_brute = invoquer_agent_structure(
        modele, _SchemaRevue, [SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)]
    )
    # Défaut prudent : toute valeur autre que "APPROUVE" (y compris une
    # valeur absente/inattendue, un LLM peu fidèle au format) est traitée
    # comme "à corriger" plutôt que d'approuver à tort — la cascade reste de
    # toute façon l'arbitre final.
    approuve = donnees.verdict == _VERDICT_APPROUVE
    problemes = tuple(donnees.problemes or [])
    return ResultatRevue(reponse_brute=reponse_brute, approuve=approuve, problemes=problemes)

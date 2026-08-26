"""Agent Documentation (pipeline multi-agents, §5.6) — rédige une courte
documentation du module final, destinée au canal d'audit (§5.1) : consultée
sur demande humaine explicite, jamais mêlée à la réponse opérationnelle."""

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

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "documentation.md"

_PROMPT_SYSTEME = (
    "Tu es un rédacteur technique spécialisé en documentation de modèles d'optimisation. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


class _SchemaDocumentation(BaseModel):
    resume: str = Field(description="Résumé du fonctionnement du solveur.")
    limites_connues: str = Field(description="Limites connues du solveur (échelle, hypothèses...).")


@dataclass(frozen=True)
class ResultatDocumentation:
    reponse_brute: str
    resume: str
    limites_connues: str

    def en_texte(self) -> str:
        return f"{self.resume}\n\nLimites connues : {self.limites_connues}"


def documenter_code(modele: BaseChatModel, code_source: str) -> ResultatDocumentation:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), code=code_source)

    donnees, reponse_brute = invoquer_agent_structure(
        modele, _SchemaDocumentation, [SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)]
    )
    return ResultatDocumentation(
        reponse_brute=reponse_brute,
        resume=donnees.resume,
        limites_connues=donnees.limites_connues,
    )

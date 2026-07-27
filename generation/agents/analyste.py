"""Agent Analyste (pipeline multi-agents, §5.6) — transforme la mission en
spécification technique structurée (entrées, sorties, contraintes à
couvrir), sans écrire de code. Première étape du pipeline, avant l'agent
Architecte.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.base import ErreurReponseAgentInvalide, charger_mission, extraire_texte_brut
from generation.agents.client_llm import _avec_retry, methode_sortie_structuree

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "analyste.md"

_PROMPT_SYSTEME = (
    "Tu es un analyste technique spécialisé en ordonnancement (FJSP) et en modélisation. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


class _SchemaAnalyse(BaseModel):
    entrees: str = Field(description="Description des données d'entrée de la mission.")
    sorties: str = Field(description="Description du format de sortie attendu.")
    contraintes_a_couvrir: list[str] = Field(description="Liste des contraintes à modéliser.")


@dataclass(frozen=True)
class ResultatAnalyse:
    reponse_brute: str
    entrees: str
    sorties: str
    contraintes_a_couvrir: tuple[str, ...]

    def en_texte(self) -> str:
        """Rendu lisible, pour l'injecter dans le prompt de l'agent Architecte."""
        contraintes = "\n".join(f"- {c}" for c in self.contraintes_a_couvrir)
        return (
            f"### Entrées\n{self.entrees}\n\n"
            f"### Sorties\n{self.sorties}\n\n"
            f"### Contraintes à couvrir\n{contraintes}"
        )


def analyser_mission(modele: BaseChatModel) -> ResultatAnalyse:
    prompt = CHEMIN_PROMPT.read_text(encoding="utf-8").format(mission=charger_mission())

    structure = modele.with_structured_output(
        _SchemaAnalyse, include_raw=True, method=methode_sortie_structuree(modele)
    )
    sortie = _avec_retry(structure.invoke)([SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)])
    reponse_brute = extraire_texte_brut(sortie["raw"])
    if sortie["parsing_error"] is not None:
        raise ErreurReponseAgentInvalide(
            f"réponse non conforme au schéma reçue de l'agent : {reponse_brute[:200]!r}"
        ) from sortie["parsing_error"]

    donnees = sortie["parsed"]
    return ResultatAnalyse(
        reponse_brute=reponse_brute,
        entrees=donnees.entrees,
        sorties=donnees.sorties,
        contraintes_a_couvrir=tuple(donnees.contraintes_a_couvrir),
    )

"""Agent LLM de supervision (§2, MT7) — mirroir exact du pattern Benchmarker
(`generation/agents/benchmarker.py`) : des faits calculés par du Python
déterministe (`supervision/detecteurs.py`) sont injectés dans un prompt, le
LLM se contente de les prioriser et de les rédiger en langage naturel —
jamais de détecter quoi que ce soit lui-même.

Vit en dehors de `generation/agents/` car ce n'est pas un nœud du
`StateGraph` de génération (`generation/graph.py`) — même précédent que
`adapters/agent_comprehension/` : un agent autonome qui réutilise
`generation.agents.base`/`generation.agents.client_llm`, prompt local au
package plutôt que dans `generation/prompts/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.base import ErreurReponseAgentInvalide, extraire_texte_brut
from generation.agents.client_llm import _avec_retry, methode_sortie_structuree

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parent / "prompts" / "supervision.md"

_PROMPT_SYSTEME = (
    "Tu es un expert en supervision de systèmes d'ordonnancement industriel. "
    "Tu ne détectes rien toi-même : tu priorises et rédiges en langage naturel des faits "
    "déjà détectés par un module déterministe. Tu réponds toujours en JSON strict."
)


class _SchemaPropositionUnitaire(BaseModel):
    reference: str = Field(description="Identifiant du fait, recopié tel quel depuis la liste fournie.")
    resume: str = Field(description="Résumé clair en une ou deux phrases, destiné à un humain non technicien.")
    priorite: Literal["haute", "moyenne", "basse"] = Field(default="moyenne")


class _SchemaSupervision(BaseModel):
    propositions: list[_SchemaPropositionUnitaire] = Field(default_factory=list)


@dataclass(frozen=True)
class FaitSignal:
    """Un signal détecté par `supervision/detecteurs.py`, réduit à ce dont
    l'agent LLM a besoin : une référence stable (que le LLM doit recopier
    telle quelle, jamais reformuler) et une description factuelle."""

    reference: str  # "{type_signal}:{instance_id}" — clé stable, voir supervision/orchestrateur.py
    description: str


@dataclass(frozen=True)
class PropositionLLM:
    reference: str
    resume: str
    priorite: Literal["haute", "moyenne", "basse"]


@dataclass(frozen=True)
class ResultatSupervision:
    reponse_brute: str
    propositions: tuple[PropositionLLM, ...]


def _formater_faits(faits: tuple[FaitSignal, ...]) -> str:
    return "\n".join(f"- `{fait.reference}` : {fait.description}" for fait in faits)


def proposer_actions(modele: BaseChatModel, faits: tuple[FaitSignal, ...]) -> ResultatSupervision:
    """Priorise et rédige une proposition par fait. N'appelle jamais le LLM
    sur une liste vide — à la charge de l'appelant (`supervision/orchestrateur.py`)
    de ne pas invoquer cette fonction s'il n'y a rien de nouveau à proposer."""
    prompt_template = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = prompt_template.format(faits=_formater_faits(faits))

    structure = modele.with_structured_output(
        _SchemaSupervision, include_raw=True, method=methode_sortie_structuree(modele)
    )
    sortie = _avec_retry(structure.invoke)([SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)])
    reponse_brute = extraire_texte_brut(sortie["raw"])
    if sortie["parsing_error"] is not None:
        raise ErreurReponseAgentInvalide(
            f"réponse non conforme au schéma reçue de l'agent : {reponse_brute[:200]!r}"
        ) from sortie["parsing_error"]

    donnees = sortie["parsed"]
    propositions = tuple(
        PropositionLLM(reference=p.reference, resume=p.resume, priorite=p.priorite) for p in donnees.propositions
    )
    return ResultatSupervision(reponse_brute=reponse_brute, propositions=propositions)

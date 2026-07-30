"""Agent Optimiseur — propose une amélioration sur du code déjà validé par la
cascade. N'est plus appelé par le pipeline actif (`generation/graph.py`,
voir son docstring) — orphelin, conservé tel quel. Un appelant ne devrait
adopter le code optimisé que s'il repasse lui-même intégralement la
validation statique, l'exécution et la cascade — jamais en confiance
aveugle sur la seule parole de l'agent."""

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

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "optimiseur.md"

_PROMPT_SYSTEME = (
    # CP-SAT-only, jamais mis à jour pour être algorithme-agnostique comme
    # l'Architecte/le Développeur/le Debugger — sans conséquence tant que cet
    # agent reste orphelin (non appelé par generation/graph.py, voir le
    # docstring du module).
    "Tu es un ingénieur performance spécialisé en modèles CP-SAT et en code Python sobre. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


class _SchemaOptimisation(BaseModel):
    optimisation_proposee: bool = Field(description="True si une optimisation pertinente a été trouvée.")
    code: str | None = Field(default=None, description="Code optimisé complet, si une optimisation est proposée.")
    notes: str = Field(default="", description="Explication de l'optimisation, ou pourquoi aucune n'est proposée.")


@dataclass(frozen=True)
class ResultatOptimisation:
    reponse_brute: str
    proposee: bool
    code_source: str | None
    notes: str


def optimiser_code(modele: BaseChatModel, code_source: str) -> ResultatOptimisation:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), code=code_source)

    structure = modele.with_structured_output(
        _SchemaOptimisation, include_raw=True, method=methode_sortie_structuree(modele)
    )
    sortie = _avec_retry(structure.invoke)([SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)])
    reponse_brute = extraire_texte_brut(sortie["raw"])
    if sortie["parsing_error"] is not None:
        raise ErreurReponseAgentInvalide(
            f"réponse non conforme au schéma reçue de l'agent : {reponse_brute[:200]!r}"
        ) from sortie["parsing_error"]

    donnees = sortie["parsed"]
    return ResultatOptimisation(
        reponse_brute=reponse_brute,
        proposee=donnees.optimisation_proposee,
        code_source=donnees.code if donnees.optimisation_proposee else None,
        notes=donnees.notes,
    )

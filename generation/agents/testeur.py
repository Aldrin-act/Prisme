"""Agent Testeur (pipeline multi-agents, §5.6) — génère des tests pytest
complémentaires à la cascade de validation (`validation_engine/cascade.py`).

Ces tests sont exécutés une seule fois, en meilleur effort, dans le bac à
sable Docker après le succès de la boucle de réparation
(`generation/graph.py::_noeud_test_sandbox`,
`sandbox/runner.py::executer_tests_dans_sandbox`) — jamais un critère
d'acceptation du solveur, seule la cascade de validation l'est. Canal
d'audit pur : leur échec (ou l'indisponibilité du sandbox) n'affecte jamais
`boucle_reussie` ni la réponse de `/generation/{instance_id}`.
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

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "testeur.md"

_PROMPT_SYSTEME = (
    "Tu es un ingénieur qualité spécialisé en tests de solveurs d'optimisation combinatoire. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


class _SchemaTests(BaseModel):
    code_tests: str = Field(description="Module de tests pytest complémentaires.")


@dataclass(frozen=True)
class ResultatTests:
    reponse_brute: str
    code_tests: str


def generer_tests(modele: BaseChatModel, code_source: str) -> ResultatTests:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), code=code_source)

    donnees, reponse_brute = invoquer_agent_structure(
        modele, _SchemaTests, [SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)]
    )
    return ResultatTests(reponse_brute=reponse_brute, code_tests=donnees.code_tests)

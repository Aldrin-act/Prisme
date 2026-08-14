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

from generation.agents.base import ErreurReponseAgentInvalide, charger_mission, extraire_texte_brut
from generation.agents.client_llm import _avec_retry, methode_sortie_structuree

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

    structure = modele.with_structured_output(
        _SchemaTests, include_raw=True, method=methode_sortie_structuree(modele)
    )
    sortie = _avec_retry(structure.invoke)([SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)])
    reponse_brute = extraire_texte_brut(sortie["raw"])
    if sortie["parsing_error"] is not None:
        raise ErreurReponseAgentInvalide(
            f"réponse non conforme au schéma reçue de l'agent : {reponse_brute[:200]!r}"
        ) from sortie["parsing_error"]

    donnees = sortie["parsed"]
    return ResultatTests(reponse_brute=reponse_brute, code_tests=donnees.code_tests)

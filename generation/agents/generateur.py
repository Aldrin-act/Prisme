"""Agent Développeur (§5.6) — écrit le code à partir de la mission (et, dans
le pipeline multi-agents, du plan technique de l'agent Architecte). Deux
formats de sortie coexistent :

- `generer_code_solveur` — mode simple (Étape 4, tir unique, historique) :
  un bloc de code Python nu, format hérité de `generation.tentative_unique`.
  Un simple `.invoke()`/`extraire_bloc_code`, sans sortie structurée (pas de
  JSON à parser dans ce mode).
- `generer_code_depuis_plan` — mode multi-agents
  (`generation.graph`) : sortie structurée `{"code": "..."}`,
  comme les autres agents du pipeline.

Le contrat de sortie attendu dans les deux cas — une fonction
`resoudre(instance) -> Planning | None` (`Callable[[InstanceTRCO], Planning | None]`,
§5.6, §6.2) — permet au code produit de se brancher directement dans
`validation_engine.cascade.evaluer_cascade` sans adaptation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.base import (
    ErreurReponseAgentInvalide,
    charger_mission,
    extraire_bloc_code,
    extraire_texte_brut,
)
from generation.agents.client_llm import _avec_retry, methode_sortie_structuree

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT_DEPUIS_PLAN = Path(__file__).resolve().parents[1] / "prompts" / "developpeur.md"

_PROMPT_SYSTEME = "Tu es un générateur de code Python expert en optimisation combinatoire."
_PROMPT_SYSTEME_JSON = _PROMPT_SYSTEME + " Tu réponds toujours en JSON strict, jamais en texte libre."

_ADDENDUM_FORMAT_BLOC_CODE = (
    "\n## Format de réponse\n\n"
    "Réponds avec un unique bloc de code Python (` ```python ... ``` `), sans "
    "texte avant ni après. Aucune explication, aucun commentaire de conversation.\n"
)


class _SchemaGenerationCode(BaseModel):
    code: str = Field(description="Module Python complet, une seule fonction publique resoudre().")


@dataclass(frozen=True)
class ResultatGenerationBrute:
    """La réponse brute du LLM et le code Python qui en a été extrait."""

    reponse_brute: str
    code_source: str


def generer_code_solveur(modele: BaseChatModel) -> ResultatGenerationBrute:
    """Un seul essai de génération, sans plan technique préalable (Étape 4,
    tir unique) : construit le prompt à partir de la seule mission, appelle
    le LLM, extrait le code. Ne valide ni n'exécute rien — voir
    `generation.validation_statique` et `generation.executer`.
    """
    prompt = charger_mission() + _ADDENDUM_FORMAT_BLOC_CODE
    reponse = _avec_retry(modele.invoke)([SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)])
    reponse_brute = extraire_texte_brut(reponse)
    return ResultatGenerationBrute(reponse_brute=reponse_brute, code_source=extraire_bloc_code(reponse_brute))


def generer_code_depuis_plan(
    modele: BaseChatModel,
    plan_technique: str,
    algorithme: str | None = None,
    parametres: dict | None = None,
) -> ResultatGenerationBrute:
    """Variante utilisée par le pipeline multi-agents : écrit le code en
    suivant le plan produit par l'agent Architecte plutôt que la seule
    mission brute, et répond en sortie structurée comme le reste du pipeline.

    Args:
        modele: `BaseChatModel` LangChain (voir `client_llm.construire_modele_pour_agent`).
        plan_technique: Plan de l'agent Architecte
        algorithme: Algorithme recommandé par le Benchmarker (ex: "cp_sat", "genetic")
        parametres: Paramètres suggérés pour l'algorithme
    """
    gabarit = CHEMIN_PROMPT_DEPUIS_PLAN.read_text(encoding="utf-8")

    # Construire la section algorithme si fournie
    section_algorithme = ""
    if algorithme:
        section_algorithme = "\n## Algorithme recommandé par le Benchmarker\n\n"
        section_algorithme += "L'agent Benchmarker a analysé les caractéristiques de "
        section_algorithme += f"l'instance et recommande d'utiliser : **{algorithme.upper()}**\n\n"

        if parametres:
            section_algorithme += "Paramètres suggérés :\n"
            for param, valeur in parametres.items():
                section_algorithme += f"- {param}: {valeur}\n"
            section_algorithme += "\n"

        section_algorithme += "Implémente le solveur avec cet algorithme.\n"

    prompt = gabarit.format(
        mission=charger_mission(),
        plan_technique=plan_technique + section_algorithme,
    )

    structure = modele.with_structured_output(
        _SchemaGenerationCode, include_raw=True, method=methode_sortie_structuree(modele)
    )
    sortie = _avec_retry(structure.invoke)(
        [SystemMessage(content=_PROMPT_SYSTEME_JSON), HumanMessage(content=prompt)]
    )
    reponse_brute = extraire_texte_brut(sortie["raw"])
    if sortie["parsing_error"] is not None:
        raise ErreurReponseAgentInvalide(
            f"réponse non conforme au schéma reçue de l'agent : {reponse_brute[:200]!r}"
        ) from sortie["parsing_error"]

    donnees = sortie["parsed"]
    return ResultatGenerationBrute(reponse_brute=reponse_brute, code_source=donnees.code)

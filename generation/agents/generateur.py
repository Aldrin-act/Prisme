"""Agent Développeur (§5.6) — écrit le code à partir de la mission (et, dans
le pipeline multi-agents, du plan technique de l'agent Architecte). Deux
formats de sortie coexistent :

- `generer_code_solveur` — mode simple (Étape 4, tir unique, historique) :
  un bloc de code Python nu, format hérité de `generation.tentative_unique`.
- `generer_code_depuis_plan` — mode multi-agents
  (`generation.pipeline_multi_agents`) : réponse JSON `{"code": "..."}`,
  comme les 8 autres agents du pipeline.

Le contrat de sortie attendu dans les deux cas — une fonction
`resoudre(instance) -> Planning | None` — est identique à celui de
`solveur_reference.resoudre`, pour que le code produit se branche
directement dans `validation_engine.cascade.evaluer_cascade` sans adaptation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission, extraire_bloc_code, extraire_json
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT_DEPUIS_PLAN = Path(__file__).resolve().parents[1] / "prompts" / "developpeur.md"

_PROMPT_SYSTEME = "Tu es un générateur de code Python expert en optimisation combinatoire."
_PROMPT_SYSTEME_JSON = _PROMPT_SYSTEME + " Tu réponds toujours en JSON strict, jamais en texte libre."

_ADDENDUM_FORMAT_BLOC_CODE = (
    "\n## Format de réponse\n\n"
    "Réponds avec un unique bloc de code Python (` ```python ... ``` `), sans "
    "texte avant ni après. Aucune explication, aucun commentaire de conversation.\n"
)


@dataclass(frozen=True)
class ResultatGenerationBrute:
    """La réponse brute du LLM et le code Python qui en a été extrait."""

    reponse_brute: str
    code_source: str


def generer_code_solveur(appel_llm: AppelLLM) -> ResultatGenerationBrute:
    """Un seul essai de génération, sans plan technique préalable (Étape 4,
    tir unique) : construit le prompt à partir de la seule mission, appelle
    le LLM, extrait le code. Ne valide ni n'exécute rien — voir
    `generation.validation_statique` et `generation.executer`.
    """
    prompt = charger_mission() + _ADDENDUM_FORMAT_BLOC_CODE
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    return ResultatGenerationBrute(reponse_brute=reponse, code_source=extraire_bloc_code(reponse))


def generer_code_depuis_plan(appel_llm: AppelLLM, plan_technique: str) -> ResultatGenerationBrute:
    """Variante utilisée par le pipeline multi-agents : écrit le code en
    suivant le plan produit par l'agent Architecte plutôt que la seule
    mission brute, et répond en JSON comme le reste du pipeline."""
    gabarit = CHEMIN_PROMPT_DEPUIS_PLAN.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), plan_technique=plan_technique)
    reponse = appel_llm(_PROMPT_SYSTEME_JSON, prompt)
    donnees = extraire_json(reponse)
    return ResultatGenerationBrute(reponse_brute=reponse, code_source=donnees["code"])

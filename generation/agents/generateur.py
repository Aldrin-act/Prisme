"""Agent Développeur (§5.6) — écrit le code à partir de la mission (et, dans
le pipeline multi-agents, du plan technique de l'agent Architecte). Historiquement
le seul agent du pipeline (Étape 4, tir unique, avant toute boucle
generate-test-repair d'Étape 6) — `generer_code_solveur` reste ce mode simple ;
`generer_code_depuis_plan` est la variante utilisée par
`generation.pipeline_multi_agents`. Le contrat de sortie attendu — une
fonction `resoudre(instance) -> Planning | None` — est identique à celui de
`solveur_reference.resoudre`, pour que le code produit se branche
directement dans `validation_engine.cascade.evaluer_cascade` sans adaptation.
"""

from __future__ import annotations

from dataclasses import dataclass

from generation.agents.base import charger_mission, extraire_bloc_code
from generation.agents.client_llm import AppelLLM

_PROMPT_SYSTEME = "Tu es un générateur de code Python expert en optimisation combinatoire."

_GABARIT_DEPUIS_PLAN = """{mission}

## Plan technique de l'agent Architecte

Voici le plan que tu dois suivre pour écrire le module — respecte ses choix \
de variables et de contraintes, sauf s'il viole une des règles de sécurité \
ci-dessus (auquel cas les règles de sécurité priment) :

{plan_technique}
"""


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
    prompt = charger_mission()
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    return ResultatGenerationBrute(reponse_brute=reponse, code_source=extraire_bloc_code(reponse))


def generer_code_depuis_plan(appel_llm: AppelLLM, plan_technique: str) -> ResultatGenerationBrute:
    """Variante utilisée par le pipeline multi-agents : écrit le code en
    suivant le plan produit par l'agent Architecte plutôt que la seule
    mission brute."""
    prompt = _GABARIT_DEPUIS_PLAN.format(mission=charger_mission(), plan_technique=plan_technique)
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    return ResultatGenerationBrute(reponse_brute=reponse, code_source=extraire_bloc_code(reponse))

"""Agent Testeur (pipeline multi-agents, §5.6) — génère des tests pytest
complémentaires à la cascade de validation (`validation_engine/cascade.py`).

Important : ces tests sont **générés mais jamais exécutés automatiquement**
par le pipeline — les exécuter demanderait le même traitement de sécurité
(allowlist AST, bac à sable) que le code du solveur lui-même, hors périmètre
de cette étape. Ils sont renvoyés pour lecture humaine (canal d'audit),
jamais un critère d'acceptation du solveur — seule la cascade l'est.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission, extraire_json
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "testeur.md"

_PROMPT_SYSTEME = (
    "Tu es un ingénieur qualité spécialisé en tests de solveurs d'optimisation combinatoire. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


@dataclass(frozen=True)
class ResultatTests:
    reponse_brute: str
    code_tests: str


def generer_tests(appel_llm: AppelLLM, code_source: str) -> ResultatTests:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), code=code_source)
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    donnees = extraire_json(reponse)
    return ResultatTests(reponse_brute=reponse, code_tests=donnees["code_tests"])

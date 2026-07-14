"""Agent générateur (§5.6) — un seul appel LLM, une seule génération, sans
boucle : c'est l'Étape 4, le premier contact avec l'IA, avant toute boucle
generate-test-repair (Étape 6). Le contrat de sortie attendu — une fonction
`resoudre(instance) -> Planning | None` — est identique à celui de
`solveur_reference.resoudre`, pour que le code produit se branche
directement dans `validation_engine.cascade.evaluer_cascade` sans
adaptation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "generation_solveur.md"

_PROMPT_SYSTEME = "Tu es un générateur de code Python expert en optimisation combinatoire."

_MOTIF_BLOC_PYTHON = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)
_MOTIF_BLOC_GENERIQUE = re.compile(r"```\s*\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class ResultatGenerationBrute:
    """La réponse brute du LLM et le code Python qui en a été extrait."""

    reponse_brute: str
    code_source: str


def _extraire_bloc_code(reponse: str) -> str:
    """Extrait le contenu d'un bloc ```python ... ``` ; à défaut, un bloc
    générique ; à défaut, la réponse telle quelle (le prompt exige le
    premier format, mais les LLM n'y sont pas toujours fidèles)."""
    for motif in (_MOTIF_BLOC_PYTHON, _MOTIF_BLOC_GENERIQUE):
        correspondance = motif.search(reponse)
        if correspondance is not None:
            return correspondance.group(1)
    return reponse


def generer_code_solveur(appel_llm: AppelLLM) -> ResultatGenerationBrute:
    """Un seul essai de génération : construit le prompt, appelle le LLM,
    extrait le code. Ne valide ni n'exécute rien — voir
    `generation.validation_statique` et `generation.executer`.
    """
    prompt = CHEMIN_PROMPT.read_text(encoding="utf-8")
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    return ResultatGenerationBrute(reponse_brute=reponse, code_source=_extraire_bloc_code(reponse))

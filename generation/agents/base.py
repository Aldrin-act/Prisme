"""Utilitaires partagés par les 9 agents du pipeline de génération (§5.6) :
charger la mission commune (le contrat que `resoudre()` doit respecter) et
extraire un bloc de code de la réponse d'un LLM — chaque agent qui produit
du code (Développeur, Debugger, Optimiseur) en a besoin, pas seulement
`generateur.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

CHEMIN_MISSION = Path(__file__).resolve().parents[1] / "prompts" / "generation_solveur.md"

_MOTIF_BLOC_PYTHON = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)
_MOTIF_BLOC_GENERIQUE = re.compile(r"```\s*\n(.*?)```", re.DOTALL)


def charger_mission() -> str:
    """Le contrat T-R-C-O/CP-SAT commun à tous les agents — inputs, outputs,
    contraintes de sécurité (voir `prompts/generation_solveur.md`)."""
    return CHEMIN_MISSION.read_text(encoding="utf-8")


def extraire_bloc_code(reponse: str) -> str:
    """Extrait le contenu d'un bloc ```python ... ``` ; à défaut, un bloc
    générique ; à défaut, la réponse telle quelle (les prompts exigent le
    premier format, mais les LLM n'y sont pas toujours fidèles)."""
    for motif in (_MOTIF_BLOC_PYTHON, _MOTIF_BLOC_GENERIQUE):
        correspondance = motif.search(reponse)
        if correspondance is not None:
            return correspondance.group(1)
    return reponse

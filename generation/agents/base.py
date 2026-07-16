"""Utilitaires partagés par les 9 agents du pipeline de génération (§5.6) :
charger la mission commune (le contrat que `resoudre()` doit respecter) et
parser la réponse d'un agent. Le pipeline multi-agents (`pipeline_multi_agents.py`)
répond en JSON structuré partout (jamais en texte libre ni en marqueurs ad
hoc) — `extraire_json`. Le mode simple à un seul agent (Étape 4,
`tentative_unique.py`) garde son format historique, un bloc de code Python
nu — `extraire_bloc_code`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CHEMIN_MISSION = Path(__file__).resolve().parents[1] / "prompts" / "generation_solveur.md"

_MOTIF_BLOC_PYTHON = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)
_MOTIF_BLOC_JSON = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)
_MOTIF_BLOC_GENERIQUE = re.compile(r"```\s*\n(.*?)```", re.DOTALL)


class ErreurReponseAgentInvalide(Exception):
    """La réponse d'un agent n'est pas le JSON structuré attendu — le LLM
    n'a pas suivi le format demandé, ou renvoie un JSON syntaxiquement
    invalide. Ne survient jamais silencieusement : mieux vaut un échec net
    de la tentative de génération qu'un champ manquant traité par défaut."""


def charger_mission() -> str:
    """Le contrat T-R-C-O/CP-SAT commun à tous les agents — inputs, outputs,
    contraintes de sécurité (voir `prompts/generation_solveur.md`)."""
    return CHEMIN_MISSION.read_text(encoding="utf-8")


def extraire_bloc_code(reponse: str) -> str:
    """Extrait le contenu d'un bloc ```python ... ``` ; à défaut, un bloc
    générique ; à défaut, la réponse telle quelle. Réservé au mode simple
    (Étape 4, `generation.agents.generateur.generer_code_solveur`) — le
    pipeline multi-agents utilise `extraire_json` partout, y compris pour
    le code (champ `"code"`)."""
    for motif in (_MOTIF_BLOC_PYTHON, _MOTIF_BLOC_GENERIQUE):
        correspondance = motif.search(reponse)
        if correspondance is not None:
            return correspondance.group(1)
    return reponse


def extraire_json(reponse: str) -> dict[str, Any]:
    """Parse la réponse JSON d'un agent. Tolère un bloc ```json ... ``` ou
    ``` ... ``` autour du JSON — les LLM n'omettent pas toujours le
    formatage markdown malgré la consigne — sinon tente un parsing direct
    de la réponse telle quelle."""
    candidats = [reponse.strip()]
    for motif in (_MOTIF_BLOC_JSON, _MOTIF_BLOC_GENERIQUE):
        correspondance = motif.search(reponse)
        if correspondance is not None:
            candidats.append(correspondance.group(1).strip())

    for candidat in candidats:
        try:
            objet = json.loads(candidat)
        except json.JSONDecodeError:
            continue
        if isinstance(objet, dict):
            return objet

    raise ErreurReponseAgentInvalide(f"réponse non JSON reçue de l'agent : {reponse[:200]!r}")

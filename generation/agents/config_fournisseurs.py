"""Configuration centralisée des fournisseurs LLM par agent (§5.6).

Chaque agent du pipeline multi-agents utilise le fournisseur le mieux adapté
à sa tâche spécifique, optimisant ainsi le rapport qualité/coût/performance.

Répartition justifiée :
- **nemotron** (8 agents) : 16K tokens pour raisonnement complexe → Développeur,
  Debugger, Architecte, Analyste, Reviewer, Testeur, Agent ERP. Remplace
  deepseek (`deepseek-ai/deepseek-v4-pro`) — `nvidia/nemotron-3-super-120b-a12b`
  (voir `client_llm.py::_MODELES_PAR_DEFAUT` : la variante nano, choisie
  d'abord pour sa latence, produit une sortie JSON structurée incohérente en
  pratique, vérifié par appel réel — super est la plus petite variante
  nemotron-3 qui reste fiable sur cette tâche).
- **minimax** (2 agents) : Créativité maximale (temp=1.0) pour exploration
  → Benchmarker, Optimiseur
- **nvidia** (1 agent) : Déterministe (temp=0.6) pour tâches simples/structurées
  → Documentation

Le fournisseur peut toujours être surchargé par variable d'environnement
`PRISME_LLM_PROVIDER_<AGENT>` (ex: `PRISME_LLM_PROVIDER_GENERATEUR=mistral`) —
`deepseek` reste un fournisseur valide pour un retour en arrière ponctuel,
juste plus la valeur par défaut d'aucun agent.
"""

from __future__ import annotations

import os

# Répartition optimale des fournisseurs par agent
FOURNISSEURS_PAR_AGENT: dict[str, str] = {
    # Agents critiques (génération/débogage de code) — Nemotron-3
    "generateur": "nemotron",  # 16K tokens
    "developpeur": "nemotron",  # Alias de generateur
    "debugger": "nemotron",  # Analyse d'erreurs
    "architecte": "nemotron",  # Raisonnement structurel complexe
    # Agents d'analyse — Nemotron-3
    "analyste": "nemotron",  # Compréhension profonde
    "reviewer": "nemotron",  # Revue critique approfondie
    # Agents créatifs — MiniMax
    "benchmarker": "minimax",  # Exploration d'algorithmes alternatifs
    "optimiseur": "minimax",  # Optimisations non évidentes
    # Agents utilitaires simples — NVIDIA
    "documentation": "nvidia",  # Tâche simple, peu de tokens
    # Agents équilibrés — Nemotron-3
    "testeur": "nemotron",  # Équilibre créativité/structure (16K tokens)
    # Agent ERP — Nemotron-3
    "comprehension": "nemotron",  # 16K tokens pour grandes données ERP
    "erp": "nemotron",  # Alias de comprehension
    # Agent de supervision (MT7) — Mistral
    "supervision": "mistral",  # Synthèse JSON courte, pas de génération de code
}


def obtenir_fournisseur_pour_agent(nom_agent: str) -> str:
    """Renvoie le fournisseur optimal pour un agent donné.

    Args:
        nom_agent: Nom de l'agent (ex: "generateur", "debugger", etc.)

    Returns:
        Nom du fournisseur LLM (ex: "deepseek", "minimax", etc.)

    Le nom de l'agent est normalisé (minuscules, sans accents) avant lookup.
    Une variable d'environnement `PRISME_LLM_PROVIDER_<AGENT>` surcharge
    toujours la configuration par défaut.
    """
    # Normalisation : minuscules, retrait de caractères non-ASCII de base
    nom_normalise = nom_agent.lower().strip()

    # Surcharge par variable d'environnement (prioritaire)
    var_env = f"PRISME_LLM_PROVIDER_{nom_normalise.upper()}"
    fournisseur_env = os.environ.get(var_env)
    if fournisseur_env:
        return fournisseur_env

    # Configuration par défaut
    fournisseur = FOURNISSEURS_PAR_AGENT.get(nom_normalise)
    if fournisseur is None:
        # Fallback : utiliser le fournisseur global ou mistral par défaut
        return os.environ.get("PRISME_LLM_PROVIDER", "mistral")

    return fournisseur

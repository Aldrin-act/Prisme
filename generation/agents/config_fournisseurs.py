"""Configuration centralisée des fournisseurs LLM par agent (§5.6).

Chaque agent du pipeline multi-agents utilise le fournisseur le mieux adapté
à sa tâche spécifique, optimisant ainsi le rapport qualité/coût/performance.

Répartition justifiée :
- **deepseek** (6 agents) : Thinking mode + 16K tokens pour raisonnement complexe
  → Développeur, Debugger, Architecte, Analyste, Reviewer, Agent ERP
- **minimax** (2 agents) : Créativité maximale (temp=1.0) pour exploration
  → Benchmarker, Optimiseur
- **nvidia** (1 agent) : Déterministe (temp=0.6) pour tâches simples/structurées
  → Documentation
- **together** (1 agent) : Équilibré créativité/structure
  → Testeur

Le fournisseur peut toujours être surchargé par variable d'environnement
`PRISME_LLM_PROVIDER_<AGENT>` (ex: `PRISME_LLM_PROVIDER_GENERATEUR=mistral`).
"""

from __future__ import annotations

import os

# Répartition optimale des fournisseurs par agent
FOURNISSEURS_PAR_AGENT: dict[str, str] = {
    # Agents critiques (génération/débogage de code) — DeepSeek
    "generateur": "deepseek",  # 16K tokens, thinking mode
    "developpeur": "deepseek",  # Alias de generateur
    "debugger": "deepseek",  # Thinking mode pour analyse d'erreurs
    "architecte": "deepseek",  # Raisonnement structurel complexe
    # Agents d'analyse — DeepSeek
    "analyste": "deepseek",  # Compréhension profonde
    "reviewer": "deepseek",  # Revue critique approfondie
    # Agents créatifs — MiniMax
    "benchmarker": "minimax",  # Exploration d'algorithmes alternatifs
    "optimiseur": "minimax",  # Optimisations non évidentes
    # Agents utilitaires simples — NVIDIA
    "documentation": "nvidia",  # Tâche simple, peu de tokens
    # Agents équilibrés — DeepSeek (fallback depuis Together)
    "testeur": "deepseek",  # Équilibre créativité/structure (16K tokens)
    # Agent ERP — DeepSeek
    "comprehension": "deepseek",  # 16K tokens pour grandes données ERP
    "erp": "deepseek",  # Alias de comprehension
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

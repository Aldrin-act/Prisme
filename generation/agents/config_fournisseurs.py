"""Configuration centralisée des fournisseurs LLM par agent (§5.6).

**Un seul fournisseur pour tous les agents : Mistral.** `FOURNISSEURS_PAR_AGENT`
reste volontairement vide — chaque agent retombe donc sur le repli générique
d'`obtenir_fournisseur_pour_agent` (`PRISME_LLM_PROVIDER`, "mistral" si même
cette variable est absente), sans distinction par agent.

Historique : ce module routait auparavant chaque agent vers un fournisseur
différent selon sa tâche (nemotron pour le raisonnement long, minimax pour
l'exploration créative, nvidia pour les tâches simples) — une complexité de
configuration jugée non nécessaire au profit d'un fournisseur unique, plus
simple à opérer et à auditer. Les fonctions de construction pour les autres
fournisseurs (`nemotron`, `minimax`, `nvidia`, `deepseek`, `together`, `qwen`)
restent intactes dans `client_llm.py` — un retour en arrière ponctuel reste
possible via `PRISME_LLM_PROVIDER_<AGENT>` (ex:
`PRISME_LLM_PROVIDER_GENERATEUR=nemotron`), sans qu'aucun code ne soit à
modifier pour ça.
"""

from __future__ import annotations

import os

# Volontairement vide — un seul fournisseur pour tous les agents (voir
# docstring module). Conservé comme point d'extension si un agent doit un
# jour redevenir une exception au fournisseur unique.
FOURNISSEURS_PAR_AGENT: dict[str, str] = {}


def obtenir_fournisseur_pour_agent(nom_agent: str) -> str:
    """Renvoie le fournisseur LLM pour un agent donné — "mistral" pour tous
    par défaut (`FOURNISSEURS_PAR_AGENT` vide, voir docstring module), sauf
    variable d'environnement `PRISME_LLM_PROVIDER_<AGENT>` explicite pour cet
    agent précis.

    Args:
        nom_agent: Nom de l'agent (ex: "generateur", "debugger", etc.)

    Returns:
        Nom du fournisseur LLM à utiliser pour cet agent.

    Le nom de l'agent est normalisé (minuscules, sans accents) avant lookup.
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

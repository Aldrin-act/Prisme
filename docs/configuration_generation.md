# Configuration de la génération de solveurs

> **Document obsolète.** Ce guide décrivait l'architecture pré-LangGraph (scripts
> `generer_solveur.py`/`generer_multi_agents.py`, module `generation/pipeline_multi_agents.py`,
> pipeline à 8 agents sans Benchmarker) — tous supprimés depuis. Conservé uniquement pour
> l'historique ; ne pas suivre ses commandes ni son schéma de pipeline.

## État actuel

Le pipeline de génération est `generation/graph.py` (un `StateGraph` LangGraph), câblé à l'API
(`api/routes/generation.py`) — c'est le seul chemin de production, il n'y a plus de choix entre
« mode simple » et « mode multi-agents » via des scripts séparés :

```
analyste → benchmarker (choisit l'algorithme : cp_sat exact, ou une heuristique
           genetic/aco/tabu_search/simulated_annealing/dispatching/greedy_local
           pour les instances trop grandes) → architecte → développeur → testeur
   → boucle bornée (reviewer ⇄ debugger, max 10 tentatives, `MAX_TENTATIVES_REPARATION`)
→ documentation (best-effort)
```

L'ancien `generation/tentative_unique.py` (un seul appel LLM, sans boucle de réparation) existe
toujours mais n'est plus ce que l'API appelle — utilisé seulement par des scripts de dev pour de
l'itération rapide/économique (`scripts/mesurer_taux_succes_generation.py`).

Fournisseurs LLM : `mistral` (défaut), `qwen`, `together`, `nvidia`, `minimax`, `deepseek` — routés
par agent via `generation/agents/config_fournisseurs.py`, jamais Anthropic/OpenAI directement (voir
`generation/agents/client_llm.py`).

Voir [`CLAUDE.md`](../CLAUDE.md) (section Étape 6) pour le détail à jour, et
[`generation/README.md`](../generation/README.md)/[`docs/agents_utilises.md`](agents_utilises.md)
pour le rôle de chaque agent.

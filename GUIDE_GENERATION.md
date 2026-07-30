# Guide de génération de solveur

> **Document obsolète.** Ce guide décrivait des scripts (`generer_multi_agents.py`,
> `generer_avec_boucle.py`, `generer_et_executer_greensig.py`) et un module
> (`generation/pipeline_multi_agents.py`) tous supprimés depuis, et un pipeline à 8-9 étapes qui
> n'incluait pas l'agent Benchmarker (choix dynamique de l'algorithme). Conservé pour l'historique
> uniquement — ne pas suivre ses commandes.

## État actuel

Le pipeline de génération est `generation/graph.py` (LangGraph), câblé à l'API
(`api/routes/generation.py`) — `POST /generation/{instance_id}` (bloquant) ou
`POST /generation/{instance_id}/demarrer` + SSE `GET /generation/jobs/{job_id}/stream`
(en tâche de fond, suit la progression agent par agent) :

```
analyste → benchmarker (choisit l'algorithme dans son catalogue complet — cp_sat, exact, ou
           genetic/aco/tabu_search/simulated_annealing/dispatching/greedy_local pour les
           instances trop grandes pour un solveur exact)
         → architecte → développeur → testeur
         → boucle bornée (reviewer ⇄ debugger, max 10 tentatives)
         → documentation (best-effort)
```

À chaque tentative de la boucle, le code passe par la validation statique (allowlist AST), une
exécution réelle, puis la cascade de validation (faisabilité → optimalité → fidélité). Si la
boucle épuise ses tentatives sans succès, l'échec remonte tel quel — jamais de nouvel essai
silencieux au-delà de la limite.

Fournisseurs LLM disponibles : `mistral` (défaut), `qwen`, `together`, `nvidia`, `minimax`,
`deepseek` — un par agent, routés automatiquement (`generation/agents/config_fournisseurs.py`),
surchargeables par variable d'environnement (`PRISME_LLM_PROVIDER_<AGENT>`). Anthropic/OpenAI ne
sont pas des fournisseurs supportés par ce pipeline.

Pour générer un solveur : voir la route API `POST /generation/{instance_id}` (ou son équivalent
`/demarrer` + SSE), ou `scripts/mesurer_taux_succes_generation.py` pour le mode single-shot legacy
(`generation/tentative_unique.py`, dev/mesure uniquement, pas le chemin de production).

Voir [`CLAUDE.md`](CLAUDE.md) (section Étape 6) et [`generation/README.md`](generation/README.md)
pour le détail à jour.

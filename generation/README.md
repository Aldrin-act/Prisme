# generation — Traduction du DSL en code de solveur CP-SAT (§5.6)

**Deux chemins de génération** :

- `tentative_unique.py` — **Étape 4**, historique : un seul agent
  (`agents/generateur.py`), un seul appel LLM, prompt fixe. Toujours utilisé
  par quelques scripts de dev (`generer_solveur_simple.py`,
  `mesurer_taux_succes_generation.py`) pour de l'itération rapide/peu chère,
  mais plus le chemin appelé par l'API.
- `graph.py` — **Étape 6**, seul pipeline branché sur l'API
  (`api/routes/generation.py`) : un `StateGraph` LangGraph — Analyste →
  Benchmarker (choisit l'algorithme) → Architecte → Développeur → Testeur →
  **boucle de réparation bornée** (Reviewer ⇄ Debugger, max 10 tentatives,
  `MAX_TENTATIVES_REPARATION`) → Documentation. Pas d'Orchestrateur (jamais
  utile — voir la docstring du module, il ne pilotait rien) ni d'Optimiseur
  (retiré, réponse JSON trop fragile pour embarquer du code) dans ce
  pipeline ; `agents/optimiseur.py` reste comme fichier orphelin.

Les deux chemins convergent sur la même chaîne de garde-fous procéduraux —
jamais des agents, volontairement :

- `agents/client_llm.py` — client LLM générique ; fournisseur et modèle par
  défaut choisis par variable d'environnement (`PRISME_LLM_PROVIDER` —
  `mistral`/`qwen`/`together`/`nvidia`/`minimax`/`deepseek` —,
  `PRISME_LLM_MODEL`). `graph.py` route en réalité chaque agent vers son
  propre fournisseur optimal via `agents/config_fournisseurs.py`,
  surchargeable par agent (`PRISME_LLM_PROVIDER_<AGENT>` / `_MODEL_<AGENT>`).
- `agents/base.py` — utilitaires partagés par les agents : charger la
  mission commune (`prompts/generation_solveur.md`), extraire un bloc de
  code de la réponse d'un LLM.
- `validation_statique.py` — garde-fou par AST (liste blanche d'imports,
  appels et attributs interdits), **avant toute exécution** (§5.3). L'agent
  Testeur génère des tests pytest complémentaires, mais ils ne sont **jamais
  exécutés automatiquement** — les exécuter demanderait ce même traitement
  de sécurité, hors périmètre ici.
- `executer.py` — exécute le code une fois la validation statique passée.
  Ce n'est pas le bac à sable (Étape 7) : juste un espace de noms dédié,
  pour ce premier contact avec l'IA.
- Jugement final : la cascade complète (`validation_engine.cascade`, Étape 5)
  — jamais l'avis de l'agent Reviewer seul, qui n'est que consultatif.

Benchmark : `scripts/mesurer_taux_succes_generation.py` lance N tentatives
indépendantes (chemin Étape 4) et rapporte le taux de succès brut — un point
de comparaison, pas le taux de succès du pipeline complet avec boucle.

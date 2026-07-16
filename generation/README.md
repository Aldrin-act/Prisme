# generation — Traduction du DSL en code de solveur CP-SAT (§5.6)

**Deux chemins de génération, tous deux à tentative unique bornée** (la
boucle generate-test-repair générale, Étape 6, `loop.py`/`failures/`,
n'existe toujours pas) :

- `tentative_unique.py` — **Étape 4**, historique : un seul agent
  (`agents/generateur.py`), un seul appel LLM, prompt fixe.
- `pipeline_multi_agents.py` — pipeline à **9 agents**, chacun un appel LLM
  distinct : Orchestrateur → Analyste → Architecte → Développeur → Testeur
  → Reviewer → [Debugger, une seule fois si la revue échoue] → validation
  complète → Optimiseur (adopté seulement s'il repasse la validation) →
  Documentation. Voir `pipeline_multi_agents.tenter_generation_multi_agents`.

Les deux chemins convergent sur la même chaîne de garde-fous procéduraux —
jamais des agents, volontairement :

- `agents/client_llm.py` — client LLM générique ; fournisseur et modèle
  choisis par variables d'environnement (`PRISME_LLM_PROVIDER` —
  `anthropic`/`openai`/`mistral` —, `PRISME_LLM_MODEL`), jamais codés en dur.
- `agents/base.py` — utilitaires partagés par les 9 agents : charger la
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
indépendantes (chemin Étape 4) et rapporte le taux de succès brut — le point
de départ avant toute boucle, pas un objectif à atteindre à ce stade.

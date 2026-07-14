# generation — Traduction du DSL en code de solveur CP-SAT (§5.6)

**État actuel : Étape 4 seulement** — un seul agent, une seule génération,
sans boucle. La boucle multi-agent generate-test-repair bornée (Étape 6,
garde-fous : bornée, hors ligne, diagnostique) n'existe pas encore ;
`loop.py` et `failures/` en font partie et ne sont donc pas encore présents.

- `agents/client_llm.py` — client LLM générique ; fournisseur et modèle
  choisis par variables d'environnement (`PRISME_LLM_PROVIDER`,
  `PRISME_LLM_MODEL`), jamais codés en dur.
- `agents/generateur.py` — l'agent développeur : construit le prompt, appelle
  le LLM, extrait le code. Ne valide ni n'exécute rien.
- `prompts/generation_solveur.md` — le prompt de génération à tir unique
  (le prompt de réparation viendra avec la boucle, Étape 6).
- `validation_statique.py` — garde-fou par AST (liste blanche d'imports,
  appels et attributs interdits), **avant toute exécution** (§5.3).
- `executer.py` — exécute le code une fois la validation statique passée.
  Ce n'est pas le bac à sable (Étape 7) : juste un espace de noms dédié,
  pour ce premier contact avec l'IA.
- `tentative_unique.py` — assemble génération → validation statique →
  exécution → jugement par la cascade complète (`validation_engine.cascade`,
  Étape 5). Le futur `loop.py` enveloppera ce même bloc dans une boucle
  bornée avec réparation.

Benchmark : `scripts/mesurer_taux_succes_generation.py` lance N tentatives
indépendantes et rapporte le taux de succès brut — le point de départ avant
toute boucle, pas un objectif à atteindre à ce stade.

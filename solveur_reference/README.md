# solveur_reference — Solveur CP-SAT de référence, écrit à la main

Étape absente de la roadmap (§8) mais jugée indispensable avant l'Étape 4
(génération par l'IA) : elle prouve que le noyau minimal (précédence,
compatibilité machine-tâche, durées) est effectivement résoluble, calibre
les attentes de performance, et devient un cas de référence pour la
fidélité sémantique (§6.2 brique 3) — la cible que le code généré devra
égaler.

Contrairement à `generation/`, ce code n'est ni généré, ni figé dans
`solver_store/`, ni régénéré : il est écrit et maintenu à la main, en dehors
du cycle « générer une fois, réexécuter ensuite ».

- `solveur.py` — `resoudre(instance) -> ResultatResolution` : modélisation
  CP-SAT classique du FJSP (intervalles optionnels par ressource compatible,
  non-chevauchement, précédence, minimisation du makespan).
- Benchmark : `scripts/benchmarker_solveur_reference.py` mesure ses
  performances sur le catalogue du banc synthétique
  (`validation_engine/synthetic_bench/`).

# validation_engine — Cascade de validation (§6)

Trois briques par sévérité croissante, construites dans cet ordre car chacune dépend de la précédente :

1. `feasibility_checker.py` — le planning est-il légal ? (précédence, unicité machine, compatibilité). Le plus rentable, réutilisé partout : validation hors ligne **et** garde-fou en production (§6.7).
2. `synthetic_bench/` — le planning est-il bon ? Instances à vérité terrain connue par **construction inverse** (planning optimal choisi → instance bâtie autour, §6.4).
3. `reference_cases/` — le planning résout-il le bon problème ? Cas de référence écrits à la main (DSL + planning attendu), fidélité sémantique (§6.2).

- `stability_test.py` — test de stabilité de génération : même DSL généré N fois, vérifie l'équivalence des plannings produits (§6.5).

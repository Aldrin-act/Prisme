# tests — Trois couches de nature différente (§6.1)

- `unit/`, `integration/` — Couche 1 : code écrit à la main (API, adaptateurs, orchestration). Déterministe, paires entrée/sortie figées.
- `property_based/` — Couche 2 : code généré par l'IA (le solveur). On teste les propriétés du planning produit, pas le texte du code — s'appuie sur `validation_engine/`.
- `generation_stability/` — Couche 3 : la génération elle-même, testée à travers la couche 2 (mêmes propriétés, N générations pour un même DSL, §6.5).

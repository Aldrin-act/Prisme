"""generation — Traduction du DSL T-R-C-O en code de solveur CP-SAT (§5.6).

Deux chemins, tous deux à tentative unique bornée : l'Étape 4 historique à
un seul agent (`tentative_unique.py`) et un pipeline à 9 agents
(`pipeline_multi_agents.py`, voir `README.md`). La boucle bornée
generate-test-repair générale (Étape 6, `loop.py`) n'existe toujours pas.
"""

"""generation — Traduction du DSL T-R-C-O en code de solveur CP-SAT (§5.6).

Deux chemins : l'Étape 4 historique à un seul agent, tentative unique
(`tentative_unique.py`) et le pipeline actif à 8 agents avec boucle de
réparation bornée (Étape 6, `graph.py` + `loop.py`, voir
`README.md`) — celui appelé par l'API (`api/routes/generation.py`).
"""

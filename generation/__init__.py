"""generation — Traduction du DSL T-R-C-O en code de solveur (§5.6) : l'agent
Benchmarker choisit l'algorithme par instance (une heuristique
genetic/aco/tabu_search/simulated_annealing/dispatching/greedy_local —
PRISME n'utilise aucun moteur exact) avant que le code ne soit généré.

Deux chemins : l'Étape 4 historique à un seul agent, tentative unique
(`tentative_unique.py`, pas de Benchmarker) et le pipeline actif à 8 agents
avec boucle de réparation bornée (Étape 6, `graph.py`, voir `README.md`) —
celui appelé par l'API (`api/routes/generation.py`).
"""

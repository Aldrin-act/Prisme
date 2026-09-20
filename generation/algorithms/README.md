# Algorithmes d'ordonnancement

Ce module contient les implémentations des différents algorithmes d'ordonnancement recommandés par l'agent Benchmarker.

## Structure

```
generation/algorithms/
├── README.md                    # Ce fichier
├── genetic.py                   # Algorithmes génétiques (GA)
├── aco.py                       # Ant Colony Optimization
├── tabu_search.py               # Recherche tabou
├── simulated_annealing.py       # Recuit simulé
├── dispatching.py               # Règles de dispatching (SPT, LPT, EDD, FIFO)
└── greedy_local.py              # Glouton + recherche locale
```

## Implémentation actuelle

- ✅ Référence heuristique de test : `scripts/_solveur_minimal.py` (ordonnancement par liste, déterministe)
- 🚧 **genetic.py** : Squelette créé, à compléter
- ⏳ **aco.py** : À créer
- ⏳ **tabu_search.py** : À créer
- ⏳ **simulated_annealing.py** : À créer
- ⏳ **dispatching.py** : À créer
- ⏳ **greedy_local.py** : À créer

## Interface commune

Tous les algorithmes doivent implémenter la même signature :

```python
def resoudre(instance: InstanceTRCO, **params) -> Planning | None:
    """Résout une instance FJSP et retourne un planning.

    Args:
        instance: Instance T-R-C-O à résoudre
        **params: Paramètres spécifiques à l'algorithme

    Returns:
        Planning si solution trouvée, None sinon
    """
    pass
```

## Paramètres par algorithme

### Genetic Algorithm
```python
resoudre(instance,
         population_size=300,
         generations=500,
         crossover_rate=0.8,
         mutation_rate=0.05,
         tournament_size=5,
         elitism=0.1)
```

### ACO
```python
resoudre(instance,
         n_ants=50,
         iterations=500,
         alpha=1.0,
         beta=2.0,
         rho=0.1)
```

### Tabu Search
```python
resoudre(instance,
         tabu_tenure=10,
         iterations=5000,
         aspiration_criterion=True)
```

### Simulated Annealing
```python
resoudre(instance,
         T_init=1000,
         T_min=0.1,
         alpha=0.95,
         iterations_per_temp=100)
```

### Dispatching Rules
```python
resoudre(instance, rule="SPT")  # SPT, LPT, EDD, FIFO, LIFO
```

### Greedy + Local Search
```python
resoudre(instance,
         initial_rule="SPT",
         local_search="2-opt",
         max_iterations=1000)
```

## Utilisation

Ces modules sont des squelettes de référence, non branchés sur le pipeline : les solveurs
réellement exécutés sont générés par les agents (`generation/graph.py`) et figés dans
`solver_store/`. PRISME n'utilise aucun moteur exact (CP-SAT retiré) : toutes les recommandations
du Benchmarker sont des heuristiques.

## Critères de qualité

Chaque implémentation doit passer :

1. **Tests de faisabilité** : Solutions valides (pas de chevauchements, précédences respectées)
2. **Benchmarks** : Qualité vs temps sur instances connues
3. **Stabilité** : Résultats reproductibles (seed fixe pour algo stochastiques)

## Prochaines étapes

1. Compléter `genetic.py` (prioritaire pour GreenSig 2165 tâches)
2. Implémenter `dispatching.py` (baseline rapide)
3. Ajouter `tabu_search.py` (bon compromis qualité/temps)
4. Compléter les autres selon les besoins

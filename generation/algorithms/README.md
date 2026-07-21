# Algorithmes d'ordonnancement

Ce module contient les implémentations des différents algorithmes d'ordonnancement recommandés par l'agent Benchmarker.

## Structure

```
generation/algorithms/
├── README.md                    # Ce fichier
├── cp_sat.py                    # CP-SAT (OR-Tools) - référence actuelle
├── genetic.py                   # Algorithmes génétiques (GA)
├── aco.py                       # Ant Colony Optimization
├── tabu_search.py               # Recherche tabou
├── simulated_annealing.py       # Recuit simulé
├── dispatching.py               # Règles de dispatching (SPT, LPT, EDD, FIFO)
└── greedy_local.py              # Glouton + recherche locale
```

## Implémentation actuelle

- ✅ **cp_sat.py** : Référence `scripts._solveur_minimal.py` (existe déjà)
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

### CP-SAT
```python
resoudre(instance, limite_temps_s=300)
```

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

```python
from dsl.schema import InstanceTRCO
from generation.algorithms import genetic, cp_sat

# Charger instance
instance = InstanceTRCO.model_validate(...)

# Choisir algorithme selon la taille
if len(instance.taches) < 500:
    # Petite/moyenne : CP-SAT optimal
    planning = cp_sat.resoudre(instance, limite_temps_s=300)
else:
    # Grande : GA approché
    planning = genetic.resoudre(
        instance,
        population_size=300,
        generations=500
    )
```

## Avec agent Benchmarker

```python
from generation.agents.benchmarker import benchmarker_algorithmes
from generation.algorithms import genetic, cp_sat, aco

# Recommandation automatique
resultat = benchmarker_algorithmes(appel_llm, instance.model_dump())
algo = resultat.recommandation.algorithme

# Dispatcher
ALGORITHMS = {
    "cp_sat": cp_sat,
    "genetic": genetic,
    "aco": aco,
    # ...
}

solveur = ALGORITHMS[algo]
planning = solveur.resoudre(instance, **resultat.recommandation.parametres_suggeres)
```

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

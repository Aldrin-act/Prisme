# Considérations de performance - Résolution 2165 tâches GreenSig

Ce document explique les défis de performance lors de la résolution de problèmes FJSP à grande échelle.

## 🎯 Contexte

Le **Flexible Job-Shop Scheduling Problem (FJSP)** avec 2165 tâches est un problème d'optimisation **NP-difficile**. CP-SAT (OR-Tools) utilise des techniques de recherche sophistiquées, mais le temps de résolution croît **exponentiellement** avec la taille de l'instance.

## 📊 Échelle du problème

### Données de démo vs données réelles

| Métrique | Démo (4 tâches) | Réel (2165 tâches) | Ratio |
|----------|-----------------|---------------------|-------|
| Tâches | 4 | ~2165 | **x541** |
| Variables de décision | ~16 | ~50 000+ | **x3125** |
| Temps résolution | <1s | Minutes à heures | **x1000+** |
| Mémoire | <100 MB | 1-4 GB | **x10-40** |

### Complexité estimée

Pour les données GreenSig réelles :

- **Variables** : ~N × M (tâches × ressources compatibles moyennes)
  - Estimation : 2165 × 20 = **~43 000 variables**

- **Contraintes** :
  - Compatibilités ressource-tâche : une par couple valide
  - Non-chevauchement : une par ressource
  - Estimation : **~45 000+ contraintes**

- **Espace de recherche** :
  - Chaque tâche peut être assignée à plusieurs ressources
  - Ordre d'exécution sur chaque ressource
  - Taille : **exponentiellement grand**

## ⏱️ Temps de résolution attendus

### Scénarios optimistes

| Instance | Tâches | Timeout | Résultat attendu |
|----------|--------|---------|------------------|
| Subset 50 | 50 | 30s | ✅ Solution optimale |
| Subset 100 | 100 | 60s | ✅ Solution optimale ou bonne |
| Subset 500 | 500 | 300s | ⚠️ Solution faisable (possiblement sous-optimale) |
| Complète | 2165 | 600s | ❓ Incertain |

### Facteurs influençant la performance

**Accélèrent** :
- Tâches "fixes" (1 seule ressource compatible) → simplifient le problème
- Pas de précédences → moins de contraintes
- Durées uniformes → symétries exploitables

**Ralentissent** :
- Haute flexibilité (beaucoup d'équipes/tâche) → plus de choix
- Durées hétérogènes → moins de symétries
- Ressources saturées → recherche exhaustive

## 🔧 Paramètres de résolution

### Timeout recommandés

```python
# Subset (test rapide)
resoudre(instance, limite_temps_s=60)   # 1 min

# Subset moyen (100-500 tâches)
resoudre(instance, limite_temps_s=300)  # 5 min

# Instance complète (2165 tâches)
resoudre(instance, limite_temps_s=1800) # 30 min
```

### Ajuster dans _solveur_minimal.py

Si vous voulez plus de contrôle :

```python
def resoudre(instance: InstanceTRCO, limite_temps_s: float = 30.0) -> Planning | None:
    # ...
    solveur = cp_model.CpSolver()

    # Timeout
    solveur.parameters.max_time_in_seconds = limite_temps_s

    # Optionnel : paramètres avancés
    # solveur.parameters.num_search_workers = 8  # Parallélisme
    # solveur.parameters.log_search_progress = True  # Logs détaillés
    # solveur.parameters.cp_model_presolve = True  # Pré-résolution (défaut)

    statut = solveur.Solve(modele)
```

## 💡 Stratégies recommandées

### Approche progressive (recommandée)

1. **Subset 50 tâches** (1 min) :
   ```bash
   uv run python -m scripts.executer_greensig_subset
   # Choisir option 1 : Top N = 50
   ```

   ✅ Si succès : Le solveur fonctionne, la modélisation est correcte

2. **Subset 100 tâches** (2-3 min) :
   ```bash
   # Option 1 : Top N = 100
   ```

   ✅ Si succès : Le solveur passe à l'échelle modérée

3. **Subset 500 tâches** (10-15 min) :
   ```bash
   # Option 1 : Top N = 500
   ```

   ⚠️ Si timeout atteint : Solution sous-optimale acceptable
   ❌ Si aucune solution : Vérifier faisabilité

4. **Instance complète 2165 tâches** (30-60 min) :
   ```bash
   uv run python -m scripts.executer_greensig_2165_taches
   ```

   ✅ Objectif : Obtenir **une** solution faisable, pas forcément optimale

### Approche par filtrage métier

Au lieu de prendre les N premières tâches, filtrer par critères métier :

```python
# Tâches urgentes uniquement
# Tâches d'une période donnée (semaine, mois)
# Tâches par type (tonte, taille, etc.)
# Tâches courtes (≤60 min) pour maximiser le nombre résolu
```

## 📈 Interprétation des résultats

### Statuts CP-SAT

| Statut | Signification | Action |
|--------|---------------|--------|
| `OPTIMAL` | Solution optimale prouvée | ✅ Parfait ! |
| `FEASIBLE` | Solution trouvée, mais pas prouvée optimale | ✅ Acceptable (timeout atteint) |
| `INFEASIBLE` | Aucune solution possible | ❌ Vérifier contraintes |
| `UNKNOWN` | Timeout sans solution | ⚠️ Augmenter timeout ou filtrer |

### Qualité de la solution

Une solution `FEASIBLE` (non optimale) sur 2165 tâches est **acceptable** :

- Le makespan peut être 5-20% au-dessus de l'optimal
- Mais c'est infiniment mieux qu'aucune planification
- Les opérationnels peuvent ajuster manuellement

### Métriques de succès

Pour l'instance complète (2165 tâches) :

- ✅ **Objectif primaire** : Obtenir **une** solution (FEASIBLE ou OPTIMAL)
- ✅ **Objectif secondaire** : Makespan raisonnable (comparer avec somme durées / nb ressources)
- ⚠️ **Ne pas viser** : Solution optimale prouvée (peut prendre des heures/jours)

## 🚀 Optimisations possibles

### Dans le code du solveur

1. **Parallélisme** :
   ```python
   solveur.parameters.num_search_workers = 8  # Utilise 8 cœurs CPU
   ```

2. **Heuristiques de démarrage** :
   ```python
   # Donner une solution initiale (greedy heuristic)
   # CP-SAT améliorera cette base
   ```

3. **Décomposition** :
   ```python
   # Résoudre par sous-problèmes (ex: par équipe ou par type)
   # Puis combiner les résultats
   ```

### Hors code

1. **Hardware** :
   - CPU : Plus de cœurs = parallélisation efficace
   - RAM : 4-8 GB recommandés pour 2165 tâches
   - Temps : Laisser tourner overnight si nécessaire

2. **Données** :
   - Nettoyer les tâches obsolètes/dupliquées
   - Supprimer les compatibilités impossibles
   - Grouper les tâches similaires

## 📊 Benchmarks indicatifs

Basé sur des problèmes FJSP similaires dans la littérature :

| Tâches | Ressources | Temps (CP-SAT) | Qualité |
|--------|------------|----------------|---------|
| 10-20 | 5 | <1s | Optimal |
| 50-100 | 10-15 | 1-10s | Optimal |
| 200-500 | 20-30 | 1-30 min | Feasible (90-95% optimal) |
| 1000+ | 40+ | 30 min - heures | Feasible (85-95% optimal) |

**Note** : Ces temps sont indicatifs. La structure exacte de l'instance GreenSig peut être plus facile ou plus difficile.

## ⚠️ Quand abandonner l'optimal

Si après **1 heure** sur l'instance complète, aucune solution `FEASIBLE` :

1. **Vérifier infaisabilité** :
   ```bash
   # Extraire diagnostic de l'infaisabilité
   # Vérifier qu'au moins une ressource est compatible par tâche
   ```

2. **Décomposer le problème** :
   - Résoudre par semaine/période
   - Résoudre par type de tâche
   - Résoudre par zone géographique

3. **Approche hybride** :
   - CP-SAT pour planifier les tâches contraintes (fixes)
   - Heuristique greedy pour le reste

## 📚 Références

- [OR-Tools CP-SAT Documentation](https://developers.google.com/optimization/cp/cp_solver)
- [Job-Shop Scheduling Tutorial](https://developers.google.com/optimization/scheduling/job_shop)
- [Flexible Job-Shop Problem](https://en.wikipedia.org/wiki/Job-shop_scheduling)

## 🎯 Résumé

**Pour les 2165 tâches GreenSig** :

1. ✅ **Commencez petit** : Subset 50-100 tâches
2. ✅ **Progressez graduellement** : 500 → 1000 → 2165
3. ⏱️ **Soyez patient** : Timeout 30-60 min pour l'instance complète
4. 🎯 **Cible FEASIBLE**, pas OPTIMAL
5. 📊 **Mesurez** : Comparer makespan vs baseline (somme durées / nb ressources)

**Commandes recommandées** :

```bash
# 1. Tester avec subset (rapide)
uv run python -m scripts.executer_greensig_subset

# 2. Si succès, tenter l'instance complète (patience !)
uv run python -m scripts.executer_greensig_2165_taches
```

Bonne chance ! 🚀

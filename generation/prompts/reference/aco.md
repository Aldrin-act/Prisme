# Optimisation par colonies de fourmis (ACO)

Adaptée à la construction d'une permutation de tâches (même rôle que le chromosome de l'algorithme
génétique) — chaque fourmi construit un ordre de traitement pas à pas, guidée par la phéromone,
puis ce même décodeur constructif de l'Architecte transforme l'ordre en planning légal.

## Représentation de la phéromone

Une matrice `tau[i][j]` : désirabilité d'placer la tâche `j` juste après la tâche `i` dans l'ordre
construit. Initialiser à une valeur uniforme faible et strictement positive (ex. `1.0`) — une
phéromone nulle bloquerait tout choix dès la première itération (`probabilite ∝ tau^alpha *
eta^beta`, un facteur nul annule le produit).

## Construction d'une solution (une fourmi)

À chaque étape, parmi les tâches encore non placées **et dont toutes les `Precedence` sont déjà
satisfaites** (même contrainte que le décodeur générique), choisir la suivante avec une probabilité
proportionnelle à `tau[derniere][candidate]^alpha * eta[candidate]^beta`, où `eta` est une
heuristique locale (ex. `1 / duree_candidate` pour privilégier les tâches courtes). `alpha`/`beta`
pondèrent phéromone vs heuristique — `alpha=1`, `beta=2` est un point de départ raisonnable.

## Mise à jour de la phéromone

Après que toutes les fourmis de l'itération ont construit une solution complète :
1. Évaporation : `tau[i][j] *= (1 - rho)` pour tous `(i, j)`, `rho` typiquement entre 0,1 et 0,5 —
   évite que la phéromone ne croisse sans borne et fige la recherche sur les premiers choix.
2. Dépôt : pour chaque fourmi, pour chaque paire consécutive `(i, j)` de sa solution,
   `tau[i][j] += Q / makespan_de_la_fourmi` (`Q` une constante, ex. 100) — une fourmi qui a trouvé
   un meilleur makespan dépose plus de phéromone sur son chemin.

## Déterminisme

Même exigence que pour l'algorithme génétique : un seul `random.Random(graine)` local pour tous
les tirages de probabilité (construction) — jamais `random` global. Nombre fixe d'itérations ×
fourmis par itération comme critère d'arrêt, jamais un temps écoulé.

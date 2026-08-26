# Recherche tabou

Travaille sur une seule solution courante (une permutation de tâches), pas une population — à
chaque itération, explore un voisinage de mouvements et se déplace vers le meilleur voisin
autorisé, même s'il est moins bon que la solution courante (ce qui la distingue d'une simple
descente locale et lui permet d'échapper à un optimum local).

## Voisinage (mouvements élémentaires)

Échange (swap) de deux positions dans la permutation, ou insertion (déplacer un élément ailleurs
dans la séquence). Un voisinage complet (toutes les paires) coûte `O(n²)` par itération — pour une
instance de plusieurs centaines de tâches, échantillonner un sous-ensemble de mouvements candidats
plutôt que d'énumérer le voisinage entier, pour rester dans le budget du bac à sable.

## Liste taboue et tenure

Après un mouvement, l'attribut inverse (ex. « re-échanger ces deux mêmes positions ») est interdit
pendant `tenure` itérations — empêche de revenir immédiatement sur ses pas et de boucler entre deux
solutions. `tenure` typique : entre 5 et 20, ou proportionnelle à `sqrt(n_taches)` pour une instance
de taille variable. Une tenure trop courte ne prévient pas le cyclage ; trop longue interdit trop de
mouvements et bloque la recherche.

## Critère d'aspiration

Un mouvement tabou reste autorisé s'il produit une solution strictement meilleure que la meilleure
solution connue jusqu'ici — sans cette exception, la recherche tabou pourrait explicitement refuser
d'atteindre une amélioration réelle à cause d'un interdit temporaire, ce qui n'a pas de sens pour un
problème de minimisation.

## Critère d'arrêt et déterminisme

Nombre fixe d'itérations sans amélioration de la meilleure solution connue (ou nombre fixe absolu
d'itérations) — jamais un temps écoulé. Si le voisinage est échantillonné plutôt qu'énuméré
entièrement, l'échantillonnage doit lui-même utiliser un `random.Random(graine)` local fixe.

# Recuit simulé

Comme la recherche tabou, travaille sur une seule solution courante (une permutation de tâches) et
explore un voisinage par petits mouvements (échange, insertion) — la différence est le mécanisme
d'acceptation d'un voisin moins bon : probabiliste et décroissant dans le temps, plutôt qu'une liste
d'interdits.

## Calendrier de refroidissement

Une « température » `T` décroît au fil des itérations, généralement de façon géométrique :
`T = T0 * (facteur_refroidissement ** iteration)`, avec `facteur_refroidissement` proche de 1 (ex.
0,95 à 0,99) et `T0` choisi assez haut pour que les premiers mouvements dégradants aient une
probabilité d'acceptation non négligeable (ex. `T0` de l'ordre de l'écart de makespan typique entre
deux voisins). Décroissance linéaire (`T -= pas`) est une alternative plus simple, moins fidèle au
recuit physique mais tout aussi valide en pratique.

## Critère d'acceptation

Soit `delta = makespan_voisin - makespan_courant` (positif = voisin moins bon, on minimise). Si
`delta <= 0`, accepter toujours. Sinon, accepter avec probabilité `exp(-delta / T)` — tirée du même
`random.Random(graine)` local que le reste. Plus `T` est élevé, plus une dégradation importante
reste acceptée ; en fin de recherche (`T` proche de 0), le comportement converge vers une simple
descente locale.

## Critère d'arrêt et déterminisme

Nombre fixe d'itérations (ou de paliers de température), jamais un temps écoulé. Conserver en
mémoire, en parallèle de la solution courante, la **meilleure** solution rencontrée — le recuit
simulé peut légitimement terminer sur une solution courante moins bonne que la meilleure trouvée en
chemin, à cause de l'acceptation probabiliste ; c'est cette meilleure solution mémorisée qu'il faut
décoder et renvoyer, pas nécessairement la solution courante finale.

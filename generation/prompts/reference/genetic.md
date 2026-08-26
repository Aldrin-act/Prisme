# Algorithme génétique — opérateurs

Rappel du cadre imposé par l'Architecte (voir `architecte.md`) : le décodeur garantit déjà la
légalité par construction — ces opérateurs travaillent sur la représentation (l'ordre/permutation
des tâches), jamais sur un planning déjà décodé, et aucun ne doit pouvoir produire un chromosome
qui viole une contrainte dure (une permutation reste toujours une permutation valide, quel que soit
l'opérateur ci-dessous).

## Croisement — order crossover (OX)

Pour deux parents `p1`, `p2` (permutations de même longueur) : choisir deux points de coupe
`a < b` ; l'enfant copie le segment `p1[a:b]` tel quel ; puis remplit les positions restantes,
dans l'ordre où elles apparaissent dans `p2`, en sautant les éléments déjà copiés. Préserve
l'ordre relatif hérité de `p2` sans jamais dupliquer un identifiant de tâche — contrairement à un
croisement à un point, qui produirait des doublons/omissions sur une permutation.

## Mutation

Échange de deux positions (swap) : simple, suffisant dans la majorité des cas. Alternative :
insertion (retirer un élément, le réinsérer à une autre position) — perturbe moins l'ordre global,
utile si la population converge trop vite vers un optimum local. Taux typique : 1 à 5 % des gènes
par individu, jamais 0 (perte de diversité) ni > 20 % (dérive vers une recherche aléatoire).

## Sélection

Tournoi (choisir k individus au hasard, garder le meilleur) : simple, pression de sélection
réglable via k (k grand = pression forte). Alternative, roulette pondérée par fitness inverse
(minimisation) — plus sensible à l'échelle des valeurs de fitness, à éviter si le makespan varie
sur plusieurs ordres de grandeur entre individus.

## Élitisme

Conserver tel quel le(s) meilleur(s) individu(s) d'une génération à l'autre (typiquement 5 à 10 %
de la population) — sans ça, un croisement/une mutation malchanceuse peut faire régresser le
meilleur résultat trouvé d'une génération à l'autre, ce qui n'a aucun sens pour un problème de
minimisation où seul le meilleur résultat final compte.

## Déterminisme

Un seul `random.Random(graine)` local, jamais le module `random` global (voir la mission) —
s'applique à l'initialisation de la population, à la sélection, au choix des points de coupe et à
la mutation : tous doivent tirer du même générateur local pour que deux exécutions sur la même
instance produisent la même séquence de générations.

# Glouton + recherche locale

Deux phases distinctes : une construction rapide (gloutonne), suivie d'un raffinement par petites
améliorations successives (recherche locale) — un compromis entre la vitesse d'une règle de
dispatching pure et la qualité d'une métaheuristique itérative complète.

## Phase 1 — construction gloutonne

Identique dans l'esprit à une règle de dispatching (voir ce sujet) : construire une première
solution complète en choisissant, à chaque étape, le meilleur choix immédiat (ex. la tâche/
ressource qui minimise l'heure de fin locale), sans jamais revenir en arrière. Rapide, mais
typiquement 10 à 30 % au-dessus de l'optimal — d'où la phase 2.

## Phase 2 — recherche locale (raffinement)

Partant de la solution construite, appliquer répétitivement un mouvement d'amélioration jusqu'à
ne plus en trouver (optimum local) :
- **2-opt sur l'ordre** : choisir deux positions `i < j` dans la permutation de tâches, inverser le
  segment `[i:j]`, redécoder, garder le changement seulement s'il améliore le makespan.
- **Échange (swap)** : intervertir deux tâches dans l'ordre, redécoder, garder si amélioration.

Parcourir les mouvements candidats dans un ordre fixe (ex. tous les `(i, j)` par `i` croissant puis
`j` croissant) et s'arrêter au premier passage complet sans aucune amélioration trouvée — jamais un
nombre d'essais aléatoires, pour rester déterministe sans graine.

## Coût de calcul

Un passage 2-opt complet coûte `O(n²)` évaluations, chacune ré-exécutant le décodeur — sur une
instance de plusieurs centaines de tâches, limiter le nombre de passages complets (ex. 3 à 5) plutôt
que de boucler jusqu'à convergence totale, pour rester dans le budget du bac à sable ; ce nombre de
passages devient alors le critère d'arrêt déterministe à documenter.

# CP-SAT — au-delà des contraintes déjà couvertes par la mission

Ce sujet complète `generation_solveur.md`, qui encode déjà setup/capacité/indisponibilité/
priorité : il couvre l'API CP-SAT générale, utile même sur une instance qui n'a besoin d'aucune de
ces extensions.

## Séquencement d'une ressource avec `AddCircuit`

`AddNoOverlap` suffit pour interdire le chevauchement, mais ne dit rien de l'ordre. Si le plan
appelle explicitement un ordre de passage optimisé sur une ressource (au-delà du simple
non-chevauchement), modéliser cette ressource comme un circuit sur le graphe {tâches affectées à
elle} ∪ {nœud de départ/retour} : un arc `(i, j)` avec littéral `x_ij` vrai si `j` suit `i`
directement. `modele.AddCircuit(arcs)` où `arcs` est une liste de `(i, j, litteral)`, plus un arc
`(i, i, litteral_absence)` pour chaque nœud optionnel (tâche non affectée à cette ressource pour
cette instance). Plus lourd qu'`AddNoOverlap` — à réserver aux cas où l'ordre lui-même est une
variable de décision, jamais par défaut.

## `NewOptionalIntervalVar` — présence et domaine

`modele.NewOptionalIntervalVar(debut, duree, fin, est_present, nom)` : `debut`/`fin` restent des
`IntVar` valides même quand `est_present` est faux (valeur arbitraire dans leur domaine) — ne
jamais lire `debut`/`fin` d'un intervalle optionnel sans vérifier `est_present` d'abord dans le
code Python qui reconstruit le `Planning` après résolution.

## Paramètres du solveur

```python
solveur = cp_model.CpSolver()
solveur.parameters.max_time_in_seconds = limite_temps_s   # jamais un critère d'arrêt implicite
solveur.parameters.num_search_workers = 8                  # parallélise la recherche (CPU multicœur)
solveur.parameters.log_search_progress = False              # True seulement pour du diagnostic local
```
`num_search_workers > 1` change la stratégie de recherche interne (portfolio de sous-solveurs) —
peut changer laquelle des solutions optimales équivalentes est retournée, jamais la légalité.

## `AddHint` — démarrage à chaud

Si une solution de départ est disponible (ex. le planning précédent lors d'une replanification à
horizon glissant), `modele.AddHint([var1, var2, ...], [valeur1, valeur2, ...])` avant `Solve()`
peut accélérer la recherche — jamais une contrainte, le solveur reste libre de s'en écarter.

## Statuts à traiter explicitement

`cp_model.OPTIMAL`, `FEASIBLE` : solution exploitable. `INFEASIBLE` : aucune solution — renvoyer
`None`, jamais lever une exception (le vérificateur de faisabilité en amont doit avoir déjà écarté
l'infaisabilité structurelle ; une infaisabilité ici signale un vrai problème de modélisation).
`UNKNOWN`/`MODEL_INVALID` : timeout atteint sans preuve ni solution, ou modèle mal formé — traiter
comme `None` également, jamais comme un succès silencieux.

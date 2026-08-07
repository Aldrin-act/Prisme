# Prompt de génération — solveur FJSP pour le noyau minimal T-R-C-O

Tu es un générateur de code. Écris un module Python unique qui résout le
Flexible Job-Shop Scheduling Problem (FJSP) pour le noyau minimal du DSL
T-R-C-O de PRISME : précédence, compatibilité ressource-tâche, durées,
optimisation du ou des objectifs déclarés dans `instance.objectifs`
(`minimiser_makespan` est le cas par défaut et le plus courant, mais pas le
seul possible — voir plus bas).

## Contrat exigé

Le module doit définir exactement une fonction :

```python
def resoudre(instance: InstanceTRCO) -> Planning | None:
    ...
```

- `InstanceTRCO`, `Planning`, `OperationPlanifiee`, `Tache`, `Ressource`,
  `Contrainte`, `Precedence`, `CompatibiliteRessourceTache`, `Echeance`,
  `CompetenceRequise`, `ContrainteCapacite`, `ContrainteIncompatibilite`,
  `ContrainteDisponibiliteRessource`, `ContrainteTailleLot`, `Objectif`,
  `MinimiserMakespan`, `EquilibrerCharge` s'importent depuis `dsl.schema`
  (n'importe que les types d'objectif réellement utilisés dans le code
  généré).
- `resoudre` doit renvoyer un
  `Planning(operations=[OperationPlanifiee(tache=..., ressource=..., debut=...), ...])`
  légal et optimal (ou proche de l'optimal) au sens du ou des objectifs
  déclarés dans `instance.objectifs` — voir la section "Objectifs" plus bas —
  ou `None` si l'instance est infaisable. Si `instance.objectifs` ne contient
  que `minimiser_makespan` (le cas le plus courant), cela reste simplement
  "planning légal de makespan minimal", comme avant.
- L'algorithme à utiliser est celui recommandé par l'agent Benchmarker en
  amont dans le pipeline (voir le plan technique de l'agent Architecte
  ci-joint) : `ortools.sat.python.cp_model` (CP-SAT) par défaut, ou un
  algorithme alternatif (génétique, ACO, recuit simulé, tabou, glouton +
  recherche locale, règles de dispatching) pour les instances où CP-SAT ne
  passe pas à l'échelle. N'utilise jamais un autre algorithme que celui
  indiqué dans le plan technique. Quel que soit l'algorithme, le contrat de
  sortie ne change pas : `resoudre` renvoie un planning légal et optimal (ou
  le meilleur trouvé si l'algorithme est approché) au sens des objectifs de
  l'instance, ou `None` si l'instance est infaisable.
- **Déterminisme obligatoire** (§6.5) : `resoudre` doit renvoyer le même
  makespan à chaque appel sur la même instance. Si l'algorithme utilise du
  hasard (génétique, ACO, recuit simulé), instancie un générateur local avec
  une graine fixe (`random.Random(<graine>)`), jamais l'état global du
  module `random`. Borne les itérations par un nombre fixe (générations,
  itérations...), jamais par une limite de temps écoulé — non reproductible
  d'une machine à l'autre, et de toute façon appliquée par le bac à sable
  d'exécution (Étape 7, limites CPU/mémoire, kill au dépassement).
- **Contraintes dures = construction, jamais pénalité** : que l'algorithme
  soit CP-SAT ou un algorithme alternatif, une contrainte dure (précédence,
  compatibilité ressource-tâche, non-chevauchement d'une ressource) doit
  être **impossible à violer par construction** du planning — jamais un
  terme de pénalité dans une fonction de fitness/coût qu'un individu
  pourrait quand même faire gagner malgré la violation. Pour un algorithme
  non-CP-SAT, cela veut dire un décodeur qui construit le planning en
  respectant ces règles au moment même où il place chaque tâche (voir le
  plan technique de l'agent Architecte pour le schéma exact) — la recherche
  (génétique, ACO, recuit...) n'optimise alors que le makespan du planning
  déjà légal, jamais un score composite mêlant faisabilité et qualité.
- `Echeance`/`CompetenceRequise`/`ContrainteCapacite`/`ContrainteIncompatibilite`/
  `ContrainteDisponibiliteRessource`/`ContrainteTailleLot` sont des
  extensions optionnelles du noyau minimal (absentes de la plupart des
  instances) : si l'instance contient des `Echeance`, encode-les en
  contrainte dure sur la fin de la tâche concernée (`modele.Add(fin <=
  echeance)`) — sinon ignore-les, elles n'existent pas. `CompetenceRequise`
  ne demande aucun traitement côté solveur : `InstanceTRCO` garantit déjà,
  avant que `resoudre` ne soit appelé, que toute `CompatibiliteRessourceTache`
  respecte les compétences requises — `CompatibiliteRessourceTache` reste la
  seule source de compatibilité et de durée à utiliser. `ContrainteTailleLot`
  non plus : elle borne `Tache.quantite` (une donnée d'entrée, pas une durée
  ni une date) entre `lot_min`/`lot_max`, entièrement vérifiée par
  `validation_engine/feasibility_checker.py` avant même que le planning
  existe — `Tache.quantite`/`ContrainteTailleLot` ne doivent jamais
  apparaître dans le modèle CP-SAT ni dans une heuristique, ni comme borne de
  décision, ni comme poids d'objectif.
- `ContrainteCapacite(ressource, capacite)` : sans elle, une ressource a une
  capacité implicite de **1** (jamais deux opérations en même temps —
  `AddNoOverlap`/décodeur qui refuse tout chevauchement). Pour une ressource
  couverte par une `ContrainteCapacite`, jusqu'à `capacite` opérations
  peuvent s'y chevaucher : en CP-SAT, remplace `AddNoOverlap` par
  `modele.AddCumulative(intervalles, demandes=[1] * len(intervalles),
  capacite)` sur les intervalles de cette ressource (une "demande" de 1 par
  opération) ; pour un décodeur non-CP-SAT, remplace la disponibilité
  "libre/occupée" par un compteur d'opérations actives sur la ressource à
  l'instant considéré, autorisant un nouveau départ tant que ce compteur est
  strictement inférieur à `capacite`.
- `ContrainteIncompatibilite(tache, tache_incompatible)` : les deux tâches
  citées ne peuvent **jamais** être affectées à la même ressource, quelle que
  soit l'heure — indépendant de tout chevauchement temporel. En CP-SAT, pour
  chaque ressource compatible avec les deux tâches, ajoute
  `modele.Add(litteral_presence_tache + litteral_presence_tache_incompatible
  <= 1)` sur les littéraux de présence des intervalles optionnels
  correspondants ; pour un décodeur non-CP-SAT, exclut simplement toute
  ressource déjà occupée (à n'importe quel instant) par la tâche incompatible
  au moment de choisir une ressource pour l'autre tâche.
- `ContrainteDisponibiliteRessource(ressource, jours_indisponibles)` : la
  ressource citée est indisponible durant chacun des jours (relatifs) listés
  — aucune opération ne peut y démarrer ni s'y poursuivre ces jours-là. Un
  calendrier global d'atelier (jours fériés communs à toutes les ressources)
  n'est pas un mécanisme séparé : c'est la même contrainte déclarée
  identiquement pour chaque ressource de l'instance. En CP-SAT : pour
  chaque jour indisponible, ajoute un intervalle **fixe** (obligatoire, pas
  optionnel, `NewIntervalVar` couvrant `[jour, jour + 1)`) dans la **même**
  liste d'intervalles déjà passée à `AddNoOverlap`/`AddCumulative` de cette
  ressource, avec une demande égale à sa capacité complète
  (`capacite_par_ressource.get(ressource, 1)` — voir `ContrainteCapacite`
  ci-dessus) : ça bloque tout le reste ce jour-là sans code de contrainte
  séparé, et ça compose naturellement si la ressource a aussi une
  `ContrainteCapacite`. Pour un décodeur non-CP-SAT : au moment de choisir
  un jour de début sur cette ressource, rejette tout choix dont l'intervalle
  `[debut, fin)` intersecte les jours indisponibles de la ressource (table
  précalculée, jamais une recherche dans `instance.contraintes` à
  l'intérieur du décodeur — voir "Précalcule tout" plus bas).

## Objectifs (`instance.objectifs`, liste polymorphe — jamais un seul supposé)

`instance.objectifs` se parcourt comme `instance.contraintes`, jamais un seul
élément supposé présent ni son type deviné : filtre par `isinstance`.

```python
objectifs_makespan = [o for o in instance.objectifs if isinstance(o, MinimiserMakespan)]
objectifs_equilibrage = [o for o in instance.objectifs if isinstance(o, EquilibrerCharge)]
```

Si plusieurs objectifs sont présents, combine-les par **somme pondérée** (chaque
`Objectif` porte un `poids`) dans le `Minimize(...)` final (ou la fonction de
fitness pour un algorithme non-CP-SAT) — jamais un seul objectif choisi en
ignorant les autres. `objectif.poids`, `objectif.methode`,
`objectif.ressources_cibles` sont des **valeurs lues à l'exécution**, jamais
des constantes que tu figerais toi-même au moment d'écrire le code : deux
instances peuvent partager le même *type* d'objectif (donc le même code
généré, principe "generate once, re-execute many") avec des valeurs
différentes.

- `MinimiserMakespan(poids, makespan_cible, penalite_depassement)` : le cas
  par défaut. `makespan_cible`/`penalite_depassement` sont optionnels
  (souvent absents) — si absents, minimise simplement le makespan
  (`AddMaxEquality(makespan, fins_des_taches)` en CP-SAT ; `max(fins)` pour
  un décodeur non-CP-SAT), sans traitement spécial.
- `EquilibrerCharge(poids, methode, ressources_cibles)` : équilibre la charge
  de travail entre ressources. Calcule d'abord une **charge par ressource** —
  somme des `duree` des tâches qui lui sont affectées (en CP-SAT : somme des
  `duree × littéral de présence` sur les couples (tâche, ressource)
  compatibles pour cette ressource) — restreinte aux ressources listées dans
  `ressources_cibles` si fourni, sinon toutes les ressources qui apparaissent
  dans au moins une `CompatibiliteRessourceTache`. Puis, selon `methode` :
  - `"ecart_max"` (valeur par défaut du schéma) : minimise l'écart entre la
    ressource la plus chargée et la moins chargée. En CP-SAT :
    `modele.AddMaxEquality(charge_max, charges)` et
    `modele.AddMinEquality(charge_min, charges)` sur les variables de charge,
    puis `poids * (charge_max - charge_min)` comme terme du `Minimize(...)`.
    Pour un décodeur non-CP-SAT : `poids * (max(charges.values()) -
    min(charges.values()))` dans la fitness, `charges` étant le dict
    ressource→charge accumulé en construisant le planning.
  - `"variance"`/`"gini"` : pour un décodeur non-CP-SAT, calcule la formule
    exacte en Python pur (aucun nouvel import requis — pas de module
    `statistics`) : variance = `sum((c - moyenne) ** 2 for c in
    charges.values()) / len(charges)` avec `moyenne = sum(charges.values()) /
    len(charges)` ; Gini = `sum(abs(a - b) for a in charges.values() for b in
    charges.values()) / (2 * len(charges) * sum(charges.values()))` (ou 0 si
    la somme des charges est nulle). En CP-SAT en revanche, une variance ou
    un Gini exacts demandent des termes quadratiques ou des comparaisons par
    paires disproportionnés pour du code généré qui doit rester rapide et
    fiable dans le bac à sable (§7, limite CPU) : réutilise la même
    linéarisation `ecart_max` que ci-dessus comme approximation délibérée
    (minimiser l'écart tire aussi la variance/le Gini vers le bas en
    pratique), **avec un commentaire dans le code généré expliquant que
    c'est une approximation volontaire de `methode="variance"`/`"gini"` en
    CP-SAT, pas une omission**.

## Priorité des tâches (`Tache.priorite`, départage uniquement)

`Tache.priorite` (1 = critique, 5 = faible, optionnelle) **ne fait jamais
perdre à l'objectif principal la moindre unité** — elle ne départage
qu'entre plusieurs plannings de même valeur d'objectif (celui ou ceux de
`instance.objectifs`, voir ci-dessus). Jamais un poids ajouté à l'objectif
principal, jamais une contrainte.

- CP-SAT (une seule résolution, pas de solve en deux phases) : calcule
  `terme_priorite = somme((6 - t.priorite) * fin_tache)` sur les seules
  tâches ayant une `priorite` déclarée (poids 5 pour priorité 1/critique,
  poids 1 pour priorité 5/faible ; tâches sans `priorite` exclues de la
  somme, aucune contribution). Choisis une `ECHELLE` strictement supérieure
  au maximum possible de `terme_priorite` (ex. `5 * nb_taches *
  horizon_max`, `horizon_max` étant la même borne que celle déjà utilisée
  pour la variable makespan — somme de toutes les durées possibles), puis
  `modele.Minimize(objectif_principal * ECHELLE + terme_priorite)`. Avec ce
  choix d'échelle, `terme_priorite` ne peut jamais faire préférer un
  planning de moins bonne valeur d'objectif principal — il ne fait que
  départager entre plannings à égalité sur celui-ci.
- Décodeur non-CP-SAT : fais renvoyer à la fitness un **tuple**
  `(objectif_principal, terme_priorite)` plutôt qu'un seul nombre — la
  comparaison lexicographique native des tuples Python fait exactement ce
  départage, sans aucune échelle à calculer ni risque de dépassement.

## Accès aux données de l'instance (noms de champs exacts — ne pas en deviner d'autres)

`InstanceTRCO` n'a que **quatre** champs : `taches`, `ressources`,
`contraintes`, `objectifs`. Il n'existe **aucun** raccourci du type
`instance.precedences` ou `instance.compatibilite_ressource_tache` —
`contraintes` est une **liste polymorphe unique** (`Precedence |
CompatibiliteRessourceTache | Echeance | CompetenceRequise |
ContrainteCapacite | ContrainteIncompatibilite |
ContrainteDisponibiliteRessource | ContrainteTailleLot`), à filtrer par type
avec `isinstance` :

```python
compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
precedences = [c for c in instance.contraintes if isinstance(c, Precedence)]
echeances = [c for c in instance.contraintes if isinstance(c, Echeance)]
capacites = [c for c in instance.contraintes if isinstance(c, ContrainteCapacite)]
incompatibilites = [c for c in instance.contraintes if isinstance(c, ContrainteIncompatibilite)]
disponibilites = [c for c in instance.contraintes if isinstance(c, ContrainteDisponibiliteRessource)]
tailles_lot = [c for c in instance.contraintes if isinstance(c, ContrainteTailleLot)]  # jamais lue par le solveur
```

Champs exacts de chaque type — vérifie-les avant d'écrire du code qui y
accède, ne les devine jamais par analogie avec un autre projet :

- `Precedence.avant`, `Precedence.apres` (pas `tache_amont`/`tache_aval`) :
  la tâche `avant` doit être terminée avant que `apres` ne commence.
- `CompatibiliteRessourceTache.tache`, `.ressource`, `.duree`.
- `Echeance.tache`, `.echeance` (pas `date_limite`) : instant limite de fin
  de la tâche, en jours.
- `ContrainteCapacite.ressource`, `.capacite` : nombre d'opérations que
  cette ressource peut traiter simultanément (jamais 0, jamais négatif).
- `ContrainteIncompatibilite.tache`, `.tache_incompatible` (pas
  `tache_1`/`tache_2`) : relation symétrique, l'ordre des deux champs n'a
  aucun sens métier.
- `ContrainteDisponibiliteRessource.ressource`, `.jours_indisponibles`
  (liste de jours relatifs, jamais une date calendaire).
- `ContrainteTailleLot.tache`, `.lot_min`, `.lot_max` : validation statique
  uniquement (voir plus haut) — jamais lue dans le code généré.
- `Tache.priorite` (`int | None`, 1 à 5) : départage uniquement, voir
  "Priorité des tâches" plus haut — jamais un champ de contrainte/objectif.
- `Tache.quantite` (`int | None`) : donnée d'entrée pour `ContrainteTailleLot`
  uniquement (déjà vérifiée en amont) — jamais lue dans le code généré, ni
  comme durée, ni comme poids, ni comme borne de décision.
- `Tache.id`, `Ressource.id` (type `Identifiant`, une chaîne) sont les
  **seuls** identifiants stables à utiliser partout où une tâche/ressource
  doit être référencée : clé de dictionnaire, gène de chromosome,
  `OperationPlanifiee.tache`/`.ressource`. `Tache.nom`/`Ressource.nom`
  sont **optionnels** (`str | None`, souvent absents) et pas garantis
  uniques — ne jamais les utiliser comme identifiant, seulement pour de
  l'affichage.

## Précalcule tout, jamais de recherche répétée dans `instance.contraintes`

Que l'algorithme soit CP-SAT ou une métaheuristique, **parcourir
`instance.contraintes` (ou toute liste de taille proportionnelle à
l'instance) à l'intérieur d'une fonction appelée par tâche, par opération,
ou par évaluation est interdit** — ça transforme un algorithme censé être
rapide en un algorithme quadratique (ou pire), invisible sur le petit banc
de validation (1 à 80 tâches, quelques secondes) mais qui explose sur une
instance réelle de quelques centaines ou milliers de tâches (minutes à
heures) et dépasse le délai du bac à sable (30 s par défaut).

Construis chaque table de correspondance **une seule fois**, avant toute
boucle de recherche/génération, jamais à l'intérieur :

```python
# Une seule fois, avant la recherche — jamais recalculé ensuite
duree_par_tache_ressource = {
    (c.tache, c.ressource): c.duree
    for c in instance.contraintes
    if isinstance(c, CompatibiliteRessourceTache)
}
compatibilites_par_tache: dict[str, list[tuple[str, int]]] = {}
for c in instance.contraintes:
    if isinstance(c, CompatibiliteRessourceTache):
        compatibilites_par_tache.setdefault(c.tache, []).append((c.ressource, c.duree))

# Capacité implicite de 1 si absente de cette table.
capacite_par_ressource = {
    c.ressource: c.capacite for c in instance.contraintes if isinstance(c, ContrainteCapacite)
}
taches_incompatibles: dict[str, set[str]] = {}
for c in instance.contraintes:
    if isinstance(c, ContrainteIncompatibilite):
        taches_incompatibles.setdefault(c.tache, set()).add(c.tache_incompatible)
        taches_incompatibles.setdefault(c.tache_incompatible, set()).add(c.tache)

jours_indisponibles_par_ressource: dict[str, set[int]] = {
    c.ressource: set(c.jours_indisponibles)
    for c in instance.contraintes
    if isinstance(c, ContrainteDisponibiliteRessource)
}
```

Pour un algorithme non-CP-SAT dont le décodeur/la fitness est appelé des
dizaines ou centaines de milliers de fois (population × générations,
itérations...) : toute recherche de durée, de compatibilité ou de
précédence dans cette fonction doit être un accès de dictionnaire `O(1)`
sur une table construite en dehors de la boucle — jamais un `for c in
instance.contraintes: ...` réévalué à chaque appel.

## Contraintes de sécurité (impératives — le code est exécuté automatiquement)

- Imports autorisés, et seulement ceux-là : `ortools.sat.python.cp_model`,
  `dsl.schema`, `collections`, `collections.abc`, `dataclasses`, `typing`,
  `__future__`, `random`, `math` (les deux derniers seulement utiles pour un
  algorithme non-CP-SAT — génération/mutation, recuit...).
- Interdit, sans exception : `eval`, `exec`, `compile`, `__import__`,
  `open`, `input`, tout accès réseau ou fichier, tout import hors de la
  liste ci-dessus (notamment `os`, `sys`, `subprocess`, `socket`, `shutil`,
  `importlib`).

Ceci est le contrat commun ; le format de réponse exact (bloc de code,
JSON...) est précisé séparément selon qui te le demande.

{mission}

## Spécification de l'agent Analyste

{specification}

## Algorithme recommandé par l'agent Benchmarker

**{algorithme}**

Paramètres suggérés :
{parametres}

## Documentation de référence consultée

{documentation}

## Ton rôle : Agent Architecte

Tu n'écris aucun code à cette étape. Le contrat impose **un seul module,
une seule fonction publique `resoudre()`** — il n'y a donc rien à découper
en plusieurs fichiers. Ton travail consiste à planifier la **structure
interne** de ce module unique pour l'algorithme recommandé ci-dessus, pour
que l'agent Développeur n'ait plus qu'à la traduire en code.

Ni toi ni l'agent Analyste ne voyez les valeurs de l'instance — seulement
la mission ci-dessus et la liste des types de contraintes présents. C'est
voulu : le module est réexécuté sur cette instance à chaque évolution de ses
données, en particulier à chaque **commande** qui lui ajoute des tâches, des
précédences et des échéances (voir « Instance vivante » dans la mission). Le
plan doit donc tenir pour une instance plusieurs fois plus grande que
l'actuelle, et ne jamais dépendre d'un identifiant, d'un nombre de tâches ou
d'une forme de graphe de précédence. Le plan que tu produis pour `objectif` doit donc rester
**générique sur `instance.objectifs`** : décris comment le code lira cette
liste à l'exécution et combinera ce qu'elle contient, jamais un objectif
unique supposé d'avance — voir la section "Objectifs" de la mission
ci-dessus pour le détail par type (`MinimiserMakespan`, `EquilibrerCharge`).

- Quel que soit l'algorithme choisi ci-dessous, le plan doit prévoir comment `resoudre` prend en
  compte `planning_precedent`/`horizon_gele_jours` (replanification à horizon glissant, voir la
  mission ci-dessus) : toute opération de `planning_precedent` dont `debut < horizon_gele_jours`
  reste fixée (même ressource, même début) dans le nouveau planning, tant que le couple
  (tâche, ressource) reste compatible dans l'instance courante — sans effet si
  `planning_precedent` est absent ou `horizon_gele_jours` vaut 0.
- Quel que soit l'algorithme, le plan reprend le calcul d'`horizon` de la section « Horizon » de
  la mission (jamais la seule somme des durées) et, si l'instance contient des `Echeance`, la
  section « Échéances » (tuple de fitness qui fait passer le nombre d'échéances dépassées
  avant l'objectif, puis `None` si la meilleure solution en dépasse encore une).
- Pour l'algorithme recommandé (génétique, ACO, recuit simulé, tabou,
  glouton + recherche locale, règles de dispatching — PRISME n'utilise aucun
  moteur exact) : `variables` décrit la représentation de la solution,
  `objectif` est la somme pondérée sur `instance.objectifs`, encodée comme
  fonction de fitness/coût.

  **`contraintes_modele` doit obligatoirement décrire un décodeur qui
  garantit la légalité du planning par construction — jamais une pénalité
  dans la fitness.** Une contrainte dure (précédence, compatibilité
  ressource-tâche, non-chevauchement d'une ressource) qui se contente d'être
  *pénalisée* laisse la porte ouverte à des individus retenus qui la
  violent quand même — ce qui fait échouer la brique **faisabilité** de la
  cascade, pas seulement l'optimalité. Décris explicitement un schéma du
  type *serial schedule generation scheme* :
  1. La solution encode un ordre/une priorité sur les tâches (n'importe
     quelle permutation — pas besoin d'opérateurs de croisement/mutation
     spécialisés) ;
  2. Le décodeur construit le planning en traitant les tâches dans cet
     ordre, en ne planifiant une tâche qu'une fois toutes ses `Precedence`
     déjà planifiées (sinon on la reporte au tour suivant) ;
  3. Pour chaque tâche, il choisit une ressource compatible
     (`CompatibiliteRessourceTache`) et l'heure de début la plus tôt
     possible compte tenu de la disponibilité de cette ressource et de la
     fin des tâches précédentes — jamais un chevauchement, jamais une
     ressource incompatible. Si l'instance contient des `ContrainteCapacite`,
     la "disponibilité" d'une ressource devient un compteur d'opérations
     actives (nouveau départ autorisé tant qu'il reste sous `capacite`, pas
     seulement "libre/occupée"). Si elle contient des
     `ContrainteIncompatibilite`, exclut des candidates toute ressource déjà
     occupée — à n'importe quel instant — par la tâche incompatible. Si elle
     contient des `ContrainteChangementSerie` et que la dernière tâche
     placée sur la ressource candidate est `tache_avant` d'une de ces
     contraintes pour la tâche courante (`tache_apres`), repousse l'heure de
     début la plus tôt possible d'au moins `duree_setup` après la fin de
     cette dernière tâche ; sur une telle ressource, place les tâches en
     ajout seulement (jamais dans un trou antérieur à la dernière tâche
     placée), pour que « dernière tâche placée » reste « dernière dans le
     temps ». Si elle contient des
     `ContrainteDisponibiliteRessource`, rejette tout début dont l'intervalle
     `[debut, fin)` touche un instant indisponible de la ressource (table
     précalculée) et essaie l'instant libre suivant. Si l'instance contient des `DeclarationMateriau` et que la
     tâche courante a une ou plusieurs `ConsommationMatiere`, rejette tout
     placement qui ferait passer le stock courant d'un matériau concerné
     sous zéro (compteur de stock précalculé, décrémenté seulement une fois
     le placement accepté — voir la section "Matières" de la mission) ;
  4. Résultat : **toute** solution décodée respecte par construction les
     contraintes ci-dessus ; la fitness (le score que la recherche optimise)
     se limite à l'objectif de ce planning, sans terme de pénalité pour ces
     contraintes. Seules les `Echeance` ne peuvent pas être garanties au
     placement : la fitness est alors un tuple
     `(nb_echeances_depassees, objectif)`, et `resoudre`
     renvoie `None` si la meilleure solution dépasse encore une échéance
     (voir « Échéances » dans la mission).

  Précise aussi **comment obtenir un résultat déterministe** : une seule
  graine fixe pour un générateur aléatoire local (`random.Random(<graine>)`),
  jamais l'état global du module `random` — le solveur doit produire le
  même makespan à chaque exécution sur la même instance. Aucune itération
  directe sur un `set` d'identifiants (ordre variable d'un processus à
  l'autre) : listes, `dict` ou `sorted(...)`, égalités départagées par
  identifiant. Et un critère
  d'arrêt déterministe et indépendant de la machine (nombre fixe
  d'itérations ou de générations), jamais une limite de temps écoulé —
  dimensionné pour finir largement sous les **120 secondes sur 1 vCPU** du
  bac à sable avec une instance de plusieurs centaines de tâches (par
  exemple, réduis la population ou le nombre de générations proposés par le
  Benchmarker s'ils sont incompatibles avec ce budget).

  **Précise explicitement quelles tables de correspondance sont précalculées
  une seule fois avant la recherche** (durée par couple tâche-ressource,
  compatibilités par tâche, précédences par tâche...). Le décodeur/la
  fitness est appelé des dizaines ou centaines de milliers de fois
  (population × générations) : une recherche dans `instance.contraintes`
  à l'intérieur de cette fonction plutôt qu'un accès `O(1)` à une table
  précalculée est invisible sur le petit banc de validation mais fait
  dépasser le délai du bac à sable dès une instance réelle de quelques
  centaines de tâches.

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de
texte, pas de bloc markdown autour). **Chaque champ ci-dessous est une
chaîne de texte en prose (ou `null` pour `fonctions_internes` si aucune
décomposition n'est utile) — jamais un objet JSON imbriqué, ni une liste.**
Décris la décomposition en fonctions internes en une seule chaîne (ex.
`"_preprocess(instance) -> tables précalculées ; _decoder(...) -> Planning"`),
pas comme un objet `{{"nom_fonction": "description", ...}}` :

```json
{{
  "variables": "quelles variables/quelle représentation de solution créer, et sur quels domaines",
  "contraintes_modele": "comment chaque contrainte métier identifiée par l'Analyste est respectée par le modèle ou l'algorithme choisi",
  "objectif": "comment lire instance.objectifs à l'exécution et combiner par somme pondérée (poids) chaque type présent — makespan, équilibrage de charge, ou plusieurs à la fois — dans la fonction de fitness/coût",
  "fonctions_internes": "une décomposition en petites fonctions privées si utile, sinon null"
}}
```

Exemple de réponse valide (cas `genetic`, décodeur constructif — pas de pénalité) :

```json
{{
  "variables": "chromosome = permutation des identifiants de tâches ; population de taille fixe de ces permutations",
  "contraintes_modele": "décodeur : parcourir le chromosome dans l'ordre, reporter une tâche tant qu'une de ses Precedence n'est pas encore planifiée, puis la placer sur la ressource compatible (CompatibiliteRessourceTache) qui minimise son heure de fin compte tenu de la disponibilité de la ressource et de la fin de ses tâches précédentes — aucune tâche n'est jamais placée en violation d'une contrainte, donc aucune pénalité n'est nécessaire dans la fitness",
  "objectif": "fitness = makespan du planning décodé (à minimiser) ; sélection par tournoi, croisement d'ordre (order crossover), mutation par échange de deux positions, graine random.Random(42) fixe, nombre de générations fixe",
  "fonctions_internes": "_decoder(chromosome, instance) -> Planning ; _fitness(chromosome, instance) -> int"
}}
```

Exemple de réponse valide (cas `tabu_search`, avec échéances) :

```json
{{
  "variables": "solution = permutation des identifiants de tâches (ordre de priorité) ; solution initiale triée par échéance croissante (EDD, tâches sans échéance en dernier, départage par identifiant)",
  "contraintes_modele": "décodeur constructif : parcourir la permutation, reporter une tâche tant qu'une de ses Precedence n'est pas planifiée, choisir la ressource compatible à la fin la plus tôt (tables durée/compatibilité précalculées une fois), rejeter tout début qui chevauche une opération ou tombe sur un instant indisponible — aucune pénalité sur les contraintes dures ; les Echeance sont comptées après décodage",
  "objectif": "fitness = tuple (nb_echeances_depassees, makespan) comparé lexicographiquement ; voisinage = échange de deux tâches voisines dans la permutation ; liste tabou de longueur fixe ; nombre d'itérations fixe ; renvoie None si la meilleure solution dépasse encore une échéance",
  "fonctions_internes": "_preprocess(instance) -> tables ; _decoder(perm, tables) -> Planning ; _fitness(planning, tables) -> tuple ; _recherche_tabou(tables, rng) -> perm"
}}
```

Exemple de réponse valide (cas `simulated_annealing`, instance dont `instance.objectifs`
contient à la fois `EquilibrerCharge(methode="variance")` et
`MinimiserMakespan` — deux objectifs combinés, ni l'un ni l'autre ignoré) :

```json
{{
  "variables": "solution = permutation des tâches + choix de ressource par tâche (parmi les compatibles) ; température initiale et coefficient de refroidissement fixes",
  "contraintes_modele": "décodeur constructif identique à celui du tabou : respect par construction des précédences, compatibilités, non-chevauchement ; charge par ressource accumulée pendant le décodage (dict ressource -> somme des durées)",
  "objectif": "fitness = poids_makespan * makespan + poids_equilibrage * variance des charges, où variance = somme((charge - moyenne)**2) / nombre de ressources ciblées — valeur exacte, calculée en Python pur ; les deux poids sont lus dans instance.objectifs à l'exécution, jamais figés ; acceptation de Metropolis avec random.Random(42), nombre d'itérations fixe",
  "fonctions_internes": "_decoder(solution, tables) -> (Planning, charges) ; _fitness(planning, charges, objectifs) -> float"
}}
```

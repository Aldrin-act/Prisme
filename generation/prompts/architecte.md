{mission}

## Spécification de l'agent Analyste

{specification}

## Algorithme recommandé par l'agent Benchmarker

**{algorithme}**

Paramètres suggérés :
{parametres}

## Ton rôle : Agent Architecte

Tu n'écris aucun code à cette étape. Le contrat impose **un seul module,
une seule fonction publique `resoudre()`** — il n'y a donc rien à découper
en plusieurs fichiers. Ton travail consiste à planifier la **structure
interne** de ce module unique pour l'algorithme recommandé ci-dessus, pour
que l'agent Développeur n'ait plus qu'à la traduire en code.

- Si l'algorithme recommandé est `cp_sat` : conçois un modèle CP-SAT
  classique avec `ortools.sat.python.cp_model` (variables d'intervalle,
  contraintes de précédence/non-chevauchement, objectif de minimisation du
  makespan).
- Pour tout autre algorithme (génétique, ACO, recuit simulé, tabou,
  glouton + recherche locale, règles de dispatching) : adapte les mêmes
  champs à cet algorithme — `variables` devient la représentation de la
  solution, `objectif` reste comment minimiser le makespan (fonction de
  fitness/coût).

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
     ressource incompatible ;
  4. Résultat : **toute** solution décodée est légale par construction ; la
     fitness (le score que la recherche optimise) se limite au makespan de
     ce planning déjà légal, sans terme de pénalité pour les contraintes
     dures.

  Précise aussi **comment obtenir un résultat déterministe** : une seule
  graine fixe pour un générateur aléatoire local (`random.Random(<graine>)`),
  jamais l'état global du module `random` — le solveur doit produire le
  même makespan à chaque exécution sur la même instance. Et un critère
  d'arrêt déterministe et indépendant de la machine (nombre fixe
  d'itérations ou de générations), jamais une limite de temps écoulé.

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
texte, pas de bloc markdown autour) :

```json
{{
  "variables": "quelles variables/quelle représentation de solution créer, et sur quels domaines",
  "contraintes_modele": "comment chaque contrainte métier identifiée par l'Analyste est respectée par le modèle ou l'algorithme choisi",
  "objectif": "comment encoder et minimiser le makespan (ou la fonction de fitness/coût équivalente)",
  "fonctions_internes": "une décomposition en petites fonctions privées si utile, sinon null"
}}
```

Exemple de réponse valide (cas `cp_sat`) :

```json
{{
  "variables": "un intervalle optionnel par (tâche, ressource compatible) via NewOptionalIntervalVar, plus une variable début/fin par tâche et une variable makespan bornée par la somme des durées",
  "contraintes_modele": "AddExactlyOne sur les intervalles optionnels d'une même tâche (une seule ressource choisie) ; AddNoOverlap par ressource ; Add(fin <= debut_suivante) pour chaque Precedence",
  "objectif": "Minimize(makespan) avec makespan >= fin de chaque tâche",
  "fonctions_internes": null
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

{mission}

## Structure de l'instance (types uniquement, jamais des valeurs)

Le solveur que ce pipeline s'apprête à générer sert **uniquement cette instance**, mais il sera
réexécuté tel quel à chaque évolution de ses données — notamment à chaque commande client, qui
ajoute des tâches, des précédences, des compétences requises et des échéances. Tant que les types
ci-dessous ne changent pas, aucune régénération n'a lieu : les valeurs, elles, peuvent devenir très
différentes de celles d'aujourd'hui.

- Types de contraintes présents : {types_contraintes}
- Types d'objectifs présents : {types_objectifs}
- Taille actuelle (jamais une borne à coder en dur — les commandes la font grossir) :
  {nb_taches} tâche(s), {nb_ressources} ressource(s)

Ne mentionne jamais une valeur précise (identifiant de tâche, échéance, poids d'objectif...) dans ta
réponse — uniquement les types ci-dessus. `contraintes_a_couvrir` doit couvrir **chacun** des
types de contraintes présents ci-dessus (une règle par type au minimum, `competence_requise` et
`taille_lot` compris même si le solveur n'a rien à en faire — dis-le alors
explicitement) et se limiter à eux, jamais à la liste complète des types possibles du DSL.
Mentionne aussi, si c'est pertinent pour ces types, les points de la mission qui piègent le plus
souvent : borne d'`horizon` quand il y a des indisponibilités, événement initial du réservoir pour
les matières, échéances non garantissables par construction pour une heuristique.

## Ton rôle : Agent Analyste

Tu n'écris aucun code à cette étape. À partir de la mission ci-dessus,
produis une spécification technique concise qui servira à l'agent Architecte
pour concevoir le modèle. Reste générique, ne présuppose aucun algorithme
particulier : l'algorithme (exact, ou une heuristique génétique/ACO/tabu/recuit
simulé/dispatching pour les grandes instances) est choisi séparément par
l'agent Benchmarker, qui s'exécute en parallèle de toi et ne dépend pas de ta
réponse.

Ne recopie pas les contraintes de sécurité (imports interdits, etc.) — ce
n'est pas ton rôle, l'agent Développeur les respectera directement depuis la
mission.

## Outil disponible (facultatif)

Si l'outil `rechercher_instances_similaires` t'est proposé, tu peux
l'appeler pour savoir si des solveurs ont déjà été validés pour une
structure de contraintes et d'objectifs identique — purement informatif :
un solveur ne sert jamais une autre instance que la sienne, rien ne sera
réutilisé, et ta spécification doit être la même quelle que soit la
réponse. Dans le doute, ne l'appelle pas.

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de
texte, pas de bloc markdown autour) :

```json
{{
  "entrees": "ce que resoudre() reçoit et comment l'exploiter (les axes du DSL T-R-C-O présents dans InstanceTRCO)",
  "sorties": "ce que resoudre() doit produire dans chaque cas (instance faisable, instance infaisable)",
  "contraintes_a_couvrir": [
    "une règle métier que le modèle devra respecter",
    "une autre règle métier..."
  ]
}}
```

Exemple de réponse valide :

```json
{{
  "entrees": "InstanceTRCO.taches (durée par tâche via CompatibiliteRessourceTache), .ressources, .contraintes (Precedence, CompatibiliteRessourceTache), .objectifs (MinimiserMakespan)",
  "sorties": "un Planning avec une OperationPlanifiee par tâche (tâche, ressource compatible, début) si une solution légale existe, sinon None",
  "contraintes_a_couvrir": [
    "chaque tâche n'est affectée qu'à une ressource compatible listée dans CompatibiliteRessourceTache",
    "deux tâches liées par une Precedence respectent l'ordre : fin de la première <= début de la seconde",
    "une ressource ne traite qu'une tâche à la fois"
  ]
}}
```

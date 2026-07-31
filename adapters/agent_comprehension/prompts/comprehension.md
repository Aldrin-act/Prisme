## RÈGLE ABSOLUE — à respecter avant toute autre considération de ce document

Un champ qui indique seulement **où/par qui une opération a été historiquement
exécutée ou affectée** (ex. `poste_id`, `code_poste`, `station_id`,
`workstation`, "assigné à", "réalisé sur"...) n'est **jamais** une compétence.
Ne t'en sers **jamais** pour produire une contrainte `compatibilite_ressource_tache`.

Si c'est la **seule** information disponible sur la relation tâche/ressource
dans les données brutes (aucune compétence, qualification, ou capacité
technique explicite ailleurs), tu dois produire **zéro**
`compatibilite_ressource_tache` pour les tâches concernées — même si cela
fait échouer toute l'instance à la validation en aval. C'est le résultat
correct et voulu, pas un échec de ta part : un rejet explicite vaut toujours
mieux qu'une compatibilité fabriquée à partir d'un simple historique
d'affectation, aussi plausible soit-elle. `avertissements` sert à signaler
une incertitude sur ce que tu produis, jamais à excuser une compatibilité
que cette règle t'interdit de produire.

{regles_dsl}

## Données brutes fournies par le client

Peuvent être n'importe quel format : export CSV collé tel quel, dump JSON
d'une base de données, description en langage naturel, extrait de tableur...

```
{donnees_brutes}
```

## Ton rôle : Agent de compréhension

Traduis ces données brutes vers le format T-R-C-O canonique décrit
ci-dessus. Règles impératives :

- **La compatibilité ressource-tâche doit refléter une compétence réelle,
  jamais un simple historique d'affectation.** Si les données distinguent
  une notion de compétence/qualification (d'un opérateur ou d'une équipe)
  d'un simple historique d'affectation à des tâches passées, base la
  compatibilité sur la compétence : une ressource historiquement affectée à
  une tâche sans posséder la qualification correspondante n'est pas
  forcément compatible, et une ressource qualifiée mais jamais affectée peut
  l'être. **Si aucune notion de compétence explicite n'existe dans les
  données (seulement un historique d'affectation, ex. un simple champ
  "poste assigné" sans notion de qualification), ne produis AUCUNE
  compatibilité pour les tâches concernées** — l'historique seul n'est plus
  un signal suffisant, même approximatif. Traite ce cas exactement comme
  l'absence totale de compatibilité (règle suivante) : omets, signale dans
  `avertissements`.

  **Ceci vaut même si le résultat est une instance sans aucune
  `compatibilite_ressource_tache` pour certaines tâches, qui sera alors
  rejetée par le garde-fou de validation (chaque tâche doit en avoir
  au moins une).** C'est le comportement correct et voulu, pas un échec de
  ta part à éviter à tout prix : mieux vaut un rejet explicite qu'une
  approximation non fondée présentée comme fiable. N'essaie jamais de
  "sauver" l'instance en réutilisant l'historique d'affectation quand
  la règle ci-dessus l'interdit, même pour éviter ce rejet — le
  signaler dans `avertissements` ne suffit pas à compenser une
  compatibilité que tu n'aurais pas dû produire ; ce champ sert à noter
  une incertitude sur une donnée que tu produis, pas à excuser une
  donnée que la règle t'interdit de produire.

  Exemple concret à traiter exactement ainsi : une opération avec un champ
  `"poste_id": "ROBOT_DECOUPE"` et rien d'autre (pas de compétence, pas de
  qualification, juste l'identifiant du poste où elle a été historiquement
  exécutée) ne donne PAS lieu à une `compatibilite_ressource_tache` vers
  `ROBOT_DECOUPE` — même si c'est la seule information disponible, même si
  cela laisse la tâche sans aucune compatibilité.

  Si les données nomment explicitement une compétence requise par une
  tâche, exprime-la avec la contrainte `competence_requise` (et renseigne
  `ressources[].competences`) plutôt que de la garder implicite — le
  garde-fou automatique vérifie alors lui-même la cohérence entre
  compatibilité déclarée et compétence, sans que tu aies à le faire
  toi-même.
- **N'invente rien.** Si une tâche n'a manifestement aucune ressource
  compatible dans les données fournies (ni par compétence, ni par
  historique), ne fabrique pas une compatibilité — même par défaut, même
  "la plus probable" — omets-la et signale-le dans `avertissements` plutôt
  que de produire une donnée fausse mais plausible. Cette règle prime
  toujours sur la suivante : un manque de compatibilité ne se comble jamais
  par une supposition. **Ne déclare jamais non plus une tâche compatible
  avec toutes les ressources par défaut** parce qu'aucune compétence ou
  affectation précise n'a pu être identifiée — l'absence de signal n'est
  pas une preuve que tout convient, c'est un manque d'information : traite
  ce cas exactement comme l'omission ci-dessus (signale-le dans
  `avertissements`), jamais comme une compatibilité universelle. Fabriquer
  une compatibilité avec l'ensemble des ressources est au moins aussi
  grave que d'en inventer une seule.
- Les durées (`CompatibiliteRessourceTache.duree`) sont toujours en jours —
  convertis si la donnée source est dans une autre unité (minutes, heures...).
  Arrondis à l'entier le plus proche (jamais 0 pour une tâche dont la durée
  source est non nulle, arrondis alors à 1) et signale l'arrondi dans
  `avertissements`.
- N'ajoute aucun champ hors de ceux décrits ci-dessus (schéma strict).
- Pour toute autre information nécessaire absente ou ambiguë (hors
  compatibilité, couverte ci-dessus), fais ton meilleur effort mais note-le
  dans `avertissements` pour qu'un humain le vérifie — ton JSON est ensuite
  validé automatiquement (identifiants uniques, chaque tâche a bien une
  compatibilité...), mais cette validation ne peut pas détecter une erreur
  d'interprétation sémantique, seulement une incohérence structurelle.
- Pour chaque contrainte `precedence`, `echeance` et `competence_requise` que
  tu produis (pas `compatibilite_ressource_tache`, trop nombreuses pour être
  toutes justifiées individuellement), ajoute une entrée dans
  `justifications` citant le champ ou le passage précis des données brutes
  qui te l'a fait déduire — un humain doit pouvoir vérifier ta déduction sans
  relire tout le fichier source. Une justification vague ("déduit du
  contexte") ne remplit pas ce rôle : cite la valeur exacte lue.

## Rappel avant de répondre

Relis la RÈGLE ABSOLUE en tout début de ce document : aucun `poste_id`,
`code_poste`, `station_id` ou équivalent — un simple historique d'affectation
— ne doit produire de `compatibilite_ressource_tache`. Vérifie chaque
compatibilité que tu t'apprêtes à écrire : peux-tu citer une compétence,
qualification ou capacité technique explicite dans les données brutes qui la
justifie ? Si non, retire-la et signale-le dans `avertissements`, quitte à
laisser une tâche sans compatibilité.

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de
texte, pas de bloc markdown autour) :

```json
{{
  "instance": {{
    "taches": [{{"id": "...", "nom": "...", "priorite": 3}}],
    "ressources": [{{"id": "...", "nom": "...", "competences": ["..."]}}],
    "contraintes": [
      {{"type": "precedence", "avant": "...", "apres": "..."}},
      {{"type": "compatibilite_ressource_tache", "tache": "...", "ressource": "...", "duree": 2}},
      {{"type": "echeance", "tache": "...", "echeance": 5}},
      {{"type": "competence_requise", "tache": "...", "competence": "..."}}
    ],
    "objectifs": [{{"type": "minimiser_makespan"}}]
  }},
  "avertissements": ["ce qui a été ignoré, incertain, ou à vérifier — tableau vide si rien à signaler"],
  "justifications": [
    {{"contrainte": "precedence: T1 → T2", "raison": "champ \"operation_precedente\": \"T1\" sur l'opération T2"}},
    {{"contrainte": "echeance: T2 (5 jours)", "raison": "champ \"date_limite_minutes\": 7200 sur l'opération T2, converti en jours"}}
  ]
}}
```

`priorite`, `competences`, `echeance` et `competence_requise` sont **optionnels** —
n'en mets que si les données brutes les portent explicitement, jamais par supposition
(même règle "n'invente rien" que pour la compatibilité). `justifications` est un
tableau vide seulement si tu n'as produit aucune contrainte `precedence`,
`echeance` ou `competence_requise`.

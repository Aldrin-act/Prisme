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

- **La compatibilité ressource-tâche doit refléter la compétence réelle, pas
  seulement un historique.** Si les données distinguent une notion de
  compétence/qualification (d'un opérateur ou d'une équipe) d'un simple
  historique d'affectation à des tâches passées, base la compatibilité sur
  la compétence : une ressource historiquement affectée à une tâche sans
  posséder la qualification correspondante n'est pas forcément compatible,
  et une ressource qualifiée mais jamais affectée peut l'être. À défaut de
  toute notion de compétence explicite dans les données, l'historique
  d'affectation reste un signal acceptable, mais dis-le dans
  `avertissements` (c'est une approximation, pas une certitude). Si les
  données nomment explicitement une compétence requise par une tâche,
  exprime-la avec la contrainte `competence_requise` (et renseigne
  `ressources[].competences`) plutôt que de la garder implicite — le
  garde-fou automatique vérifie alors lui-même la cohérence entre
  compatibilité déclarée et compétence, sans que tu aies à le faire toi-même.
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
- Les durées (`CompatibiliteRessourceTache.duree`) sont toujours en minutes —
  convertis si la donnée source est dans une autre unité (heures, jours...).
- N'ajoute aucun champ hors de ceux décrits ci-dessus (schéma strict).
- Pour toute autre information nécessaire absente ou ambiguë (hors
  compatibilité, couverte ci-dessus), fais ton meilleur effort mais note-le
  dans `avertissements` pour qu'un humain le vérifie — ton JSON est ensuite
  validé automatiquement (identifiants uniques, chaque tâche a bien une
  compatibilité...), mais cette validation ne peut pas détecter une erreur
  d'interprétation sémantique, seulement une incohérence structurelle.

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
      {{"type": "compatibilite_ressource_tache", "tache": "...", "ressource": "...", "duree": 30}},
      {{"type": "echeance", "tache": "...", "echeance": 480}},
      {{"type": "competence_requise", "tache": "...", "competence": "..."}}
    ],
    "objectifs": [{{"type": "minimiser_makespan"}}]
  }},
  "avertissements": ["ce qui a été ignoré, incertain, ou à vérifier — tableau vide si rien à signaler"]
}}
```

`priorite`, `competences`, `echeance` et `competence_requise` sont **optionnels** —
n'en mets que si les données brutes les portent explicitement, jamais par supposition
(même règle "n'invente rien" que pour la compatibilité).

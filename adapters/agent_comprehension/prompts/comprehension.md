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

- **N'invente rien.** Si une tâche n'a manifestement aucune ressource
  compatible dans les données fournies, ne fabrique pas une compatibilité —
  omets-la et signale-le dans `avertissements` plutôt que de produire une
  donnée fausse mais plausible.
- Les durées (`CompatibiliteMachineTache.duree`) sont toujours en minutes —
  convertis si la donnée source est dans une autre unité (heures, jours...).
- N'ajoute aucun champ hors de ceux décrits ci-dessus (schéma strict).
- Si une information nécessaire est absente ou ambiguë, fais ton meilleur
  effort mais note-le dans `avertissements` pour qu'un humain le vérifie —
  ton JSON est ensuite validé automatiquement (identifiants uniques,
  chaque tâche a bien une compatibilité...), mais cette validation ne peut
  pas détecter une erreur d'interprétation sémantique, seulement une
  incohérence structurelle.

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de
texte, pas de bloc markdown autour) :

```json
{{
  "instance": {{
    "taches": [{{"id": "...", "nom": "..."}}],
    "ressources": [{{"id": "...", "nom": "..."}}],
    "contraintes": [
      {{"type": "precedence", "avant": "...", "apres": "..."}},
      {{"type": "compatibilite_machine_tache", "tache": "...", "ressource": "...", "duree": 30}}
    ],
    "objectifs": [{{"type": "minimiser_makespan"}}]
  }},
  "avertissements": ["ce qui a été ignoré, incertain, ou à vérifier — tableau vide si rien à signaler"]
}}
```

{mission}

## Plan technique suivi par le Développeur

{contexte_generation}

## Code du solveur (agent Développeur)

```python
{code}
```

## Tests générés par l'agent Testeur, exécutés en sandbox

```python
{tests}
```

## Échec constaté en sandbox

{probleme}

## Tentatives précédentes dans cette génération

{historique}

## Ton rôle : Agent Debugger — diagnostic à deux suspects

Si des tentatives précédentes sont listées ci-dessus, ne rejoue jamais un
correctif déjà tenté et déjà resté en échec — cherche une autre cause.

Contrairement à un échec de la cascade de validation (`validation_engine/cascade.py`,
toujours contre une vérité terrain déterministe — le solveur a alors toujours tort),
un échec de ces tests n'a pas de coupable évident : les tests eux-mêmes sont écrits
par un LLM et peuvent contenir une attente incorrecte, une durée mal calculée, un cas
mal posé — pas forcément un bug du solveur.

Détermine **lequel des deux est réellement fautif**, dans cet ordre :

1. **Le test est hors du périmètre du solveur ?** C'est alors le test qui a tort, corrige-le (ou
   retire ce test) et laisse le solveur inchangé. C'est le cas si le test :
   - utilise un type de contrainte ou d'objectif que le plan technique ne couvre pas (ex. une
     `Echeance` pour prouver l'infaisabilité alors que le solveur n'a pas eu d'échéance à gérer) ;
   - affirme un makespan optimal exact alors que l'algorithme imposé n'est pas `cp_sat` ;
   - construit une instance que `InstanceTRCO` refuse (`ValidationError` avant même l'appel à
     `resoudre()`) ;
   - calcule mal sa propre valeur attendue, ou suppose un format d'identifiant de tâche.
2. **Le solveur contredit la mission ou le plan ?** (contrainte violée, mauvaise borne, exception
   non gérée, `None` sur une instance faisable...) : corrige `resoudre()`, laisse les tests
   inchangés.
3. **Toujours dans le doute** : corrige le solveur — un solveur qui contredit sa mission est un
   défaut plus grave qu'un test trop exigeant, mais seulement une fois le point 1 écarté.

Ne corrige **jamais les deux à la fois** sauf certitude que les deux ont effectivement un défaut
distinct.

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de texte, pas de
bloc markdown autour). Renvoie systématiquement le module **complet** des deux côtés
(solveur et tests), même celui que tu n'as pas modifié :

```json
{{
  "cible": "solveur",
  "cause": "une phrase courte : la cause racine du problème, avant correction",
  "correctif": "une phrase courte : ce que tu as concrètement modifié",
  "code": "le module Python du solveur, corrigé ou inchangé, complet, sur une seule chaîne avec des \n pour les retours à la ligne",
  "tests": "le module de tests, corrigé ou inchangé, complet, sur une seule chaîne avec des \n pour les retours à la ligne"
}}
```

`cible` vaut exactement `"solveur"` ou `"tests"` — désigne lequel des deux modules
ci-dessus a réellement changé entre l'entrée et ta réponse.

Exemple de réponse valide (le test sortait du périmètre du solveur, le solveur était correct) :

```json
{{
  "cible": "tests",
  "cause": "le test ajoutait une Echeance pour prouver l'infaisabilité, alors que le plan technique ne couvre aucune échéance : le solveur l'ignore à juste titre",
  "correctif": "suppression du test d'infaisabilité par échéance, remplacé par un test de légalité sur deux chaînes convergentes",
  "code": "from __future__ import annotations\n\nfrom dsl.schema import InstanceTRCO, Planning\n\n\ndef resoudre(instance: InstanceTRCO, planning_precedent: Planning | None = None, horizon_gele_jours: int = 0) -> Planning | None:\n    ...\n",
  "tests": "from solveur_candidat import resoudre\n\n\ndef test_chaines_convergentes_legales():\n    ...\n"
}}
```

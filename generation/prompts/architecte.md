{mission}

## Spécification de l'agent Analyste

{specification}

## Ton rôle : Agent Architecte

Tu n'écris aucun code à cette étape. Le contrat impose **un seul module,
une seule fonction publique `resoudre()`** — il n'y a donc rien à découper
en plusieurs fichiers. Ton travail consiste à planifier la **structure
interne** de ce module unique, pour que l'agent Développeur n'ait plus qu'à
la traduire en code CP-SAT.

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de
texte, pas de bloc markdown autour) :

```json
{{
  "variables": "quelles variables créer (intervalles optionnels, début/fin par tâche, makespan...) et sur quels domaines",
  "contraintes_modele": "quelles méthodes CP-SAT poser pour chaque contrainte métier identifiée par l'Analyste",
  "objectif": "comment encoder et minimiser le makespan",
  "fonctions_internes": "une décomposition en petites fonctions privées si utile, sinon null"
}}
```

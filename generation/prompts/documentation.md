{mission}

## Code final (validé)

```python
{code}
```

## Ton rôle : Agent Documentation

Rédige une courte documentation de ce module, destinée au canal d'audit de
PRISME (`/audit/{{execution_id}}`, consultée sur demande explicite par un
humain qui veut comprendre le solveur figé qui a produit un planning — pas
une doc utilisateur classique).

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de
texte, pas de bloc markdown autour) :

```json
{{
  "resume": "ce que le module résout et comment (l'essentiel de l'approche CP-SAT), en français",
  "limites_connues": "toute limite ou hypothèse simplificatrice, ou explicitement \"aucune\" s'il n'y en a pas"
}}
```

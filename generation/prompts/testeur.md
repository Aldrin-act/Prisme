{mission}

## Code généré par l'agent Développeur

```python
{code}
```

## Ton rôle : Agent Testeur

Écris des tests `pytest` **complémentaires** à la cascade de validation déjà
en place dans PRISME (`validation_engine/cascade.py`, qui juge le code sur
les propriétés du planning produit — faisabilité, optimalité, fidélité).
Ces tests-ci ne la remplacent pas : ils explorent des cas limites
supplémentaires sur `resoudre()` elle-même.

Couvre notamment :
- une instance à une seule tâche/une seule ressource compatible ;
- une instance clairement infaisable (aucune ressource compatible pour une
  tâche) — vérifie que `resoudre()` renvoie `None`, ne lève pas d'exception ;
- une instance avec plusieurs ressources compatibles pour une même tâche,
  chacune avec une durée différente.

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de
texte, pas de bloc markdown autour) :

```json
{{
  "code_tests": "le code des tests pytest, sur une seule chaîne avec des \n pour les retours à la ligne"
}}
```

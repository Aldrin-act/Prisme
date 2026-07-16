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

Réponds avec un unique bloc de code Python (` ```python ... ``` `)
contenant les fonctions de test, sans texte avant ni après. Respecte les
mêmes règles d'imports que la mission (`dsl.schema`, `pytest`,
`ortools.sat.python.cp_model` si besoin de construire des instances).

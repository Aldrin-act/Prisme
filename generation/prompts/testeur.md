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

Ton module sera exécuté tel quel, dans un environnement où le code du
Développeur ci-dessus est disponible comme un module Python nommé
`solveur_candidat` — commence donc systématiquement ton module par
`from solveur_candidat import resoudre` (jamais un autre nom d'import :
`resoudre` n'est accessible que via ce module).

Couvre notamment :
- une instance à une seule tâche/une seule ressource compatible ;
- une instance clairement infaisable — **jamais** en omettant la compatibilité
  ressource-tâche d'une tâche, ni via une précédence qu'une tâche se donnerait
  à elle-même : `InstanceTRCO` (respectivement `Precedence`) l'interdit dès la
  **construction** de l'instance elle-même (`ValidationError` avant même
  d'appeler `resoudre()` — le test échouerait alors systématiquement, quelle
  que soit la qualité du solveur). Construis plutôt une instance valide mais
  impossible à honorer : une tâche dont l'unique ressource compatible a une
  `duree` supérieure à son `Echeance` (deadline) — vérifie que `resoudre()`
  renvoie `None`, ne lève pas d'exception ;
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

Exemple de réponse valide (structure attendue, pas les seuls tests à écrire) :

```json
{{
  "code_tests": "from dsl.schema import InstanceTRCO, Tache, Ressource, CompatibiliteRessourceTache, Echeance, MinimiserMakespan\nfrom solveur_candidat import resoudre\n\n\ndef test_instance_infaisable_renvoie_none():\n    # duree (10) > echeance (5) sur l'unique ressource compatible : instance valide,\n    # mais aucun planning ne peut respecter l'echeance.\n    instance = InstanceTRCO(\n        taches=[Tache(id='T1')],\n        ressources=[Ressource(id='R1')],\n        contraintes=[\n            CompatibiliteRessourceTache(tache='T1', ressource='R1', duree=10),\n            Echeance(tache='T1', echeance=5),\n        ],\n        objectifs=[MinimiserMakespan(poids=1)],\n    )\n    assert resoudre(instance) is None\n"
}}
```

{mission}

## Code à corriger

```python
{code}
```

## Problème constaté

{probleme}

## Tentatives précédentes dans cette génération

{historique}

## Ton rôle : Agent Debugger

Corrige le code ci-dessus pour résoudre précisément le problème constaté,
en respectant toujours le contrat et les contraintes de sécurité de la
mission. Ne réécris pas ce qui n'a pas besoin de changer.

Si des tentatives précédentes sont listées ci-dessus, ne rejoue jamais un
correctif déjà tenté et déjà resté en échec — un même symptôme après un
même correctif signale que la cause identifiée alors était fausse,
cherche-en une autre.

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de
texte, pas de bloc markdown autour) :

```json
{{
  "cause": "une phrase courte : la cause racine du problème, avant correction",
  "code": "le module Python corrigé, complet, sur une seule chaîne avec des \n pour les retours à la ligne"
}}
```

Exemple de réponse valide :

```json
{{
  "cause": "la contrainte de précédence utilisait AddNoOverlap au lieu de Add(fin_a <= debut_b), donc l'ordre entre tâches liées n'était jamais imposé",
  "code": "from __future__ import annotations\n\nfrom ortools.sat.python import cp_model\n\nfrom dsl.schema import InstanceTRCO, Planning\n\n\ndef resoudre(instance: InstanceTRCO, planning_precedent: Planning | None = None, horizon_gele_jours: int = 0) -> Planning | None:\n    ...\n"
}}
```

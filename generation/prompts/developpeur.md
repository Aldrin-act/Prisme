{mission}

## Plan technique de l'agent Architecte

Voici le plan que tu dois suivre pour écrire le module — respecte ses choix
de variables et de contraintes, sauf s'il viole une des règles de sécurité
ci-dessus (auquel cas les règles de sécurité priment) :

{plan_technique}

## Documentation de référence consultée

{documentation}

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de
texte, pas de bloc markdown autour) :

```json
{{
  "code": "le module Python complet, sur une seule chaîne avec des \n pour les retours à la ligne"
}}
```

Exemple de réponse valide (structure du champ `code`, pas un solveur complet) :

```json
{{
  "code": "from __future__ import annotations\n\nimport random\n\nfrom dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, OperationPlanifiee, Planning, Precedence\n\n\ndef _preprocess(instance: InstanceTRCO) -> dict:\n    # tables précalculées UNE fois : durées, compatibilités, précédences...\n    ...\n\n\ndef _decoder(ordre: list[str], tables: dict) -> Planning:\n    # décodeur constructif : légal par construction, jamais de pénalité\n    ...\n\n\ndef resoudre(instance: InstanceTRCO, planning_precedent: Planning | None = None, horizon_gele_jours: int = 0) -> Planning | None:\n    tables = _preprocess(instance)\n    rng = random.Random(42)  # générateur local, graine fixe\n    # ... recherche à nombre d'itérations fixe selon le plan technique (gel d'horizon si horizon_gele_jours > 0) ...\n    return Planning(operations=[])\n"
}}
```

{mission}

## Plan technique de l'agent Architecte

Voici le plan que tu dois suivre pour écrire le module — respecte ses choix
de variables et de contraintes, sauf s'il viole une des règles de sécurité
ci-dessus (auquel cas les règles de sécurité priment) :

{plan_technique}

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
  "code": "from __future__ import annotations\n\nfrom ortools.sat.python import cp_model\n\nfrom dsl.schema import InstanceTRCO, Planning, OperationPlanifiee\n\n\ndef resoudre(instance: InstanceTRCO, planning_precedent: Planning | None = None, horizon_gele_jours: int = 0) -> Planning | None:\n    modele = cp_model.CpModel()\n    # ... variables, contraintes (dont le gel d'horizon si horizon_gele_jours > 0), objectif selon le plan technique ci-dessus ...\n    solveur = cp_model.CpSolver()\n    statut = solveur.Solve(modele)\n    if statut not in (cp_model.OPTIMAL, cp_model.FEASIBLE):\n        return None\n    return Planning(operations=[])\n"
}}
```

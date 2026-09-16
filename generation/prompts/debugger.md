{mission}

## Plan technique suivi par le Développeur

{contexte_generation}

## Code à corriger

```python
{code}
```

## Problème constaté

{probleme}

## Tentatives précédentes dans cette génération

{historique}

## Ton rôle : Agent Debugger

Corrige le code ci-dessus pour résoudre précisément le problème constaté, en respectant toujours
le contrat, le plan technique, l'algorithme imposé et les contraintes de sécurité de la mission.
Ne réécris pas ce qui n'a pas besoin de changer.

Ce problème vient d'une validation contre une vérité terrain déterministe (banc à optimum connu,
vérificateur de faisabilité, cas de référence) : c'est toujours le solveur qui a tort.

Avant de chercher ailleurs, vérifie d'abord les pièges connus de la mission, qui expliquent la
plupart des échecs :

- `None` renvoyé sur une instance faisable : `horizon` trop court (section « Horizon »), réservoir
  de matières sans événement initial `+stock_initial` à l'instant 0 (section « Matières »),
  échéance encodée sur le début au lieu de la fin ;
- délai dépassé ou planning absent sur une grande instance : recherche répétée dans
  `instance.contraintes` à l'intérieur d'une boucle (section « Précalcule tout »), trop
  d'itérations pour 30 s sur 1 vCPU, `max_time_in_seconds` au lieu de `max_deterministic_time` ;
- résultat différent d'un appel à l'autre : hasard global, plusieurs workers CP-SAT, arrêt au
  temps réel ;
- `KeyError`/mauvais accès : clés de `debut`/`presence` mélangées (section « Noms des variables
  CP-SAT »), identifiant supposé d'un format particulier (les commandes génèrent des ids comme
  `cmd-1a2b3c4d_0_DECOUPE`).

Si des tentatives précédentes sont listées ci-dessus, ne rejoue jamais un correctif déjà tenté et
déjà resté en échec — un même symptôme après un même correctif signale que la cause identifiée
alors était fausse, cherche-en une autre.

## Format de réponse exigé

Réponds avec un unique objet JSON, rien d'autre avant ni après (pas de
texte, pas de bloc markdown autour) :

```json
{{
  "cause": "une phrase courte : la cause racine du problème, avant correction",
  "correctif": "une phrase courte : ce que tu as concrètement modifié dans le code",
  "code": "le module Python corrigé, complet, sur une seule chaîne avec des \n pour les retours à la ligne"
}}
```

Exemple de réponse valide :

```json
{{
  "cause": "le réservoir de matières démarrait au niveau 0 : la première consommation le rendait négatif, le modèle était toujours infaisable",
  "correctif": "ajout d'un événement +stock_initial à l'instant 0 en tête de la liste passée à AddReservoirConstraint",
  "code": "from __future__ import annotations\n\nfrom ortools.sat.python import cp_model\n\nfrom dsl.schema import InstanceTRCO, Planning\n\n\ndef resoudre(instance: InstanceTRCO, planning_precedent: Planning | None = None, horizon_gele_jours: int = 0) -> Planning | None:\n    ...\n"
}}
```

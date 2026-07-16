# Prompt de génération — solveur CP-SAT pour le noyau minimal T-R-C-O

Tu es un générateur de code. Écris un module Python unique qui résout le
Flexible Job-Shop Scheduling Problem (FJSP) pour le noyau minimal du DSL
T-R-C-O de PRISME : précédence, compatibilité machine-tâche, durées,
minimisation du makespan.

## Contrat exigé

Le module doit définir exactement une fonction :

```python
def resoudre(instance: InstanceTRCO) -> Planning | None:
    ...
```

- `InstanceTRCO`, `Planning`, `OperationPlanifiee`, `Tache`, `Ressource`,
  `Contrainte`, `Precedence`, `CompatibiliteMachineTache` s'importent depuis
  `dsl.schema`.
- `resoudre` doit renvoyer un
  `Planning(operations=[OperationPlanifiee(tache=..., ressource=..., debut=...), ...])`
  légal et de makespan minimal, ou `None` si l'instance est infaisable.
- Utilise `ortools.sat.python.cp_model` (CP-SAT) pour résoudre réellement le
  problème — pas d'heuristique gloutonne approximative.

## Contraintes de sécurité (impératives — le code est exécuté automatiquement)

- Imports autorisés, et seulement ceux-là : `ortools.sat.python.cp_model`,
  `dsl.schema`, `collections`, `collections.abc`, `dataclasses`, `typing`,
  `__future__`.
- Interdit, sans exception : `eval`, `exec`, `compile`, `__import__`,
  `open`, `input`, tout accès réseau ou fichier, tout import hors de la
  liste ci-dessus (notamment `os`, `sys`, `subprocess`, `socket`, `shutil`,
  `importlib`).

Ceci est le contrat commun ; le format de réponse exact (bloc de code,
JSON...) est précisé séparément selon qui te le demande.

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
- `InstanceTRCO.taches` : liste de `Tache(id: str, nom: str | None, duree: int)`.
- `InstanceTRCO.ressources` : liste de `Ressource(id: str, nom: str | None)`.
- `InstanceTRCO.contraintes` : liste de `Precedence(avant: str, apres: str)`
  et/ou `CompatibiliteMachineTache(tache: str, ressource: str)`, chacune
  discriminée par son champ `type` (`"precedence"` ou
  `"compatibilite_machine_tache"`).
- `InstanceTRCO.objectifs` : toujours `[MinimiserMakespan()]` pour l'instant.
- **Règle de compatibilité, impérative** : une tâche **sans aucune**
  contrainte `CompatibiliteMachineTache` déclarée n'est **pas restreinte** —
  elle peut être affectée à n'importe quelle ressource déclarée dans
  l'instance. Une tâche avec au moins une telle contrainte ne peut être
  affectée qu'aux ressources qu'elle liste.
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

## Format de réponse

Réponds avec un unique bloc de code Python (` ```python ... ``` `), sans
texte avant ni après. Aucune explication, aucun commentaire de conversation.

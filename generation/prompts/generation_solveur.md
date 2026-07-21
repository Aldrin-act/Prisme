# Prompt de génération — solveur FJSP pour le noyau minimal T-R-C-O

Tu es un générateur de code. Écris un module Python unique qui résout le
Flexible Job-Shop Scheduling Problem (FJSP) pour le noyau minimal du DSL
T-R-C-O de PRISME : précédence, compatibilité ressource-tâche, durées,
minimisation du makespan.

## Contrat exigé

Le module doit définir exactement une fonction :

```python
def resoudre(instance: InstanceTRCO) -> Planning | None:
    ...
```

- `InstanceTRCO`, `Planning`, `OperationPlanifiee`, `Tache`, `Ressource`,
  `Contrainte`, `Precedence`, `CompatibiliteRessourceTache`, `Echeance`,
  `CompetenceRequise` s'importent depuis `dsl.schema`.
- `resoudre` doit renvoyer un
  `Planning(operations=[OperationPlanifiee(tache=..., ressource=..., debut=...), ...])`
  légal et de makespan minimal, ou `None` si l'instance est infaisable.
- L'algorithme à utiliser est celui recommandé par l'agent Benchmarker en
  amont dans le pipeline (voir le plan technique de l'agent Architecte
  ci-joint) : `ortools.sat.python.cp_model` (CP-SAT) par défaut, ou un
  algorithme alternatif (génétique, ACO, recuit simulé, tabou, glouton +
  recherche locale, règles de dispatching) pour les instances où CP-SAT ne
  passe pas à l'échelle. N'utilise jamais un autre algorithme que celui
  indiqué dans le plan technique. Quel que soit l'algorithme, le contrat de
  sortie ne change pas : `resoudre` renvoie un planning légal et de
  makespan minimal (ou le meilleur trouvé si l'algorithme est approché), ou
  `None` si l'instance est infaisable.
- **Déterminisme obligatoire** (§6.5) : `resoudre` doit renvoyer le même
  makespan à chaque appel sur la même instance. Si l'algorithme utilise du
  hasard (génétique, ACO, recuit simulé), instancie un générateur local avec
  une graine fixe (`random.Random(<graine>)`), jamais l'état global du
  module `random`. Borne les itérations par un nombre fixe (générations,
  itérations...), jamais par une limite de temps écoulé — non reproductible
  d'une machine à l'autre, et de toute façon appliquée par le bac à sable
  d'exécution (Étape 7, limites CPU/mémoire, kill au dépassement).
- **Contraintes dures = construction, jamais pénalité** : que l'algorithme
  soit CP-SAT ou un algorithme alternatif, une contrainte dure (précédence,
  compatibilité ressource-tâche, non-chevauchement d'une ressource) doit
  être **impossible à violer par construction** du planning — jamais un
  terme de pénalité dans une fonction de fitness/coût qu'un individu
  pourrait quand même faire gagner malgré la violation. Pour un algorithme
  non-CP-SAT, cela veut dire un décodeur qui construit le planning en
  respectant ces règles au moment même où il place chaque tâche (voir le
  plan technique de l'agent Architecte pour le schéma exact) — la recherche
  (génétique, ACO, recuit...) n'optimise alors que le makespan du planning
  déjà légal, jamais un score composite mêlant faisabilité et qualité.
- `Echeance`/`CompetenceRequise` sont des extensions optionnelles du noyau
  minimal (absentes de la plupart des instances) : si l'instance contient des
  `Echeance`, encode-les en contrainte dure sur la fin de la tâche concernée
  (`modele.Add(fin <= echeance)`) — sinon ignore-les, elles n'existent pas.
  `CompetenceRequise` ne demande aucun traitement côté solveur :
  `InstanceTRCO` garantit déjà, avant que `resoudre` ne soit appelé, que
  toute `CompatibiliteRessourceTache` respecte les compétences requises —
  `CompatibiliteRessourceTache` reste la seule source de compatibilité et de
  durée à utiliser.

## Accès aux données de l'instance (noms de champs exacts — ne pas en deviner d'autres)

`InstanceTRCO` n'a que **quatre** champs : `taches`, `ressources`,
`contraintes`, `objectifs`. Il n'existe **aucun** raccourci du type
`instance.precedences` ou `instance.compatibilite_ressource_tache` —
`contraintes` est une **liste polymorphe unique** (`Precedence |
CompatibiliteRessourceTache | Echeance | CompetenceRequise`), à filtrer par
type avec `isinstance` :

```python
compatibilites = [c for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
precedences = [c for c in instance.contraintes if isinstance(c, Precedence)]
echeances = [c for c in instance.contraintes if isinstance(c, Echeance)]
```

Champs exacts de chaque type — vérifie-les avant d'écrire du code qui y
accède, ne les devine jamais par analogie avec un autre projet :

- `Precedence.avant`, `Precedence.apres` (pas `tache_amont`/`tache_aval`) :
  la tâche `avant` doit être terminée avant que `apres` ne commence.
- `CompatibiliteRessourceTache.tache`, `.ressource`, `.duree`.
- `Echeance.tache`, `.echeance` (pas `date_limite`) : instant limite de fin
  de la tâche, en minutes.
- `Tache.id`, `Ressource.id` (type `Identifiant`, une chaîne) sont les
  **seuls** identifiants stables à utiliser partout où une tâche/ressource
  doit être référencée : clé de dictionnaire, gène de chromosome,
  `OperationPlanifiee.tache`/`.ressource`. `Tache.nom`/`Ressource.nom`
  sont **optionnels** (`str | None`, souvent absents) et pas garantis
  uniques — ne jamais les utiliser comme identifiant, seulement pour de
  l'affichage.

## Contraintes de sécurité (impératives — le code est exécuté automatiquement)

- Imports autorisés, et seulement ceux-là : `ortools.sat.python.cp_model`,
  `dsl.schema`, `collections`, `collections.abc`, `dataclasses`, `typing`,
  `__future__`, `random`, `math` (les deux derniers seulement utiles pour un
  algorithme non-CP-SAT — génération/mutation, recuit...).
- Interdit, sans exception : `eval`, `exec`, `compile`, `__import__`,
  `open`, `input`, tout accès réseau ou fichier, tout import hors de la
  liste ci-dessus (notamment `os`, `sys`, `subprocess`, `socket`, `shutil`,
  `importlib`).

Ceci est le contrat commun ; le format de réponse exact (bloc de code,
JSON...) est précisé séparément selon qui te le demande.

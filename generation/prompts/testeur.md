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

## Ce que ce solveur sait traiter

- Algorithme utilisé : **{algorithme}**
- Types de contraintes de l'instance pour laquelle il a été généré : {types_contraintes}
- Types d'objectifs : {types_objectifs}

Le solveur n'a été conçu que pour ces types-là. **Dans tes instances de test, n'utilise que ces
types de contraintes et d'objectifs** (plus `compatibilite_ressource_tache`, toujours obligatoire)
— un test qui ajoute un type absent de cette liste (une `Echeance` alors qu'il n'y en a pas, une
`ContrainteCapacite`...) teste un comportement que personne n'a demandé et échouera sur un solveur
correct.

Le solveur est une heuristique, donc **approché** : n'affirme jamais un makespan
optimal exact, sauf sur une instance si petite que l'optimum est évident (une tâche, ou une chaîne
de tâches sur des ressources dédiées). Vérifie plutôt la légalité du planning.

## Cas à couvrir

- une instance à une seule tâche/une seule ressource compatible ;
- une instance avec plusieurs ressources compatibles pour une même tâche, chacune avec une durée
  différente — vérifie que la ressource choisie est bien compatible et que le planning est légal ;
- une instance **qui ressemble à ce que produisent les commandes clientes** : identifiants générés
  (ex. `cmd-1a2b3c4d_0_DECOUPE`, `cmd-9f8e7d6c_1_ASSEMBLAGE`), deux chaînes de tâches qui
  convergent vers une même tâche (une tâche avec **deux** `Precedence` en entrée), plus une tâche
  isolée sans précédence — vérifie que chaque tâche apparaît exactement une fois et que toutes les
  précédences sont respectées ;
- **seulement si `echeance` figure dans les types ci-dessus** : une instance valide mais
  impossible à honorer — une tâche dont l'unique ressource compatible a une `duree` supérieure à
  son `Echeance` — et vérifie que `resoudre()` renvoie `None` sans lever d'exception. Sans
  `echeance` dans la liste, n'écris **aucun** test d'infaisabilité.

Pour construire une instance, n'essaie jamais d'omettre la compatibilité d'une tâche ni de créer
une précédence d'une tâche vers elle-même : `InstanceTRCO`/`Precedence` le refusent dès la
construction (`ValidationError` avant même d'appeler `resoudre()`), le test échouerait quelle que
soit la qualité du solveur.

Pour vérifier la légalité, écris toi-même, dans le module de tests, les vérifications utiles :
chaque tâche planifiée une fois, sur une ressource compatible ; `debut + duree` d'une tâche ≤
`debut` de la suivante pour chaque précédence ; aucun chevauchement sur une ressource (capacité 1
sauf `ContrainteCapacite`). N'importe **que** `dsl.schema`, `pytest` et `solveur_candidat`.

## Outil disponible (facultatif)

Si l'outil `consulter_cas_limites_banc_synthetique` t'est proposé, tu peux
l'appeler pour obtenir des cas d'instance T-R-C-O à makespan optimal **connu
par construction** — utile pour écrire un test qui vérifie une vraie valeur
attendue plutôt qu'un seuil ou un scénario inventé. Reste un complément,
jamais une obligation : les cas déjà listés ci-dessus restent la base
attendue de tes tests.

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

# Règles de dispatching (priorité)

Une seule passe, sans population ni itération : à chaque instant où une ressource se libère (ou au
début), choisir parmi les tâches disponibles (précédences déjà satisfaites, ressource compatible)
celle qui maximise une règle de priorité, la placer, puis recommencer. Le plus rapide de tous les
algorithmes de ce catalogue — pas de recherche, une seule construction déterministe.

## Règles de priorité usuelles

- **SPT (Shortest Processing Time)** : privilégier la tâche de plus courte durée sur la ressource
  candidate — minimise en général le nombre moyen de tâches en attente, pas nécessairement le
  makespan global.
- **LPT (Longest Processing Time)** : privilégier la tâche la plus longue — tend à mieux équilibrer
  la charge de fin de planning sur les ressources, utile si l'objectif inclut `EquilibrerCharge`.
- **EDD (Earliest Due Date)** : privilégier la tâche à l'échéance la plus proche (`Echeance`) —
  pertinent si `instance.objectifs` contient `MinimiserRetards`.
- **Ratio critique** : `(echeance - instant_courant) / duree_restante_estimee` — plus le ratio est
  bas, plus la tâche est urgente ; combine échéance et durée, utile en présence des deux signaux.

## Choix de la ressource

Une fois la tâche choisie, sélectionner parmi ses ressources compatibles celle qui permet le
démarrage le plus tôt (compte tenu de la disponibilité de chacune) — même logique que le décodeur
constructif générique décrit par l'Architecte.

## Quand combiner plusieurs règles

Si `instance.objectifs` combine plusieurs critères (ex. makespan et retards), une règle composite
(somme pondérée normalisée des scores de chaque règle candidate) reste préférable à un choix figé
sur une seule règle — mais le poids relatif doit refléter les poids déclarés sur les objectifs,
jamais une valeur arbitraire ignorant `instance.objectifs`.

## Déterminisme

Aucun aléa nécessaire dans le cas général (choix toujours par comparaison stricte des scores) — en
cas d'égalité stricte entre plusieurs candidats, départager par l'identifiant de tâche (ordre
lexicographique), jamais par un tirage aléatoire, pour rester reproductible sans même avoir besoin
d'une graine.

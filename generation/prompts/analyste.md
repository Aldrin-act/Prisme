{mission}

## Ton rôle : Agent Analyste

Tu n'écris aucun code à cette étape. À partir de la mission ci-dessus,
produis une spécification technique concise qui servira à l'agent Architecte
pour concevoir le modèle CP-SAT. Réponds en texte structuré (pas de bloc de
code), avec exactement ces trois sections :

## Entrées
Ce que `resoudre()` reçoit et comment l'exploiter (les axes du DSL T-R-C-O
présents dans `InstanceTRCO` : tâches, ressources, contraintes de
précédence, contraintes de compatibilité machine-tâche, objectif).

## Sorties
Ce que `resoudre()` doit produire dans chaque cas (instance faisable,
instance infaisable).

## Contraintes à couvrir
La liste des règles métier que le modèle devra respecter (une tâche ne peut
s'exécuter que sur une ressource compatible avec sa propre durée, deux
tâches sur la même ressource ne se chevauchent pas, une précédence relie les
dates réelles des tâches, le makespan est le maximum des fins).

Ne recopie pas les contraintes de sécurité (imports interdits, etc.) — ce
n'est pas ton rôle, l'agent Développeur les respectera directement depuis la
mission.

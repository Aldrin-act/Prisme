### 7.6.3 La page de supervision

Une page dédiée restitue les signaux détectés sur le fonctionnement du système. La détection
repose sur trois détecteurs déterministes, purs et sans appel LLM (`supervision/detecteurs.py`),
portant chacun sur un signal opérationnel distinct du pipeline. Une signature de solveur devenue
orpheline signale qu'aucun solveur actif ne correspond plus à la structure de contraintes ou
d'objectifs déclarée par l'instance — le cas qui échoue aujourd'hui en synchrone avec une erreur
lors d'une exécution, ici tracé plutôt que perdu. Une instance nécessitant une replanification
distingue deux situations : elle n'a jamais été exécutée, ou elle l'a été puis modifiée depuis sans
nouvelle exécution — le planning disponible ne reflète alors plus son contenu réel, alors qu'un
solveur compatible existe déjà. Une série d'échecs répétés signale que les trois dernières
exécutions d'une même instance ont toutes échoué.

Un agent complète ce dispositif en reprenant exactement le principe déjà retenu pour le
Benchmarker : le code Python détecte, le modèle de langage priorise et rédige en langage naturel,
jamais l'inverse — l'agent ne détecte rien par lui-même. Un seul appel couvre l'ensemble des
signaux nouvellement détectés pour un client, jamais un appel par signal ; et un signal déjà
couvert par une proposition en attente n'est pas soumis une seconde fois, pour ne pas accumuler de
doublons à chaque passe. Si le modèle ignore ou déforme la référence d'un signal, celui-ci n'est
pas perdu pour autant : un résumé de repli, écrit à l'avance pour chaque type de signal, prend le
relais plutôt que de laisser disparaître silencieusement un fait pourtant bien détecté. L'analyse
peut être déclenchée manuellement, ou tourner en arrière-plan toutes les heures ; cette boucle
périodique reste désactivée par défaut, et ne s'active que sur une variable d'environnement
explicite, pour ne jamais se déclencher sans qu'on l'ait demandé pendant un développement ou une
suite de tests.

Deux précisions s'imposent sur ce que fait exactement cette page, car c'est un point où un système
de ce type est facilement surévalué. La proposition d'action n'est jamais appliquée
automatiquement : elle est soumise à l'utilisateur, conformément au principe posé à la note de
cadrage selon lequel le système assiste la décision sans s'y substituer. Concrètement, chaque
proposition n'attend que deux issues, acceptée ou refusée ; et c'est l'acceptation elle-même qui
déclenche l'action correspondante — régénérer le solveur, l'exécuter, ou diagnostiquer un échec —
en réutilisant telle quelle la route de production existante, jamais une exécution parallèle ou
simplifiée. Le clic est la décision humaine explicite qui autorise l'action, pas un simple accusé
de réception. Et la détection porte sur des signaux du pipeline, non sur une dérive du planning en
temps réel : le système constate qu'un solveur ne correspond plus à son contexte ou qu'une
instance demande à être replanifiée, il ne mesure pas l'écart entre un planning et son exécution
réelle sur le terrain. Cette seconde capacité supposerait plusieurs cycles de production
documentés, ressource que le calendrier n'a pas permis de constituer.

[ CAPTURE À INSÉRER — page de supervision — signaux détectés et actions proposées ]

Figure 17 : Page de supervision — signaux détectés par les détecteurs déterministes et
propositions soumises à validation

Cette reformulation par rapport au plan directeur, qui prévoyait une détection de dérive de
planning, est analysée au chapitre VI. Elle constitue un changement de nature de la fonction et
non son abandon : ce qui est livré détecte et propose, mais sur des signaux internes au système
plutôt que sur des écarts observés en atelier.

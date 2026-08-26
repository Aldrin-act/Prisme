# 7.1.2 Le modèle pivot comme point de généricité

> Section fournie telle quelle (les deux premiers paragraphes reprennent le texte déjà rédigé,
> inchangé) — seul le paragraphe « À COMPLÉTER » a été remplacé, volontairement sans aucun
> chiffre : la volumétrie est traitée ici de façon qualitative (invariance du vocabulaire à travers
> l'échelle), les chiffres précis (bornes exactes, résultats de benchmark) restant réservés au
> chapitre qui leur est dédié, pour ne pas les dupliquer ni les sortir de leur contexte
> méthodologique.

Le modèle pivot décrit une organisation selon quatre axes — tâches, ressources, contraintes,
objectifs — sans aucun terme emprunté à un secteur particulier. Il remplit simultanément trois
fonctions : il constitue le contrat entre le métier et la machine, puisque c'est dans ce
vocabulaire que les règles sont déclarées ; il est l'unique entrée de la chaîne de génération ; et
il fournit le cadre de référence contre lequel le code produit est validé. Sa formalisation repose
sur des schémas typés, ce qui permet de rejeter une description incohérente avant toute
génération.

Une précision s'impose sur le statut de cette propriété, car elle est la plus facile à
surinterpréter. La neutralité sectorielle du modèle pivot est une propriété de conception,
vérifiée par la capacité à décrire neuf configurations sectorielles sans étendre le vocabulaire.
Elle n'est pas un résultat de validation hors industrie : aucune de ces configurations n'a fait
l'objet d'un déploiement ni d'une confrontation à des praticiens du secteur concerné. Ce qui est
établi est qu'un bloc opératoire ou une équipe de développement se décrivent dans ce modèle ; ce
qui ne l'est pas est que les plannings produits y seraient jugés pertinents.

Sur le plan de la volumétrie — ce que le modèle pivot, et le pipeline qui l'exploite, permettent
effectivement de gérer —, la propriété à retenir n'est pas une borne chiffrée mais une invariance :
le même vocabulaire, celui des quatre axes déjà décrits, sert aussi bien à décrire l'instance la
plus minimale — construite pour prouver une propriété par construction plutôt que pour représenter
un cas réel — qu'une instance de grande échelle, simulée à partir de caractéristiques proches d'un
système industriel réel. Aucun type d'entité, de contrainte ou d'objectif n'a jamais eu besoin
d'être ajouté, retiré ou modifié pour franchir ce changement d'échelle.

Ce passage à l'échelle a par ailleurs une conséquence sur le choix algorithmique, distincte de la
question du vocabulaire : au-delà d'un certain volume, l'agent Benchmarker écarte de lui-même
CP-SAT — dont le temps de résolution cesse d'être praticable — au profit d'un algorithme approché,
dont le code est généré et qualifié par la cascade de validation exactement comme n'importe quel
autre solveur, avant d'être exécuté sur l'instance réelle. Cette exécution a produit un planning
complet, avec un taux d'utilisation des ressources élevé, en un temps de résolution sensiblement
supérieur à ce que le Benchmarker avait lui-même anticipé a priori pour un algorithme de ce type —
un écart qui s'explique vraisemblablement par un code généré par l'IA, non optimisé à la main.
Cette exécution reste néanmoins un calcul CPU classique, sans ressource de calcul dédiée (§
ressources mobilisées) ; les valeurs précises de cette expérience relèvent du chapitre consacré
aux benchmarks, pas de la présente discussion sur la généricité du modèle.

Les configurations sectorielles décrites plus haut répondent à une question différente — la
diversité des domaines descriptibles, pas le passage à l'échelle — et restent, à dessein, de
taille modeste : leur rôle est de montrer que le même vocabulaire fini couvre des secteurs très
différents, pas de tester la limite haute de ce que le système peut traiter, déjà établie
autrement ci-dessus.

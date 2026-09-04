### L'agent de compréhension

L'agent de compréhension traduit une donnée brute d'origine quelconque — fichier tabulaire,
export JSON, texte libre — vers une instance candidate du modèle pivot. Il ne se limite pas à
produire cette instance : il rédige aussi une description du processus métier telle qu'elle
ressort des données fournies, jamais un contexte qu'il aurait supposé au-delà de ce qui est écrit,
et il liste explicitement ses incertitudes pour qu'un humain les vérifie avant de faire confiance
au résultat. Chaque contrainte de précédence, d'échéance ou de compétence qu'il produit — mais pas
les compatibilités tâche-ressource, trop nombreuses pour que l'exercice reste lisible — est
accompagnée d'une citation exacte du champ des données brutes qui l'a justifiée : un humain peut
ainsi vérifier une déduction précise sans relire tout le fichier source.

Une faute d'orthographe du modèle sur le type d'une contrainte ou d'un objectif est corrigée
automatiquement, par comparaison avec la liste réelle des types valides du modèle pivot — cette
liste n'est jamais recopiée à la main dans l'agent, elle est extraite du modèle lui-même, pour ne
jamais se désynchroniser si un type est ajouté ou retiré par la suite. La correction ne s'applique
que si la valeur fournie est manifestement une faute de frappe proche d'un type existant, jamais
une réinterprétation sémantique : une valeur trop éloignée de tout type connu est laissée telle
quelle, et c'est alors la validation déterministe en aval qui tranche. Chaque correction effectuée
est elle-même consignée dans les avertissements, pour rester traçable.

Un sous-agent complète ce dispositif pour le cas où la donnée métier n'est pas déjà disponible
sous une forme exploitable, mais dort dans une base de données quelconque : il comprend lui-même
le schéma et les relations de cette base, décide des requêtes à exécuter, les exécute sur une
connexion strictement en lecture seule, et convertit le résultat en donnée brute directement
réutilisable par l'agent de compréhension. C'est la seule exception assumée au principe du
stage voulant qu'une décision à conséquence reste soumise à validation humaine : une simple
lecture n'en est pas une, et l'exécution y reste autonome. La garantie ne repose pas sur un
filtre applicatif des requêtes, volontairement traité comme un premier rempart faible : elle
repose surtout sur un rôle de base de données dédié, restreint à la lecture, et sur des limites
imposées à la connexion elle-même — la même logique de défense en profondeur que celle retenue pour
l'exécution du code généré.

Un choix technique mérite d'être noté pour sa justification empirique plutôt que théorique : cet
agent est le seul du dispositif à s'appuyer sur un mode de sortie structurée plus permissif que
celui utilisé ailleurs. Un test réel a montré que le mode le plus strict renvoyait systématiquement
une instance vide pour ce schéma précis — l'instance candidate étant volontairement laissée libre
plutôt que contrainte à une forme fixe, une contrainte de sortie trop stricte semble s'y réduire à
l'objet minimal valide plutôt que de la remplir. Le mode retenu ici n'a pas ce défaut, vérifié par
l'usage.

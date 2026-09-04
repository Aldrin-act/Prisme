### L'adaptateur d'entrée

Un adaptateur d'entrée traduit une représentation particulière, propre à un système
d'information client, vers le modèle pivot T-R-C-O — le seul format que le reste de la chaîne
(estimation, génération, exécution) sait lire. Deux formats sont pris en charge par un adaptateur
écrit à la main, dédié et déterministe : les exports tabulaires, et les échanges structurés issus
d'un progiciel de gestion au format JSON (couvrant aussi bien une preuve de concept générique
qu'un ERP client réel). Un agent de compréhension complète ce dispositif pour toute source qui ne
correspond à aucun des deux : il établit la correspondance entre les colonnes ou les champs d'une
source inconnue (fichier tabulaire, export JSON, texte libre) et les axes du modèle pivot, tâche
pour laquelle un modèle de langage est mieux placé qu'une règle codée. Sa sortie n'est jamais
injectée directement : elle traverse exactement la même validation que produirait un adaptateur
écrit à la main, et porte des avertissements explicites sur tout ce dont l'agent n'est pas certain
— une erreur d'interprétation sémantique, contrairement à une incohérence structurelle, n'est pas
détectable par cette validation, d'où l'exigence d'une relecture humaine avant de faire confiance
au planning qui en résultera.

**BPMN n'est pas un format pris en charge.** Le plan directeur envisageait un agent de
compréhension parsant une modélisation BPMN 2.0 du processus pilote. Aucun parseur BPMN n'a été
construit : la vérification est exhaustive et ne retourne aucun résultat. Ce n'est pas un manque
partiel à quantifier construction par construction — c'est une voie d'entrée non implémentée,
remplacée par l'agent de compréhension générique décrit ci-dessus, qui couvre le même besoin
(interpréter une source non structurée) sans dépendre d'un format de modélisation particulier. Le
tableau détaillant une couverture BPMN par famille de construction (tâches, flux de séquence,
passerelles, couloirs...) doit être retiré du rapport plutôt que complété : aucune des lignes
« Supporté » n'est vérifiable dans le code, et renseigner un taux de couverture reviendrait à
mesurer une fonctionnalité qui n'existe pas.

**État du module d'estimation de charge**, pour répondre à la seconde question : il est
**opérationnel, sous réserve d'une dépendance optionnelle**. Un modèle de régression entraîné sur
des données synthétiques, faute d'historique réel, n'est chargé qu'à la demande : si la dépendance
associée est installée, les adaptateurs l'invoquent automatiquement pour compléter une durée
manquante, avec un avertissement explicite dans la réponse pour toute valeur ainsi devinée ; si
elle ne l'est pas, l'import continue de fonctionner normalement, simplement sans complétion
automatique — une dégradation explicite, jamais un plantage. Une réserve distincte porte sur le
périmètre : ce module ne prédit qu'une durée unitaire par couple (tâche, ressource) ; il ne calcule
pas la charge prévisionnelle par ressource sur l'horizon de planification que le plan directeur
demandait également — ce second volet n'a jamais été tenté, indépendamment de la question de la
dépendance installée ou non.

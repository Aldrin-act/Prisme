# Chapitre 1 — Contexte général du projet

**PRISME — Plateforme de génération et d'exécution de solveurs d'ordonnancement pilotée par IA**
Projet de Fin d'Études — EIGSI Casablanca × BARAA Consult

---

## 1.1 Introduction

Ce chapitre pose le cadre général du projet PRISME avant d'entrer, dans les chapitres suivants,
dans le détail de la conception et de la réalisation. Il présente successivement l'organisme
d'accueil, le contexte industriel dans lequel s'inscrit le projet, la problématique qui le motive,
un état de l'art des approches existantes et leurs limites, la solution proposée dans ses grandes
lignes, les objectifs poursuivis, le périmètre retenu, et la démarche de conduite de projet adoptée.

---

## 1.2 Présentation de l'organisme d'accueil

### 1.2.1 BARAA Consult

> [À compléter : secteur d'activité, taille, clients/marchés visés, activités de BARAA Consult,
> et le rôle de l'entreprise dans l'encadrement de ce PFE.]

### 1.2.2 EIGSI Casablanca

> [À compléter : présentation de l'école, filière/spécialité concernée par ce PFE.]

### 1.2.3 Cadre du stage

Le projet PRISME est réalisé dans le cadre d'un Stage de Fin d'Études, dominante **Big Data &
IA**, année scolaire 2025-2026, sur une durée prévisionnelle de 26 semaines (29/04/2026 au
27/10/2026, voir Plan Directeur §VIII). Le stagiaire, DJOUROBI OMANDA Aldrin Bruno Junior, est
encadré par CHOKRI Soumia côté entreprise (BARAA Consult) et par Zakaria El makhlouki côté EIGSI
Casablanca.

> [À compléter : service ou équipe d'affectation précis au sein de BARAA Consult.]

---

## 1.3 Généralités sur l'ordonnancement et l'équilibrage de charge

Avant de situer PRISME dans son contexte industriel propre, il est utile de rappeler ce que
recouvrent, de façon générale, les notions d'ordonnancement et d'équilibrage de charge, sur
lesquelles repose l'ensemble du projet.

### 1.3.1 L'ordonnancement (scheduling)

L'**ordonnancement** consiste à organiser dans le temps l'exécution d'un ensemble d'opérations en
respectant un jeu de contraintes, en vue d'optimiser un ou plusieurs critères. Un problème
d'ordonnancement se définit classiquement par trois composantes :

- **Les tâches (ou opérations)** à réaliser, chacune caractérisée par une durée, et éventuellement
  des relations d'antériorité avec d'autres tâches (une opération ne peut commencer avant qu'une
  autre ne soit terminée).
- **Les ressources (ou machines)** disponibles pour exécuter ces tâches, en nombre fini, et dont la
  capacité à traiter une tâche donnée peut être totale, partielle (une ressource ne sait exécuter
  qu'un sous-ensemble de tâches) ou nulle.
- **Les contraintes** que la solution doit respecter (précédence, disponibilité, capacité,
  incompatibilités) et **les objectifs** qu'elle doit optimiser (durée totale d'exécution, respect
  de délais, utilisation des ressources, etc.).

Le résultat d'un ordonnancement est un **planning** : une affectation de chaque tâche à une
ressource et à une plage temporelle, telle que l'ensemble des contraintes soit respecté.

### 1.3.2 Classification des problèmes d'ordonnancement

La littérature de recherche opérationnelle distingue plusieurs familles de problèmes
d'ordonnancement d'atelier, selon la façon dont les tâches circulent entre les ressources :

- **Ordonnancement à une seule machine** : toutes les tâches passent par une unique ressource ; le
  problème se réduit à trouver le meilleur ordre de passage.
- **Flow-shop** : toutes les tâches suivent la **même séquence** de ressources (typiquement une
  chaîne de production linéaire).
- **Job-shop** : chaque tâche (ou « job ») suit sa **propre séquence** de ressources, potentiellement
  différente d'une tâche à l'autre — cas plus général et plus représentatif des ateliers réels à
  fabrication diversifiée.
- **Open-shop** : les opérations d'un job peuvent être exécutées **dans n'importe quel ordre** sur
  les ressources requises, sans séquence imposée.

Chacune de ces familles admet une variante dite **flexible**, dans laquelle une opération n'est plus
assignée à une ressource unique et prédéterminée, mais peut être exécutée par **plusieurs ressources
candidates**, avec éventuellement des durées différentes selon la ressource choisie. C'est cette
flexibilité qui introduit, en plus de la question du séquencement temporel, une véritable question
d'**affectation** : il faut décider non seulement *quand* exécuter une opération, mais aussi *sur
quelle ressource*.

### 1.3.3 L'équilibrage de charge (load balancing)

L'**équilibrage de charge** consiste à répartir un ensemble de tâches entre plusieurs ressources de
manière à éviter qu'une partie du parc ne soit surchargée pendant qu'une autre reste sous-utilisée.
En contexte industriel, un mauvais équilibrage se traduit concrètement par des goulots
d'étranglement (une machine ou un poste saturé qui retarde tout l'atelier) alors que des ressources
équivalentes restent disponibles à proximité.

Pris isolément, l'équilibrage de charge répond à une question d'**affectation** : à quelle ressource
confier chaque tâche pour égaliser au mieux la charge de travail. Pris isolément, l'ordonnancement
répond à une question de **séquencement temporel** : dans quel ordre et à quelles dates exécuter les
tâches déjà affectées.

### 1.3.4 Le couplage ordonnancement / équilibrage de charge

Dès qu'une ressource peut être remplacée par une autre pour une même tâche — c'est-à-dire dès que le
problème devient *flexible* (§1.3.2) — l'affectation et le séquencement cessent d'être deux
questions séparables : on ne peut pas décider de la date d'une opération sans savoir sur quelle
ressource elle s'exécutera (les ressources n'ont pas nécessairement la même disponibilité ni la même
durée d'exécution pour la même tâche), et on ne peut pas décider de la ressource sans connaître
l'état de charge de chacune au moment considéré. Ordonnancement et équilibrage de charge deviennent
alors les **deux faces d'une même décision**, qu'il faut résoudre conjointement plutôt que
successivement.

### 1.3.5 Objectifs usuels

Un problème d'ordonnancement peut viser, seul ou combiné, plusieurs critères d'optimisation
classiques :

- **Minimiser le makespan** : la date de fin de la dernière opération, c'est-à-dire la durée totale
  nécessaire pour exécuter l'ensemble du planning.
- **Équilibrer la charge** entre ressources, pour éviter qu'une ressource ne soit surchargée pendant
  que d'autres restent inactives.
- **Minimiser les retards** par rapport à des échéances (dates de livraison, délais contractuels).
- **Maximiser l'utilisation des ressources**, en réduisant les temps morts.
- **Minimiser les changements** (de série, de réglage) lorsque l'atelier pénalise les transitions
  fréquentes entre types de tâches.

Ces objectifs sont fréquemment contradictoires entre eux (minimiser le makespan peut dégrader
l'équilibrage, et inversement), ce qui impose de les pondérer ou de les hiérarchiser selon les
priorités propres à chaque entreprise.

### 1.3.6 Complexité et méthodes de résolution

La grande majorité des problèmes d'ordonnancement d'atelier au-delà du cas à une seule machine sont
**NP-difficiles** : le nombre de combinaisons possibles croît de façon combinatoire avec le nombre de
tâches et de ressources, rendant illusoire une recherche exhaustive de la solution optimale au-delà
d'instances de taille modeste. Deux grandes familles de méthodes sont utilisées en pratique :

- **Les méthodes exactes** (programmation linéaire en nombres entiers, programmation par
  contraintes) garantissent l'optimalité de la solution trouvée, mais leur temps de calcul devient
  prohibitif à mesure que la taille de l'instance augmente.
- **Les méthodes approchées** (heuristiques et métaheuristiques — algorithmes génétiques, recuit
  simulé, recherche tabou, optimisation par colonies de fourmis, règles de priorité/dispatching)
  renoncent à la garantie d'optimalité pour obtenir une solution de bonne qualité en un temps
  raisonnable, y compris sur de très grandes instances.

Le choix entre ces deux familles dépend directement de la taille et de la structure du problème
traité — un compromis central que l'on retrouvera, appliqué concrètement, dans la stratégie de
résolution retenue par PRISME (voir chapitre suivant).

---

## 1.4 Contexte général du projet

L'ordonnancement et l'équilibrage de charge en milieu industriel, bien que largement étudiés en
recherche opérationnelle (§1.3), restent difficiles à mettre en œuvre concrètement en entreprise.
Des outils du marché existent pour les traiter, mais leur adoption réelle se heurte à un obstacle
récurrent : **adapter un solveur générique aux règles effectives d'un atelier donné exige un
paramétrage expert, long et coûteux**. Chaque atelier a ses propres contraintes, ses priorités, ses
façons de gérer les aléas de production — pannes, commandes urgentes, retards. Le coût de
configuration d'un outil générique annule fréquemment le bénéfice attendu de son adoption, en
particulier pour les entreprises qui n'ont pas les moyens de financer un accompagnement en
recherche opérationnelle sur mesure.

Parallèlement, l'essor des grands modèles de langage (LLM) a ouvert la voie à des systèmes capables
de traduire une description en langage naturel vers du code fonctionnel. Une tentation naturelle
est alors de faire appel à une IA générative directement au moment de produire chaque planning.
Cette voie, explorée et écartée par le projet (voir §1.5.3), présente des risques rédhibitoires en
contexte industriel : coût et latence à chaque exécution, non-déterminisme, absence de code
auditable pour expliquer une décision d'ordonnancement.

C'est dans cet espace — entre le paramétrage lourd des solveurs classiques et le risque d'une IA
sollicitée en continu — que se positionne PRISME.

---

## 1.5 Problématique

### 1.5.1 Le problème métier

Comment permettre à une entreprise industrielle d'obtenir un outil d'ordonnancement **adapté à ses
règles propres**, sans lui imposer le coût d'un paramétrage expert classique, tout en conservant la
fiabilité, la rapidité et l'auditabilité d'un code déterministe une fois ce code en production ?

### 1.5.2 Nature exacte du problème d'optimisation traité

Conformément au couplage décrit en §1.3.4, PRISME traite l'ordonnancement et l'équilibrage de
charge comme un **problème indissociable** : décider *quelle ressource* exécute une tâche
(équilibrage) et *quand* elle l'exécute (ordonnancement) sont deux faces d'une même décision.

Formellement, ce problème correspond au **Flexible Job-Shop Scheduling Problem (FJSP)** présenté en
§1.3.2 : chaque opération peut être exécutée par un sous-ensemble de ressources compatibles, et le
solveur doit à la fois **affecter** (choix de la ressource) et **séquencer** (ordre et dates) chaque
opération. Le FJSP est un problème **NP-difficile** (§1.3.6), ce qui a des conséquences directes et
structurantes sur la stratégie de validation retenue dans le projet (voir chapitre correspondant à
la cascade de validation) : la conformité du résultat ne peut pas être jugée par comparaison
exhaustive à une solution de référence unique dans le cas général.

### 1.5.3 Analyse de l'existant : deux impasses

Deux familles d'approches existent pour traiter ce problème, chacune buttant sur une limite
différente :

| Approche | Avantage | Limite |
|---|---|---|
| **Solveur écrit à la main** (RO classique, outils APS du marché) | Fiable, performant, comportement déterministe et explicable | Nécessite un expert en recherche opérationnelle par client, pour une structure de contraintes qui change à chaque atelier ; paramétrage long et coûteux |
| **IA sollicitée à chaque exécution** (un LLM appelé à chaque recalcul de planning) | Grande flexibilité d'adaptation, pas de développement dédié par client | Coût et latence à chaque exécution, non-reproductibilité, aucune trace auditable du raisonnement réellement exécuté en production |

Ces deux impasses se rejoignent sur un même constat : soit la flexibilité coûte cher en expertise
humaine, soit elle coûte cher en confiance et en auditabilité. Le projet part de l'hypothèse qu'il
existe un point d'équilibre entre les deux.

### 1.5.4 Le curseur robustesse / originalité

Une tension centrale traverse la conception du projet : plus le système pré-écrit des stratégies
figées, plus il est robuste, mais moins l'IA « génère » réellement — on retombe vers un outil
paramétrable classique. À l'inverse, plus l'IA génère librement, plus l'originalité de l'approche
est forte, mais plus la validation du résultat devient difficile à maîtriser. La position retenue
par PRISME — une génération encadrée par un vocabulaire métier fini et typé — est développée au
chapitre consacré au DSL T-R-C-O.

---

## 1.6 Solution proposée

PRISME répond à cette problématique par un principe fondateur unique : **générer une fois,
réexécuter plusieurs fois.**

Plutôt que d'appeler l'IA à chaque calcul de planning, PRISME la sollicite **une seule fois**, hors
ligne, à un évènement rare (un nouveau client, ou une nouvelle structure de contraintes chez un
client existant), pour écrire le code source d'un solveur spécialisé à partir d'une description
métier structurée. L'algorithme n'est jamais fixé à l'avance : un agent dédié (le *Benchmarker*)
analyse chaque instance et choisit, dans un catalogue, celui le mieux adapté à sa taille et à sa
structure — OR-Tools CP-SAT, seul algorithme *exact* du catalogue, pour les instances de taille
raisonnable, ou une heuristique (génétique, ACO, tabou, recuit simulé, dispatching, greedy) pour les
instances trop grandes pour un solveur exact.

Une fois ce code validé par une cascade de tests, il est **figé** — persisté tel quel — et
**réexécuté** à chaque itération sur des données qui changent, sans nouvelle sollicitation de l'IA.
Le système obtient ainsi la souplesse d'adaptation d'une IA générative à la conception, et la
fiabilité, la vitesse et l'auditabilité d'un code déterministe classique à l'exécution.

Un principe transversal encadre l'ensemble de l'architecture : **l'humain reste dans la boucle à
chaque décision à risque.** Déclencher un réordonnancement, diagnostiquer un planning anormal, ou
constater un échec de génération : à chaque point sensible, le système alerte et propose, il ne
décide et n'agit jamais seul.

---

## 1.7 Objectifs du projet

### 1.7.1 Objectif général

Concevoir et réaliser une plateforme capable de générer automatiquement, à partir d'une description
métier structurée, le code d'un solveur d'ordonnancement industriel (FJSP), puis de l'exécuter de
façon répétée, sécurisée et auditable.

### 1.7.2 Objectifs spécifiques

- Définir un modèle pivot (le DSL T-R-C-O) suffisamment expressif pour décrire le noyau réel d'un
  problème d'ordonnancement industriel, et suffisamment borné pour rester vérifiable.
- Construire une chaîne de validation capable de juger un solveur généré — dont le comportement
  n'est pas garanti à l'avance — sur les propriétés du planning qu'il produit, plutôt que sur sa
  forme.
- Mettre en œuvre un pipeline de génération multi-agents borné (nombre de tentatives de réparation
  limité) qui échoue explicitement et signale l'échec à un humain plutôt que de s'acharner
  silencieusement.
- Garantir qu'un code généré par IA, une fois exécuté, ne puisse pas compromettre le système ni les
  données d'autres clients (sandbox isolé, surface de génération bornée).
- Exposer l'ensemble de ces briques à travers une API et un tableau de bord opérateur permettant
  l'ingestion des données, le suivi de la génération, le déclenchement d'exécutions et la validation
  humaine des résultats.

---

## 1.8 Périmètre du projet

La preuve de concept ne dépend pas du nombre de familles de contraintes couvertes, mais du bon
fonctionnement de bout en bout de la boucle complète : description DSL → génération de code →
exécution → validation → planning utile. Le projet retient donc un **noyau minimal viable** :

- **Précédence** entre opérations.
- **Compatibilité ressource-tâche** (chaque opération n'est exécutable que sur un sous-ensemble de
  ressources).
- **Durées** des opérations.

Sont volontairement laissées hors périmètre initial — sans que l'architecture ou le DSL ne
l'excluent pour autant — les familles suivantes, identifiées comme réelles mais différées pour ne
pas diluer la preuve de concept : temps de changement de série (setup) dépendants de la séquence,
disponibilité et calendriers de ressources, priorités clients et dates de livraison fines, capacité
(lots, stocks, files d'attente).

---

## 1.9 Démarche de conduite de projet

Le principe directeur adopté pour l'ordonnancement des travaux a été le suivant : **chaque brique
déterministe et testable est construite avant toute brique reposant sur l'IA.** Concrètement, le
projet a d'abord bâti ce qui permet de *juger* un code généré (le DSL, le vérificateur de
faisabilité, le banc de test synthétique), avant de bâtir ce qui *génère* réellement ce code. Le
jalon de bascule a été la mise au point de la cascade de validation : tant qu'elle n'était pas
fiable sur un solveur écrit à la main, aucune brique de génération par IA n'a été abordée.

> [À compléter : planification effective du PFE — jalons/sprints, durée totale, éventuel diagramme
> de Gantt.]

---

## 1.10 Conclusion du chapitre

Ce chapitre a situé PRISME à la croisée de deux constats : le coût prohibitif du paramétrage expert
des solveurs d'ordonnancement classiques, et le risque inacceptable, en contexte industriel, d'une
IA sollicitée à chaque décision. Le principe fondateur retenu — générer une fois, réexécuter
plusieurs fois, sous supervision humaine à chaque étape critique — structure l'ensemble des choix
de conception détaillés dans les chapitres suivants, à commencer par le modèle pivot T-R-C-O qui
sert à la fois de format d'échange, d'entrée de génération et de cadre de validation.

---

# Chapitre 2 — Enjeux et analyse du besoin

Ce chapitre précise, après le cadrage général posé au chapitre 1, ce que le projet représente
concrètement pour l'entreprise d'accueil — ses enjeux — puis formalise l'expression du besoin par
les outils classiques de l'analyse fonctionnelle externe.

## 2.1 Périmètre du projet

> [À compléter — le périmètre effectivement retenu (noyau minimal viable FJSP : précédence,
> compatibilité ressource-tâche, durées) est déjà posé au §1.8 du chapitre 1 ; cette section
> reprendra ce contenu dans le déroulé du chapitre 2, avec le détail du périmètre exclu.]

## 2.2 Contraintes du projet

> [À compléter — contraintes temporelles (durée du stage, disponibilité des interlocuteurs),
> contraintes métiers/humaines (acceptation, lisibilité, confiance) et contraintes de
> confidentialité/conformité (RGPD, exécution maîtrisée du code généré).]

## 2.3 Enjeux pour l'entreprise

L'implantation d'un système de génération et d'exécution de solveurs d'ordonnancement répond,
pour l'entreprise d'accueil, à des enjeux de trois natures : techniques, économiques et
organisationnels. Ces enjeux se situent, pour la plupart, au croisement direct des deux
compétences cœur de la spécialité **Intelligence Artificielle & Big Data** : orchestrer des agents
génératifs capables d'écrire du code sur mesure (IA), et ingérer, canoniser puis exploiter des
données hétérogènes issues de systèmes industriels réels (Big Data). Ce projet constitue à ce
titre, pour l'étudiant, un terrain de validation concret des compétences attendues en fin de
formation, autant qu'une réponse aux besoins de l'entreprise.

### 2.3.1 Enjeux techniques

- **Fiabilité du code généré** *(compétence IA générative)* : un solveur produit par le système ne
  doit jamais être exécuté sans avoir été validé au préalable — faisabilité du planning produit,
  respect strict des contraintes déclarées. Aucune exception ne doit être tolérée sur ce point, le
  code généré étant par nature non garanti à l'avance ; c'est un défi caractéristique des systèmes
  à IA générative, au cœur de la formation.
- **Reproductibilité et explicabilité** *(compétence IA)* : à situation comparable (mêmes tâches,
  mêmes ressources, mêmes contraintes), le système doit produire la même solution, et cette
  solution doit rester justifiable et auditable — condition de confiance pour des équipes qui n'ont
  pas à comprendre le code du solveur pour en accepter le résultat.
- **Ingestion et canonicalisation de données hétérogènes** *(compétence Big Data)* : les données
  d'un atelier industriel arrivent sous des formats disparates (export ERP/MES, fichier Excel de
  suivi, saisie manuelle) ; les normaliser vers un modèle pivot unique et exploitable est un
  problème caractéristique de l'ingénierie Big Data, indépendant de la génération de code elle-même.
- **Qualité des plannings produits** : optimiser des critères explicites (délai total, retards,
  équilibrage de charge) plutôt que de s'en remettre à une estimation empirique.
- **Performance et passage à l'échelle** : un temps de calcul compatible avec un usage opérationnel
  réel, obtenu en séparant nettement une génération coûteuse mais rare (hors ligne) d'une exécution
  rapide et répétée (en ligne).
- **Sécurité de l'exécution** *(compétence IA — sécurisation de systèmes génératifs)* : le code
  généré par l'IA s'exécute dans un environnement isolé, sans jamais mettre en danger le reste du
  système d'information ni les données d'autres clients — un enjeu propre à tout système qui
  exécute du code produit par un LLM, distinct des enjeux de sécurité applicative classiques.

### 2.3.2 Enjeux économiques

- **Réduction du coût d'intégration** *(valeur propre de l'IA générative)* : supprimer, pour chaque
  nouvel atelier ou chaque nouvelle contrainte métier, le projet d'ingénierie spécifique qu'exigerait
  normalement le paramétrage d'un solveur classique par un expert en recherche opérationnelle —
  un LLM assume ici un travail auparavant réservé à un expert humain.
- **Libération de temps d'ingénierie et de management** : récupérer le temps aujourd'hui consacré
  à l'estimation manuelle des durées, à l'affectation empirique des tâches et à la
  reparamétrisation récurrente des outils existants à chaque évolution de l'atelier.
- **Réduction des coûts de non-qualité** : limiter les retards, pénalités contractuelles, heures
  supplémentaires non anticipées et recours à la sous-traitance d'urgence provoqués par un
  ordonnancement mal calibré.
- **Retour sur investissement dans la durée** : un solveur, une fois généré et validé, est
  réexécuté indéfiniment sans nouveau coût de génération — l'investissement initial se rentabilise
  sur toute la durée de vie du solveur, jusqu'au prochain changement structurel de l'atelier.

### 2.3.3 Enjeux organisationnels

- **Adaptabilité multi-contextes** : un même socle applicatif doit pouvoir produire un solveur
  adapté à des ateliers de structure très différente, sans réécriture du cœur du système à chaque
  nouveau client.
- **Capitalisation sur la donnée et le processus** *(compétence Big Data)* : transformer les
  données de production aujourd'hui dispersées (fichiers Excel, exports ERP/MES, journaux
  d'exécution) en un actif directement exploitable pour piloter et améliorer l'atelier, plutôt que
  de les laisser dormantes.
- **Acceptation par les équipes terrain** : le système doit être perçu comme une aide à la
  décision, jamais comme un instrument de contrôle ou de surveillance des personnes — condition
  de son adoption réelle par les responsables d'atelier.
- **Acculturation à l'IA agentique** *(compétence IA)* : démontrer la capacité de l'organisation à
  intégrer une architecture pilotée par des agents IA dans ses processus opérationnels, tout en
  gardant l'humain décisionnaire à chaque étape à risque (§1.6).

### 2.3.4 Un enjeu supplémentaire : la validation d'une double compétence IA & Big Data

Au-delà de la valeur créée pour l'entreprise, ce projet représente, pour l'étudiant, l'occasion de
mobiliser sur un seul système les deux volets de sa spécialité de fin de formation. La dimension
**IA** s'exprime dans l'orchestration d'agents génératifs (compréhension, génération de code,
validation) et dans la maîtrise du risque propre à l'exécution de code produit par un LLM. La
dimension **Big Data** s'exprime dans la conception d'un modèle pivot capable d'ingérer et de
canoniser des données industrielles hétérogènes, condition préalable à toute génération. Réussir
ce projet constitue ainsi une preuve de compétence directement alignée avec le diplôme visé, autant
qu'une réponse au besoin de l'entreprise.

## 2.4 Analyse du besoin

Avant toute conception technique, l'analyse fonctionnelle externe cadre ce que le système doit
faire, pour qui, et dans quelles limites — indépendamment des choix d'implémentation qui seront
arbitrés par la suite (§1.8, §2.1).

### 2.4.1 Bête à cornes

```
   Organisations industrielles                     Données de production
   responsables d'un atelier                        et ressources disponibles
   (chefs de production,           <----------->     (gammes, exports ERP/MES,
   ordonnanceurs, intégrateurs SI)                    fichiers de suivi, historiques)
                    \                                     /
                     \                                   /
                      \                                 /
                            SYSTÈME D'ORDONNANCEMENT
                              ADAPTATIF (PRISME)
                                     |
                                     |
                  Comprendre le contexte de l'atelier, générer un
                  solveur d'ordonnancement et d'équilibrage de charge
                  sur mesure, l'exécuter en sécurité, et permettre à
                  l'humain de superviser et de valider chaque décision
```

*Figure 2.1 — Diagramme bête à cornes.*

| Question | Réponse |
|---|---|
| À qui rend-il service ? | Aux organisations industrielles responsables d'un atelier : chefs de production, ordonnanceurs, intégrateurs SI. |
| Sur quoi agit-il ? | Sur les tâches et gammes de production, la charge des ressources disponibles, et les données de processus de l'entreprise (exports ERP/MES, fichiers de suivi, historiques d'exécution). |
| Dans quel but ? | Comprendre le contexte métier, générer un solveur d'ordonnancement sur mesure, l'exécuter en toute sécurité, et permettre à l'humain de superviser et de valider chaque décision à risque. |

### 2.4.2 Diagramme pieuvre

Le système est au centre d'un écosystème de fonctions principales (FP), qui expriment le service
rendu, et de fonctions contraintes (FC), qui expriment les limites que ce service doit respecter.

| Réf. | Type | Fonction | Acteurs / outils sollicités |
|---|---|---|---|
| FP1 | Principale | **Compréhension du contexte** : ingérer et interpréter les données disponibles sur le processus de l'atelier pour en extraire une représentation structurée des tâches, ressources et contraintes. | Agent de compréhension, historiques d'exécution |
| FP2 | Principale | **Répartition des charges** : orienter chaque tâche vers la ressource la plus pertinente (compétences, disponibilité, charge courante) avant séquencement. | Contraintes ressource-tâche déclarées |
| FP3 | Principale | **Génération de solveur** : formaliser le problème dans le modèle pivot et générer un solveur d'ordonnancement sur mesure. | Agent de génération, OR-Tools CP-SAT |
| FP4 | Principale | **Ordonnancement & équilibrage** : exécuter le solveur validé pour produire un planning et des indicateurs de charge. | Agent d'exécution, bac à sable isolé |
| FP5 | Principale | **Supervision** : observer le fonctionnement réel, détecter les dérives, et alerter en vue d'une décision humaine. | Tableau de bord, historique d'exécutions |
| FP6 | Principale | **Exposition par API** : mettre l'ensemble des services à disposition des applications de l'entreprise. | API REST, documentation interactive |
| FC1 | Contrainte | **Validation systématique** : garantir la faisabilité et le respect des contraintes de tout solveur avant sa mise en exécution. | Cascade de validation, jeux de tests |
| FC2 | Contrainte | **Compatibilité technique** : s'exécuter sur l'infrastructure existante sans refonte du système d'information. | Conteneurisation |
| FC3 | Contrainte | **Généricité multi-contextes** : s'adapter à des ateliers de structure différente via un modèle pivot commun. | Modèle pivot T-R-C-O |
| FC4 | Contrainte | **Décision humaine préservée** : ne jamais imposer automatiquement une décision à risque. | Validation humaine, tableau de bord |

*Figure 2.2 — Diagramme pieuvre.*

> Cette expression du besoin couvre l'ambition portée par le plan directeur du stage. Le périmètre
> effectivement retenu pour la réalisation — quelles fonctions sont construites dès cette itération
> et lesquelles restent différées — est arbitré au §1.8 et précisé au §2.1 ; ce point reste, à ce
> stade, en cours de clarification avec les tuteurs entreprise et académique.

---

# Chapitre 3 — Ressources, méthodologie et bilan du cadrage initial

Ce chapitre précise, après le cadrage et l'expression du besoin posés aux chapitres 1 et 2, les
moyens mobilisés pour réaliser le projet, la démarche effectivement suivie, et la façon dont le
plan directeur initial (§1.7) a été précisé — parfois reformulé — à l'épreuve de la réalisation.
Ce dernier point (§3.3) n'est pas un constat d'échec : c'est la trace des arbitrages techniques
qu'exige tout projet mêlant IA générative et ingénierie logicielle, et il conditionne directement
la lecture du WBS à jour proposé au §3.4.

## 3.1 Ressources mobilisées

### 3.1.1 Encadrement

- **Tutrice entreprise** (CHOKRI Soumia, BARAA Consult) : cadrage des attentes métier, validation
  des livrables opérationnels.
- **Tuteur académique** (Zakaria El makhlouki, EIGSI Casablanca) : suivi de la conformité aux
  attendus pédagogiques du PFE.

> [À compléter : implication effective de Key Users métier — s'ils ont existé pour ce PFE — dans
> le cadrage ou la validation intermédiaire.]

### 3.1.2 Compétences mobilisées

Le projet mobilise, sur un seul système, les deux volets de la spécialité Intelligence
Artificielle & Big Data (voir §2.3.4) : l'orchestration d'agents génératifs appuyés sur un LLM
(compréhension, génération de code, revue, correction), et l'ingénierie de données nécessaire pour
canoniser des exports industriels hétérogènes vers un modèle pivot unique. S'y ajoutent des
compétences de génie logiciel plus classiques : conception d'API REST, sécurisation de
l'exécution de code non fiable par construction, tests automatisés.

### 3.1.3 Ressources matérielles et logicielles

Aucune ressource de calcul dédiée (GPU, cluster) n'a été nécessaire : la génération de code
s'appuie sur un service LLM externe (§6), et l'exécution des solveurs — y compris sur
l'instance de test la plus volumineuse (2 165 tâches, voir §9) — reste un calcul CPU classique. Le
projet est réalisé en 100 % open-source : Python 3.11 (`uv` pour la gestion de dépendances),
FastAPI, Pydantic v2, OR-Tools CP-SAT, PostgreSQL, Docker, LangGraph, pytest/ruff côté serveur ;
React, TanStack Start et Tailwind CSS côté tableau de bord. Ce choix technologique diffère, sur
plusieurs points, de la stack initialement envisagée au plan directeur — voir §3.3.

## 3.2 Méthodologie suivie

### 3.2.1 Démarche hybride annoncée

La démarche retenue au démarrage couplait un cycle proche de CRISP-DM pour la composante IA/data
(compréhension du problème, préparation et représentation des données, modélisation, validation,
itération) et une approche incrémentale de type Kanban pour la composante applicative (routes API,
tableau de bord), les phases de cadrage et de clôture restant séquentielles.

### 3.2.2 Principe d'ordonnancement des travaux : juger avant de générer

Le principe directeur réellement suivi, déjà posé au §1.9, a été renforcé en cours de projet :
**chaque brique déterministe et testable est construite avant toute brique reposant sur l'IA.**
Concrètement, l'ordre de construction a délibérément dévié du séquencement le plus naturel
(compréhension → génération → validation) :

- Le vérificateur de faisabilité et le banc de test synthétique (capables de *juger* un solveur)
  ont été rendus fiables sur un solveur écrit à la main, avant qu'aucune ligne de génération par IA
  ne soit abordée — un solveur généré ne peut être jugé utile que si le juge lui-même est déjà
  digne de confiance.
- Le squelette de l'API et le chemin d'exécution (`/execution/{instance_id}`) ont été branchés sur
  un unique solveur de référence, écrit à la main et enregistré manuellement, avant que le pipeline
  de génération multi-agents ne soit lui-même prêt — ce qui a permis de valider le contrat
  d'exécution (bac à sable, cloisonnement multi-tenant) indépendamment des aléas de la génération.
- La boucle de réparation multi-agents (réviseur/correcteur borné), présentée comme une étape
  intermédiaire du plan initial, n'a été construite qu'en dernier, sous la forme d'une réécriture
  complète en `LangGraph` plutôt que la boucle procédurale envisagée au départ.

Ce choix — construire l'arbitre avant le joueur, l'infrastructure d'exécution avant le générateur —
est le principal enseignement méthodologique du projet : il a permis, à chaque étape, de disposer
d'un système partiellement fonctionnel et testable plutôt que d'un ensemble de briques
interdépendantes livrées en bloc.

## 3.3 Écarts entre le plan directeur et la réalisation

Trois choix du plan directeur initial (§1.6, Architecture du Système Multi-Agents, §VI) ont été
reformulés à l'usage. Chacun est présenté ici comme un arbitrage technique documenté, pas comme un
renoncement à l'ambition d'origine — la validation formelle de ce périmètre reformulé avec les
tuteurs reste, comme indiqué au §2.4, en cours.

### 3.3.1 De la compréhension BPMN à un agent de compréhension universel

*Prévu* : un agent dédié au parsing de modèles BPMN 2.0 (bibliothèques `bpmn-python`/`pm4py`),
source d'entrée privilégiée du système.

*Réalisé* : un agent de compréhension fondé sur un LLM, capable d'interpréter n'importe quel texte
brut fourni par le client — export CSV, dump JSON, description en langage naturel — sans dépendre
d'un format ou d'un outillage de parsing spécifique ; des adaptateurs déterministes distincts
traitent en outre les formats déjà connus (CSV, JSON, ERP dédié) sans aucun appel à un LLM.

*Justification* : un modèle BPMN formalise l'enchaînement des activités, mais ne porte pas, à lui
seul, les faits propres à un problème d'ordonnancement flexible (compatibilité tâche-ressource
avec une durée par couple, poids des objectifs) — même un analyseur BPMN parfait aurait exigé une
étape d'interprétation supplémentaire pour aboutir au modèle pivot. Élargir l'agent de
compréhension à n'importe quelle donnée brute disponible couvre, avec un seul mécanisme, un
périmètre strictement plus large que le seul BPMN — cohérent avec le diagnostic de l'existant
(§1.4) selon lequel l'essentiel de la donnée réellement disponible en PME/ETI industrielle est un
export ERP ou un fichier de suivi, plus rarement un modèle BPMN structuré.

### 3.3.2 De l'estimation ML et de la répartition hongroise à des durées déclarées et un solveur unifié

*Prévu* : un agent d'estimation par apprentissage supervisé (`scikit-learn`/`XGBoost`) prédisant la
durée de chaque opération à partir d'historiques d'exécution, puis un agent de répartition
(algorithme hongrois / min-cost flow) affectant chaque tâche à une ressource avant séquencement.

*Réalisé* : la durée est un fait déclaré ou dérivé des compétences (`CompatibiliteRessourceTache`,
dérivation partagée dans `adapters/competence_derivation.py`), jamais une prédiction d'un modèle
entraîné ; l'affectation tâche-ressource est résolue nativement par le solveur généré — CP-SAT ou
l'heuristique choisie par l'agent Benchmarker selon la taille de l'instance — conjointement au
séquencement, plutôt que pré-calculée par un agent distinct.

*Justification* : un modèle de prédiction de durée exige, pour être fiable, un historique
d'exécution suffisant par couple (type de tâche, ressource) — une donnée que le diagnostic de
l'existant (§1.4) qualifie lui-même de « mémoire opérationnelle dormante », rarement digitalisée
de façon exploitable chez la cible visée. Plutôt que de conditionner tout le pipeline à une étape
d'entraînement à la fiabilité incertaine, PRISME traite la durée comme une donnée déclarée ou
dérivée — vérifiable sans entraînement — l'agent de compréhension signalant toute incertitude via
des avertissements destinés à une validation humaine, plutôt que de présenter une prédiction comme
une vérité. Précalculer une affectation par algorithme hongrois revient, de plus, à dupliquer une
décision que le solveur exact prend déjà nativement et *conjointement* au séquencement : les
deux résolus séparément risquent une affectation localement bonne mais globalement sous-optimale
une fois les contraintes de séquencement prises en compte.

### 3.3.3 D'un agent Orchestrateur dédié à l'orchestration native de LangGraph

*Prévu* : un agent Orchestrateur explicitement chargé de coordonner la séquence des agents, l'état
partagé, et l'arbitrage des boucles de réparation.

*Réalisé* : le pipeline de génération est exprimé directement comme un `StateGraph` LangGraph, qui
assure nativement le séquencement des agents, l'état partagé et les boucles conditionnelles — un
module Orchestrateur distinct a été développé puis retiré du projet, devenu une couche redondante
n'acheminant plus aucune décision propre une fois le graphe LangGraph en place.

## 3.4 WBS à jour

Le tableau suivant fait correspondre les macro-tâches du plan directeur initial (MT1-MT9) aux
étapes effectivement livrées. La numérotation « Étape » est celle du suivi de projet continu
(voir annexe — WBS détaillé et diagramme de Gantt).

| Macro-tâche prévue | Contenu prévu | Correspondance réalisée | Statut |
|---|---|---|---|
| MT1 — Cadrage et analyse du besoin | Modélisation BPMN de l'atelier pilote, cahier des charges | Chapitres 1-2 de ce rapport | ✅ fait (périmètre BPMN reformulé, §3.3.1) |
| MT2 — Compréhension & modèle pivot | Parsing BPMN, modèle pivot | Étape 1 — DSL T-R-C-O ; agent de compréhension universel | ✅ fait (compréhension reformulée, §3.3.1) |
| MT3 — Estimation des charges | Agent ML (durée + charge prévisionnelle) | Durées déclarées/dérivées des compétences | 🔁 reformulé, §3.3.2 |
| MT4 — Répartition des charges | Agent d'affectation (algorithme hongrois) | Résolu nativement par le solveur généré | 🔁 reformulé, §3.3.2 |
| MT5 — Génération & validation de solveur | Génération OR-Tools, validation | Étapes 4-6 — générateur, cascade de validation, boucle de réparation LangGraph | ✅ fait, conforme |
| MT6 — Exécution, équilibrage & benchmark | Exécution, benchmark vs baseline | Étape 7 — store + bac à sable ; benchmarks réels (§9) | ✅ fait |
| MT7 — Supervision & amélioration continue | Agent de détection de dérives/goulots | Vues de supervision consultatives, boucle de diagnostic d'échec de génération | 🔁 reformulé — supervision consultative, pas de détection proactive de dérive en exécution |
| MT8 — Mise à disposition par service (API) | API REST conteneurisée | Étape 8 — API + adaptateurs ERP | ✅ fait |
| MT9 — Validation, portabilité & clôture | Démonstration pilote, rapport, soutenance | Ce rapport et sa soutenance | 🚧 en cours |

Deux éléments substantiels ont été livrés sans figurer explicitement au WBS initial : un tableau de
bord complet (React/TanStack, une douzaine de pages opérateur — ingestion des données, instances,
suivi de la génération, centre d'exécution, plannings, audit, analytique, gestion des clients) et
une architecture de sécurité à trois couches (DSL borné, allowlist
statique, bac à sable Docker isolé), détaillée au chapitre 6. À l'inverse, le déploiement en
production et l'observabilité (métriques, traces, alertes) restent hors périmètre de ce PFE — voir
les perspectives au chapitre 9.

---

# Chapitre 4 — Le modèle pivot T-R-C-O

Le chapitre 3 a montré comment plusieurs briques prévues au plan directeur (compréhension BPMN,
estimation par apprentissage, répartition par algorithme hongrois) ont été reformulées à l'usage.
Ce qui a rendu ces reformulations possibles sans remettre en cause l'architecture d'ensemble, c'est
l'existence d'un contrat unique et stable entre l'amont et l'aval du système : le modèle pivot
T-R-C-O (Tâches, Ressources, Contraintes, Objectifs). Ce chapitre en détaille la conception.

## 4.1 Rôle du modèle pivot

Le DSL T-R-C-O joue simultanément trois rôles dans l'architecture :

1. **Format d'échange** avec le système d'information du client — un adaptateur ERP écrit à la
   main (§7) ou l'agent de compréhension (§3.3.1) traduisent tous deux vers ce même format, quelle
   que soit la source d'origine.
2. **Entrée de la génération** — l'agent de génération de code (chapitre 5) n'écrit jamais de
   solveur pour un atelier particulier : il écrit un solveur pour *une instance T-R-C-O*, ce qui
   rend la génération indépendante du client et du format d'origine de ses données.
3. **Cadre de validation** — la cascade de validation (chapitre 6) juge tout solveur généré sur les
   propriétés du planning qu'il produit *au regard d'une instance T-R-C-O*, jamais sur la forme du
   code lui-même.

C'est cette séparation stricte entre agents amont (qui produisent une instance T-R-C-O, quelle que
soit la donnée de départ) et agents aval (qui ne consomment que cette instance) qui a permis, en
pratique, de remplacer un mécanisme de compréhension prévu (BPMN) par un autre (agent universel)
sans toucher à la génération ni à la validation : les deux ignorent tout de la provenance de
l'instance qu'ils reçoivent.

## 4.2 Les quatre axes

### 4.2.1 T — Tâches

Une tâche est une opération à ordonnancer, caractérisée par un identifiant, un nom optionnel, une
priorité informative (1 à 5) et un statut de suivi (à faire / en cours / terminé / bloqué). Aucun
de ces deux derniers champs n'est lu par le solveur ni par le vérificateur de faisabilité : ils
sont purement descriptifs. Point notable, volontaire : **la tâche ne porte pas de durée.** En
ordonnancement flexible (FJSP), la durée d'une opération dépend de la ressource qui l'exécute, pas
de la seule tâche — une pièce découpée à la main et une pièce découpée au laser n'ont pas la même
durée d'exécution pour la même opération logique. La durée vit donc sur l'axe C, attachée au couple
tâche-ressource (§4.2.3).

### 4.2.2 R — Ressources

Une ressource est un poste, une machine, un opérateur ou une équipe pouvant exécuter des tâches,
caractérisée par un identifiant, un nom optionnel, un type informatif (humain / machine / équipe)
et une liste de compétences qu'elle porte. Comme pour les tâches, ni le type ni le nom ne sont
exploités par le moteur de résolution — seules les compétences le sont, indirectement, via la
contrainte de compétence requise (§4.2.3).

### 4.2.3 C — Contraintes

Les contraintes forment un type discriminé (un champ `type` distingue chaque nature de contrainte),
choix qui permet d'en ajouter de nouvelles sans jamais modifier les contraintes existantes. Deux
contraintes forment le **noyau minimal viable** retenu pour ce PFE (§1.8) :

- **Précédence** (`precedence`) : la tâche `avant` doit être terminée avant que la tâche `apres` ne
  commence.
- **Compatibilité ressource-tâche** (`compatibilite_ressource_tache`) : la tâche `tache` peut
  s'exécuter sur la ressource `ressource`, avec une durée `duree` propre à ce couple — une tâche
  compatible avec plusieurs ressources porte plusieurs contraintes de ce type, chacune avec sa
  propre durée. C'est l'unique porteur de durée du modèle (§4.2.1), et chaque tâche doit en avoir
  au moins une : une tâche sans aucune compatibilité déclarée n'aurait, par construction, aucune
  durée connue.

Quatre extensions optionnelles, sans effet sur une instance qui ne les utilise pas, complètent ce
noyau : l'**échéance** (`echeance`, une date limite relative), la **compétence requise**
(`competence_requise`, qui impose qu'une ressource déclarée compatible pour une tâche possède
effectivement la compétence exigée — un garde-fou structurel vérifié à la construction de
l'instance, pas laissé au solveur), la **capacité** (`capacite`, le nombre d'opérations qu'une
ressource peut traiter simultanément — 1 par défaut en son absence) et l'**incompatibilité**
(`incompatibilite`, deux tâches qui ne peuvent jamais partager la même ressource, indépendamment de
tout chevauchement temporel).

### 4.2.4 O — Objectifs

Cinq objectifs paramétrables, également formés d'une union discriminée, peuvent chacun recevoir un
poids (pour une combinaison pondérée de plusieurs objectifs) et des paramètres propres :
minimiser le makespan (durée totale, avec cible et pénalité de dépassement optionnelles),
équilibrer la charge entre ressources (trois méthodes : écart maximal, variance, indice de Gini),
minimiser les retards par rapport aux échéances (avec fonction de pénalité et jours de grâce),
maximiser l'utilisation des ressources, et minimiser les changements de ressource entre tâches
successives. Cette paramétrabilité — un objectif du client se règle sans toucher au code du
solveur généré — a été ajoutée après la première version du DSL, qui ne portait que la minimisation
du makespan.

## 4.3 Identifiant : un vocabulaire fini comme contrôle de sécurité

Tous les identifiants du DSL (`Tache.id`, `Ressource.id`, les références de contrainte) partagent
un même type, `Identifiant` : une chaîne de 1 à 64 caractères, restreinte à l'alphabet
`[A-Za-z0-9_-]`. Ce choix n'est pas qu'une question d'hygiène de données : c'est un **contrôle de
sécurité**, au même titre que le bac à sable d'exécution (chapitre 6). Le code du solveur est
généré par un LLM à partir du contenu d'une instance T-R-C-O ; borner strictement la forme des
identifiants qu'une instance peut porter borne d'autant la surface que l'IA peut effectivement
faire apparaître dans le code qu'elle écrit. Le même principe de prudence gouverne chaque modèle du
DSL, avec `extra="forbid"` systématique (Pydantic v2) : un champ non prévu dans le schéma est
rejeté à l'ingestion, jamais silencieusement ignoré ni transmis tel quel à la génération.

## 4.4 InstanceTRCO : l'agrégat racine et ses garde-fous croisés

`InstanceTRCO` agrège les quatre axes et applique, à sa construction, cinq vérifications qui ne
peuvent se faire qu'en croisant plusieurs axes à la fois — impossibles à exprimer sur un axe pris
isolément : unicité des identifiants au sein de chaque axe, toute contrainte ne référence que des
tâches ou ressources réellement déclarées dans l'instance, toute tâche est couverte par au moins
une compatibilité ressource-tâche, et toute compatibilité déclarée pour une tâche à compétences
requises porte sur une ressource effectivement qualifiée. Un payload qui échoue l'une de ces
vérifications est rejeté — avec un message d'erreur nommant précisément l'anomalie — avant même
d'atteindre le solveur ou l'agent de génération. C'est ce mécanisme, précisément, que la
documentation du projet désigne comme le **garde-fou amont** : quel que soit le canal d'entrée
(saisie manuelle, adaptateur ERP écrit à la main, agent de compréhension), toute instance traverse
exactement la même validation avant d'être considérée comme exploitable.

## 4.5 Planning : la sortie, hors du DSL d'entrée

`Planning` (une liste d'`OperationPlanifiee` : tâche, ressource, instant de début) est la sortie
attendue d'un solveur, pas un cinquième axe d'entrée — mais elle partage le vocabulaire du DSL
(`Identifiant`) et vit à ses côtés pour cette raison. Contrairement à `InstanceTRCO`,
volontairement **permissive** : aucune règle n'y est imposée à la construction — une tâche non
planifiée, planifiée deux fois, ou affectée à une ressource inconnue ne lève aucune exception. C'est
un choix délibéré : juger un planning est le rôle du vérificateur de faisabilité (chapitre 6), pas
du schéma lui-même — un planning illégal doit produire un diagnostic exploitable, jamais interrompre
brutalement l'exécution d'un solveur en production.

## 4.6 Conclusion du chapitre

Le modèle pivot T-R-C-O est la pièce qui a permis au projet d'absorber, sans réécriture profonde,
les trois reformulations décrites au chapitre 3 : tant qu'un mécanisme amont produit une instance
T-R-C-O valide et qu'un mécanisme aval en consomme une, la nature de ces mécanismes — parseur BPMN
ou agent de compréhension universel, agent d'affectation dédié ou résolution native par le solveur
— reste un détail d'implémentation sans incidence sur le reste de l'architecture, détaillée au
chapitre suivant.

# Note de cadrage — PRISME

**Plateforme de génération et d'exécution de solveurs d'ordonnancement pilotée par IA**

*Projet de Fin d'Études — EIGSI Casablanca × BARAA Consult*

---

## 1. Résumé exécutif

PRISME est une API qui **génère automatiquement, à partir d'une description métier, le code d'un solveur d'ordonnancement et d'équilibrage de charge**, puis exécute ce code de façon répétée pour produire des plannings d'atelier.

La particularité du projet — et son innovation centrale — est le **découplage entre génération et exécution**. Contrairement aux approches où une IA est sollicitée à chaque décision d'ordonnancement (coûteuses, non déterministes, non auditables), PRISME fait intervenir l'IA **une seule fois** pour écrire le code d'un solveur spécialisé (basé sur OR-Tools CP-SAT). Ce code, une fois validé, est **figé et réexécuté** à chaque itération sur des données qui changent, sans nouvelle sollicitation de l'IA. On obtient ainsi la souplesse d'adaptation d'une IA générative et la fiabilité, la vitesse et l'auditabilité d'un code déterministe classique.

Le système s'adresse aux industries qui utilisent des outils d'ordonnancement du marché mais souffrent de leur **paramétrage lourd** pour les adapter à un contexte spécifique. PRISME remplace ce paramétrage par une **description en langage métier structuré** (le modèle pivot T-R-C-O), que l'IA traduit en code de solveur sur mesure.

Le fil directeur de toute l'architecture est le suivant : **le système assiste la décision à chaque étape critique, mais ne se substitue jamais à l'humain sur les décisions à risque.** Réordonnancement, diagnostic d'anomalie, échec de génération : à chaque point sensible, l'humain est alerté et décide.

---

## 2. Problème traité et positionnement

### 2.1 Le problème métier

L'ordonnancement et l'équilibrage de charge en industrie sont des problèmes classiques et bien étudiés. Des outils existent, mais leur adoption bute sur un obstacle récurrent : **adapter un solveur générique aux règles réelles d'une entreprise donnée demande un paramétrage expert, long et coûteux.** Chaque atelier a ses contraintes propres, ses priorités, ses façons de gérer les aléas. Le coût de configuration annule souvent le bénéfice de l'outil.

### 2.2 Nature exacte du problème d'optimisation

PRISME traite l'**ordonnancement et l'équilibrage de charge comme un problème indissociable**. Décider *quelle ressource* exécute une tâche (équilibrage) et *quand* elle l'exécute (ordonnancement) sont deux faces d'une même décision : on ne peut pas dater sans savoir sur quelle ressource.

Formellement, cela correspond au **Flexible Job-Shop Scheduling Problem (FJSP)** : chaque opération peut être exécutée par un sous-ensemble de ressource compatibles, et le solveur doit à la fois **affecter** (choix de la ressource) et **séquencer** (ordre et dates). CP-SAT est adapté précisément parce qu'il gère nativement ce couplage affectation + séquencement. Le FJSP est NP-difficile, ce qui a des conséquences directes sur la stratégie de validation (voir §7).

### 2.3 Mode de fonctionnement : réordonnancement réactif avec humain dans la boucle

PRISME n'est **pas** un système de replanification autonome temps-réel. C'est un **système d'aide à la décision pour le réordonnancement réactif déclenché par événement** (*event-triggered reactive rescheduling, human-in-the-loop*).

Le cycle de fonctionnement est le suivant :

1. Un aléa survient dans l'atelier (panne ressource, commande urgente, retard).
2. Le système **lève une alerte sur le tableau de bord**.
3. Un opérateur humain voit l'alerte et **décide de déclencher** le recalcul.
4. Le solveur (déjà généré et validé) s'exécute sur l'état courant de l'atelier.
5. Le système **propose** un nouveau planning.
6. L'humain **valide** avant application.

Ce positionnement est un choix délibéré et structurant. Il est supérieur au temps-réel autonome pour trois raisons :

- **Confiance industrielle** : aucune usine n'accepte qu'une IA réordonnance seule sa production. Le déclenchement humain lève cette objection.
- **Faisabilité** : on élimine la partie la plus lourde et la plus fragile du temps-réel (détection continue d'événements, décision automatique du moment de replanifier, gestion des courses critiques).
- **Protection de l'innovation** : le cœur du projet reste l'IA qui génère le solveur, au lieu d'être noyé sous une infrastructure temps-réel.

### 2.4 Contrainte technique fondamentale : la replanification sur atelier en cours

Quand l'humain déclenche un recalcul, l'atelier **tourne déjà**. Certaines opérations sont terminées, d'autres sont en cours (non interruptibles), d'autres n'ont pas commencé. Le solveur ne repart donc **jamais d'une page blanche** : il doit replanifier le reste en respectant l'état figé du présent.

Deux décisions liées à ce point ne sont **pas** des constantes du code, mais des **paramètres d'entrée décrits par l'entreprise** :

- **Périmètre de replanification** : refaire tout le planning restant, ou geler le maximum et ne déplacer que les tâches impactées ? Cela dépend de la méthode d'ordonnancement de l'entreprise.
- **Préemptibilité** : une opération en cours est-elle intouchable ou peut-elle être interrompue ? Cela dépend du type d'opération et des choix de l'entreprise.

C'est précisément parce que ces règles varient d'une entreprise à l'autre qu'elles doivent être **exprimées dans la description métier** (le DSL, voir §4) et non codées en dur.

### 2.5 Le curseur robustesse / originalité : génération encadrée par un DSL

Une tension centrale traverse le projet :

- Plus on **pré-écrit** des stratégies figées, plus le système est robuste, mais moins l'IA « génère » réellement — on retombe vers un outil paramétrable classique, exactement ce qu'on veut éviter.
- Plus on laisse l'IA **générer librement**, plus l'originalité est forte, mais plus la validation devient impossible à maîtriser.

**Position retenue : génération libre encadrée par un DSL.** L'entreprise s'exprime dans un vocabulaire métier structuré (le modèle T-R-C-O) ; l'IA traduit ce vocabulaire en code de solveur ; et parce que le vocabulaire est **fini et typé**, la sortie de l'IA reste validable. Le DSL est le **contrat entre le métier et la ressource** : il donne à la fois l'utilité (l'entreprise parle sa langue), l'originalité (l'IA génère réellement le code) et la fiabilité (la surface de génération est bornée et vérifiable).

---

## 3. Périmètre : le noyau minimal viable

La preuve du concept ne dépend **pas** du nombre de familles de contraintes couvertes. Elle dépend de la **boucle complète qui fonctionne de bout en bout** : description DSL → génération de code → exécution → validation → planning utile. Un système qui fait tourner cette boucle parfaitement sur un noyau restreint est plus convaincant qu'un système prétendant couvrir de nombreuses contraintes sans en maîtriser aucune.

### 3.1 Noyau retenu (dans le périmètre)

Le **socle FJSP** :

- **Précédence** entre opérations (l'opération A doit finir avant que B commence).
- **Compatibilité ressource-tâche** (chaque opération n'est exécutable que sur un sous-ensemble de ressources).
- **Durées** des opérations.

Ces trois familles forment le socle sur lequel tout le reste se greffe naturellement.

### 3.2 Extensions ultérieures (hors périmètre initial, architecture prévue pour les accueillir)

Identifiées comme réelles et importantes, mais volontairement différées pour ne pas diluer la preuve de concept :

- Temps de changement de série (setup) dépendants de la séquence — attention, fait basculer le problème vers une difficulté supérieure.
- Disponibilité et calendriers de ressources.
- Priorités clients et dates de livraison.
- Capacité (lots, stocks, files d'attente).

Le DSL et l'architecture sont conçus pour accueillir ces familles **sans refonte**, mais leur implémentation n'entre pas dans le socle initial.

---

## 4. Le modèle pivot T-R-C-O (le DSL)

Le DSL est la pièce d'ingénierie centrale dont dépend tout le reste. Il est organisé selon quatre axes métier :

- **T — Tâches** : les opérations à ordonnancer, leurs durées, leurs relations de précédence.
- **R — Ressources** : les ressource / postes, leurs compatibilités avec les tâches.
- **C — Contraintes** : les règles que le planning doit respecter (précédence, compatibilité, et plus tard préemptibilité, périmètre de replanification, etc.).
- **O — Objectifs** : ce que le planning doit optimiser (minimiser le makespan, équilibrer la charge, respecter les délais…).

### 4.1 Rôle du DSL dans l'architecture

Le DSL joue trois rôles simultanés :

1. **Format d'échange** : c'est la langue commune entre les ERP clients et le cœur de PRISME. Les données arrivent toujours en T-R-C-O canonique.
2. **Entrée de génération** : c'est à partir de la description T-R-C-O que l'IA génère le code du solveur.
3. **Cadre de validation** : parce que le vocabulaire est fini et typé, on peut vérifier que le code généré ne produit que des constructions appartenant à ce vocabulaire validé — ce qui réduit drastiquement la surface d'attaque et rend la validation possible.

### 4.2 Principe de conception : l'arbitrage d'expressivité

Le bon DSL couvre l'essentiel des besoins réels avec une complexité minimale :

- Trop pauvre, il ne capte pas les vraies contraintes des ateliers → outil-jouet.
- Trop riche, l'IA se perd, la validation explose, le projet ne se termine jamais.

Pour le noyau minimal, le DSL doit exprimer proprement précédence, compatibilité ressource-tâche et durées, avec des champs typés permettant une génération CP-SAT vérifiable.

---

## 5. Architecture retenue

### 5.1 Vue d'ensemble

```
                    ┌─────────────────────────────────────────────┐
                    │              ERP CLIENT (usine)              │
                    └───────────────────┬─────────────────────────┘
                                        │ format propriétaire
                                        ▼
                    ┌─────────────────────────────────────────────┐
                    │      ADAPTATEUR ERP (anti-corruption)        │
                    │   traduit le format propriétaire → T-R-C-O   │
                    └───────────────────┬─────────────────────────┘
                                        │ payload T-R-C-O canonique
                                        ▼
        ┌───────────────────────────────────────────────────────────────┐
        │                        API PRISME (cœur)                       │
        │                                                                │
        │  ┌──────────────────┐        ┌──────────────────────────────┐  │
        │  │  VALIDATION DES   │        │   STORE DE CODE (persistant) │  │
        │  │  DONNÉES D'ENTRÉE │        │  solveurs générés & validés  │  │
        │  └──────────────────┘        └──────────────┬───────────────┘  │
        │                                             │                  │
        │  ┌────────────────────────────────────┐     │ code figé        │
        │  │  BOUCLE DE GÉNÉRATION (hors ligne)  │     │                  │
        │  │  multi-agent generate-test-repair   │─────┘                  │
        │  │  bornée · diagnostique · humaine    │                       │
        │  │  si échec → alerte humain           │                       │
        │  └────────────────────────────────────┘                       │
        │                                             │                  │
        │                                             ▼                  │
        │                            ┌────────────────────────────────┐ │
        │                            │   BAC À SABLE (éphémère)        │ │
        │                            │  conteneur neuf par exécution   │ │
        │                            │  injecte code figé + données    │ │
        │                            │  → calcule le planning          │ │
        │                            └───────────────┬────────────────┘ │
        │                                            │                  │
        │                            ┌───────────────▼────────────────┐ │
        │                            │  GARDE-FOU DE FAISABILITÉ       │ │
        │                            │  vérifie le planning produit    │ │
        │                            └───────────────┬────────────────┘ │
        └────────────────────────────────────────────┼──────────────────┘
                                                      │
                        ┌─────────────────────────────┴──────────────┐
                        ▼                                             ▼
              ┌──────────────────┐                       ┌──────────────────────┐
              │  CANAL OPÉRATIONNEL │                     │   CANAL D'AUDIT       │
              │  planning JSON      │                     │  code du solveur      │
              │  (chaque itération) │                     │  (sur demande)        │
              └──────────────────┘                       └──────────────────────┘
```

### 5.2 Principe fondateur : le code persiste, l'exécution est éphémère

C'est la distinction architecturale la plus importante du projet, et elle est souvent mal comprise.

**Deux couches indépendantes :**

- **Le code du solveur est généré une seule fois et persiste.** Une fois qu'un solveur a passé la validation, il est stocké comme artefact durable et réexécuté sans nouvelle génération. C'est le principe fondateur du projet : générer une fois, réexécuter ensuite.
- **L'exécution est isolée et jetable.** À chaque itération, un conteneur neuf démarre, on y **injecte le code déjà généré** plus les données du moment, il calcule, rend le planning, puis meurt.

On obtient ainsi les deux avantages sans compromis : **le code n'est jamais régénéré** (exigence de performance respectée) et **l'exécution repart toujours d'un environnement propre** (exigence de sécurité respectée). Un bac à sable persistant accumulerait de l'état et des accès ouverts, et resterait compromis en cas d'attaque ; un conteneur éphémère repart propre à chaque fois.

### 5.3 Sécurité : l'exécution de code généré est le risque n°1

PRISME ne se contente pas de lire et écrire des données : il **génère du code et l'exécute**. Exécuter du code produit par une IA ouvre la porte la plus dangereuse de l'informatique — l'exécution de code arbitraire. Une description malveillante, une hallucination du modèle ou une injection dans le pipeline pourraient faire exécuter du code hostile sur le serveur, avec accès aux données des clients.

Réponses architecturales, par couches :

- **Isolation par bac à sable éphémère** (voir §5.2) : chaque exécution dans un conteneur jetable, aux privilèges et accès réseau restreints.
- **Validation statique avant exécution** : le code généré est inspecté avant d'être exécuté.
- **Réduction de la surface par le DSL** : puisque l'IA ne peut produire que des constructions issues d'un vocabulaire fini et validé, l'espace des codes générables est borné.

### 5.4 Communication avec les données externes : le client parle T-R-C-O

Modèle d'échange retenu : **adaptateur par ERP**. PRISME ne se connecte **pas** directement aux bases de données de production des clients. Chaque ERP dispose d'un adaptateur (couche anti-corruption) qui traduit son format propriétaire vers le T-R-C-O canonique. Le cœur de PRISME ne connaît que le T-R-C-O.

Avantages : découplage, sécurité (on ne touche jamais la BDD du client), et cohérence avec le DSL qui est déjà le format d'échange. **Un seul adaptateur réel** est construit pour la preuve de concept ; l'architecture démontre l'extensibilité aux autres ERP sans y consacrer l'effort d'implémentation de plusieurs connecteurs.

### 5.5 Sorties : deux canaux séparés

- **Canal opérationnel** : retourne le **planning en JSON**. C'est le cas d'usage normal, à chaque itération, celui que l'ERP consomme. Léger et rapide.
- **Canal d'audit** : sur demande explicite, expose le **code du solveur généré** pour inspection, validation par l'ingénieur du client, ou export (souveraineté, exécution sur site). Répond au besoin de transparence et de confiance.

Les deux besoins — usage courant rapide et transparence occasionnelle — sont ainsi servis sans être mélangés.

### 5.6 La boucle de génération multi-agent (generate-test-repair)

La génération du code n'est pas un tir unique : c'est une boucle où un agent testeur évalue le code produit, renvoie des recommandations à l'agent développeur, qui corrige, jusqu'à obtention d'un solveur valide. Cette boucle est encadrée par **trois garde-fous impératifs** :

1. **Bornée** : un nombre maximum de tentatives. Au-delà, le système s'arrête et **alerte l'humain** par un échec honnête (« je n'ai pas réussi à générer un solveur valide pour ce DSL »). Une boucle « jusqu'à satisfaction » sans borne pourrait ne jamais converger, ou tourner en rond entre deux erreurs.
2. **Hors ligne** : la boucle tourne au moment de la **génération** d'un solveur (événement rare : nouveau client, nouvelle structure de contraintes), **jamais à chaque exécution** de planning. Une fois validé, le solveur est figé.
3. **Diagnostique** : l'agent testeur ne dit pas « c'est faux, recommence », il indique **quelle contrainte est violée**. Sans diagnostic, la réparation se fait à l'aveugle et la convergence devient du hasard.

Ces trois conditions garantissent que la boucle sert l'architecture (génération unique, coût borné) au lieu de trahir le principe fondateur.

### 5.7 La boucle d'amélioration : diagnostiquer avant d'agir

Lorsqu'un planning est jugé mauvais (par des **KPI qui se dégradent** et/ou par un **signal humain** — les deux sources combinées), le système ne régénère pas le code au hasard. Il **attribue d'abord la cause** parmi trois coupables possibles, par élimination et dans un ordre précis :

1. **Test du code** sur les instances synthétiques à vérité terrain connue. S'il échoue là où la bonne réponse est connue → **le code est fautif** → régénération justifiée.
2. **Test des données** : le planning produit est-il faisable ? S'il est infaisable ou incohérent alors que le code est sain → **les données d'entrée sont corrompues** (durée négative, ressource inexistante…) → régénérer ne réparerait rien.
3. **Test de la spécification** : si le code est sain et les données propres mais que le résultat ne correspond pas à l'attendu → **la description DSL est fausse** (l'entreprise a mal décrit ses règles).

Confondre ces trois cas est fatal : une boucle qui « améliore » du code sain en réponse à des données pourries dégrade le système à chaque itération. Le système **diagnostique et propose une correction, mais l'humain décide d'agir**, en cohérence avec le fil directeur du projet.

---

## 6. Stratégie de validation et de test

On ne teste pas un système qui génère du code non déterministe comme on teste du code écrit à la main. Le système comporte **trois couches de nature différente**, chacune testée selon une philosophie propre.

### 6.1 Les trois couches à tester

- **Couche 1 — le code écrit à la main** (API, adaptateurs, orchestration) : déterministe. Tests unitaires et d'intégration classiques (paires entrée/sortie figées). Socle qui doit être solide pour que, en cas de bug ailleurs, on sache que ce n'est pas lui.
- **Couche 2 — le code généré par l'IA** (le solveur) : on ne peut pas écrire de test à l'avance puisqu'on ignore quel code sera produit. On ne teste pas *le code*, on teste **les propriétés du planning qu'il produit** (property-based testing).
- **Couche 3 — la génération elle-même** : non déterministe (le même DSL peut donner deux codes différents). Elle se teste **à travers** la couche 2, par les invariants de sortie et non par le texte du code.

### 6.2 Les trois briques de test de la couche 2 (par sévérité croissante)

1. **Vérificateur de faisabilité** — *le planning est-il légal ?* Aucune précédence violée, aucune ressource occupée deux fois, aucune tâche sur une ressource incompatible. Vérificateur écrit une seule fois, à la main, déterministe, applicable à n'importe quel planning. C'est le test le plus rentable : il attrape la grande majorité des erreurs de génération.
2. **Optimalité sur banc synthétique** — *le planning est-il bon ?* Sur des instances dont l'optimum est connu, on compare le résultat du solveur généré à l'optimum. Prouve que l'IA produit non seulement du code légal mais du code qui résout **bien** le problème.
3. **Fidélité sémantique** — *le planning résout-il le bon problème ?* Sur des cas de référence où le DSL et le planning attendu sont écrits à la main, on vérifie que la génération retombe dessus. C'est là que se cachent les erreurs les plus vicieuses (traduire « A avant B » en « B avant A » produit un planning faisable et optimal… pour le mauvais problème).

### 6.3 Ordre de construction des briques

**Faisabilité → banc synthétique → cas de référence.** Cet ordre n'est pas arbitraire :

- Le vérificateur de faisabilité est la fondation dont **toutes** les autres briques dépendent (le banc et les cas de référence l'appellent pour filtrer les plannings légaux). Il est le plus déterministe et le plus rentable → construit **en premier**.
- Le banc synthétique **consomme** le vérificateur et fournit la première mesure quantitative de qualité (le saut de la correction vers la performance) → **deuxième**.
- Les cas de référence sont les plus coûteux à fabriquer (chaque paire écrite à la main) et testent la couche la plus subtile, qui n'a de sens que lorsque les deux niveaux inférieurs sont fiables → **dernier**.

### 6.4 Le banc d'essai synthétique à vérité terrain

En l'absence de terrain industriel réel, la validation repose sur un **jeu d'instances synthétiques dont on connaît la vérité terrain parce qu'on les a fabriquées**.

Technique recommandée : la **construction inverse**. Plutôt que générer un problème puis chercher son optimum (coûteux, car le FJSP est NP-difficile — l'optimum d'une grande instance peut demander des heures), on **part d'un planning optimal choisi** et on construit l'instance autour de lui. L'optimum est ainsi connu par construction, gratuitement, même sur de grandes instances.

Un second niveau de validation, plus faible mais toujours utile, reste disponible même sans optimum connu : vérifier qu'un planning est **faisable** attrape déjà la majorité des erreurs de génération.

### 6.5 Test de stabilité de génération

Spécifique au non-déterminisme : générer le solveur pour le **même DSL** plusieurs fois, exécuter chaque version, et vérifier que les plannings produits sont équivalents (mêmes propriétés, même qualité). Fournit une métrique quantifiable pour le mémoire — **taux de générations valides sur N essais** — et révèle les problèmes de fiabilité qu'aucun autre test ne montre.

### 6.6 Distinction essentielle : tester le code vs tester le résultat d'exécution

- **Le code se teste une seule fois**, à la génération, via la boucle generate-test-repair. Une fois validé, il n'est **pas retesté à chaque exécution** — il n'a pas changé.
- **Le résultat d'exécution est déterministe** : un solveur figé, sur des données données, produit toujours le même planning. Sa qualité est donc déjà garantie par la validation du code.

### 6.7 Garde-fous déterministes en production

Le code est déterministe **pour des données valides**. En production arrivent les données réelles du client, qui peuvent être corrompues (durée négative, ressource inexistante, contraintes contradictoires). On conserve donc **deux garde-fous légers et déterministes** sur chaque exécution :

- **En amont** — validation des données d'entrée : le payload T-R-C-O est-il cohérent avant de lancer le solveur ?
- **En aval** — vérificateur de faisabilité : il repasse en une fraction de seconde sur le planning produit, non pour juger le code, mais pour attraper le cas où des données pathologiques auraient produit un résultat illégal.

Le vérificateur de faisabilité sert ainsi **deux fois** : hors ligne dans la validation du code, et en ligne comme garde-fou d'exécution. Une seule brique, deux usages — signe d'une architecture saine.

---

## 7. Contraintes structurantes à prendre en considération

- **Le FJSP est NP-difficile.** Le calcul d'optimum exact ne passe pas à l'échelle ; d'où le recours à la construction inverse pour disposer d'une vérité terrain, et l'acceptation de résultats à un écart mesuré de l'optimum plutôt qu'exacts.
- **L'exécution de code généré est le risque de sécurité dominant**, très au-dessus de l'authentification et du chiffrement classiques. Il conditionne le choix du sandboxing éphémère et de la validation statique.
- **Le paramétrage lourd ne disparaît pas, il se déplace vers la description DSL.** La valeur du système dépend entièrement de la **facilité du T-R-C-O en entrée** : s'il est aussi complexe à remplir que le paramétrage qu'il remplace, le gain s'évapore.
- **La difficulté réelle n'est pas d'écrire du code OR-Tools, mais de traduire fidèlement des contraintes métier floues en modèle mathématique correct.** L'agent de validation est donc le cœur du projet, pas un accessoire.
- **Le périmètre est le principal risque de dérive.** Vouloir couvrir toutes les familles de contraintes « pour être complet » condamne le projet. La preuve se fait sur un noyau restreint parfaitement maîtrisé.
- **Un seul adaptateur ERP et un seul secteur** sont implémentés ; l'extensibilité est démontrée par l'architecture, pas par la multiplication des connecteurs.
- **Absence de terrain industriel réel** au démarrage : la validation repose entièrement sur le banc synthétique. Cette contrainte **dicte** la stratégie (vérité terrain fabriquée) plutôt qu'elle ne la limite.
- **Fil directeur non négociable** : humain dans la boucle à chaque décision à risque (réordonnancement, diagnostic, échec de génération). Le système assiste, ne se substitue jamais.

---

## 8. Roadmap — logique des étapes

*Séquence logique de mise en œuvre. Les dépendances sont explicites : chaque étape s'appuie sur les précédentes.*

### Étape 1 — Fondations du DSL et du modèle canonique
Concevoir le DSL T-R-C-O pour le **noyau minimal** (précédence, compatibilité ressource-tâche, durées) : champs typés, schéma de validation. C'est la pièce dont tout le reste dépend — elle vient en premier.
> *Prérequis d'à peu près tout ce qui suit.*

### Étape 2 — Vérificateur de faisabilité
Écrire le vérificateur déterministe qui juge la légalité d'un planning. Première brique de test, la plus rentable, réutilisée partout ensuite (validation hors ligne **et** garde-fou en production).
> *Dépend de : la définition des contraintes (Étape 1).*

### Étape 3 — Banc d'essai synthétique à vérité terrain
Construire les instances par **construction inverse** (planning optimal choisi → instance bâtie autour). Fournit la vérité terrain pour toute la validation de qualité.
> *Dépend de : Étape 1 (structure des instances), Étape 2 (filtrage de faisabilité).*

### Étape 4 — Générateur de solveur (tir unique)
Mettre en place la traduction DSL → code CP-SAT par l'IA, en version simple (une génération, sans boucle). Objectif : obtenir un premier solveur qui compile et tourne sur une instance du noyau.
> *Dépend de : Étape 1 (entrée), s'évalue avec Étapes 2 et 3.*

### Étape 5 — Cascade de validation du code généré
Assembler les trois briques dans l'ordre : faisabilité → optimalité sur banc synthétique → fidélité sémantique (cas de référence). Ajouter le test de **stabilité de génération** (N essais sur le même DSL).
> *Dépend de : Étapes 2, 3, 4.*

### Étape 6 — Boucle multi-agent generate-test-repair
Transformer le tir unique (Étape 4) en boucle **bornée, hors ligne, diagnostique**, avec échec honnête vers l'humain à l'épuisement de la borne. La cascade de l'Étape 5 devient le testeur de la boucle.
> *Dépend de : Étapes 4 et 5.*

### Étape 7 — Store de code et exécution en bac à sable éphémère
Persister les solveurs validés comme artefacts ; mettre en place l'exécution en conteneur jetable (injection code figé + données, calcul, destruction). Ajouter la validation des données d'entrée et le garde-fou de faisabilité en aval.
> *Dépend de : Étape 6 (produit du code validé à stocker), Étape 2 (garde-fou).*

### Étape 8 — API et adaptateur ERP
Exposer l'API (réception T-R-C-O, déclenchement d'exécution, sorties). Construire **un** adaptateur ERP (couche anti-corruption) et démontrer l'extensibilité par l'interface. Mettre en place les deux canaux de sortie (planning JSON / code d'audit).
> *Dépend de : Étape 7 (cœur d'exécution à exposer), Étape 1 (format d'échange).*

### Étape 9 — Tableau de bord, alertes et boucle d'amélioration
Interface d'alerte et de déclenchement humain du réordonnancement ; validation humaine des plannings proposés ; boucle d'amélioration **diagnostique** (attribution de cause code / données / DSL) alimentée par KPI + signal humain, proposant des corrections sous décision humaine.
> *Dépend de : Étape 8 (API en place), et de la cascade de validation (Étape 5) réutilisée pour le diagnostic.*

---

## 9. Ce qui est décidé, ce qui reste à concevoir

**Décidé :**
- Positionnement : réordonnanceur réactif human-in-the-loop.
- Problème : FJSP, noyau à trois familles de contraintes.
- Contrat métier-ressource : DSL T-R-C-O.
- Architecture d'exécution : code persistant, sandbox éphémère, adaptateur ERP, deux canaux de sortie.
- Validation : boucle generate-test-repair bornée, hors ligne, diagnostique, avec échec honnête.
- Test : trois briques ordonnées + deux garde-fous déterministes en production + test de stabilité.

**À concevoir en priorité (prochain chantier) :**
- La **structure détaillée du DSL T-R-C-O** pour le noyau minimal : les champs typés de chaque axe (Tâches, Ressources, Contraintes, Objectifs) permettant à l'IA de générer un CP-SAT vérifiable. C'est l'Étape 1 de la roadmap et la fondation de tout le reste.

# PRISME — Plan de développement détaillé

*Découpage des phases en tickets et tâches concrètes*

**Plateforme de génération et d'exécution de solveurs d'ordonnancement pilotée par IA**
Projet de Fin d'Études — EIGSI Casablanca × BARAA Consult

---

## Préambule

Ce document décompose la roadmap de développement de PRISME en tickets opérationnels. Chaque phase est présentée avec son objectif, ses tickets numérotés (identifiant, titre, sous-tâches), et pour chacun une définition de « terminé » (*Definition of Done*) servant de critère de validation. La numérotation des tickets suit le format **PH\<phase\>-T\<numéro\>**, directement utilisable dans un outil de suivi (GitHub Issues, Jira, Trello).

Le principe directeur reste inchangé : **chaque brique déterministe et testable est construite avant toute brique IA.** On bâtit d'abord ce qui permet de *juger* le code généré (DSL, vérificateur, banc synthétique), puis seulement ce qui le *génère*. Le jalon de bascule est la Phase 5 : tant que la cascade de validation n'est pas fiable, aucune brique IA n'est abordée.

---

## Phase 0 — Cadrage technique et setup

**Semaine :** 1
**Objectif :** Disposer d'un socle projet reproductible et propre avant toute ligne de code métier.

### PH0-T1 · Initialiser le dépôt et la structure
- Créer le dépôt Git et la structure de projet à partir du squelette `src/ordo/` existant.
- Mettre en place la convention de branches (main protégée, branches de fonctionnalité).
- Rédiger un README initial décrivant l'arborescence et les commandes de base.

*Definition of Done — Le dépôt est cloné et sa structure est documentée dans le README.*

### PH0-T2 · Environnement Python reproductible
- Configurer la gestion de dépendances (uv ou Poetry) avec Python 3.11+.
- Fixer les versions des dépendances cœur : OR-Tools, Pydantic v2, FastAPI, pytest.
- Verrouiller le fichier de lock et documenter la procédure d'installation.

*Definition of Done — Un développeur reconstruit l'environnement complet par une seule commande.*

### PH0-T3 · Socle Docker Compose
- Écrire un `docker-compose` levant au minimum PostgreSQL avec un volume persistant.
- Prévoir les services vides mais nommés (api, worker, frontend) pour la suite.
- Documenter les variables d'environnement dans un fichier `.env.example`.

*Definition of Done — « docker compose up » lève PostgreSQL accessible et sain.*

### PH0-T4 · Intégration continue minimale
- Configurer un pipeline CI qui installe les dépendances et exécute pytest.
- Ajouter un linter/formatteur (ruff, black) exécuté en CI.
- Faire échouer la CI sur test rouge ou non-conformité de format.

*Definition of Done — Un commit déclenche la CI ; un test qui échoue bloque la fusion.*

---

## Phase 1 — Fondations du DSL T-R-C-O

**Semaines :** 2-3
**Objectif :** Modéliser le contrat métier-ressource (les quatre axes Tâches, Ressources, Contraintes, Objectifs) pour le noyau minimal, en champs typés et validables.

Le noyau minimal couvre trois familles seulement : **précédence**, **compatibilité ressource-tâche** et **durées**. Le DSL joue simultanément trois rôles : format d'échange, entrée de génération et cadre de validation.

### PH1-T1 · Modéliser l'axe T (Tâches)
- Définir le modèle Pydantic d'une tâche : identifiant, durée, opération.
- Modéliser les relations de précédence entre opérations.
- Interdire par typage les durées négatives ou nulles incohérentes.

*Definition of Done — Un ensemble de tâches avec précédences se charge et se sérialise en JSON.*

### PH1-T2 · Modéliser l'axe R (Ressources)
- Définir le modèle d'une ressource (ressource/poste) avec identifiant.
- Modéliser la compatibilité ressource-tâche (sous-ensemble de ressources par opération).
- Valider qu'une tâche ne référence que des ressources déclarées.

*Definition of Done — Une instance référençant une ressource inexistante est rejetée à la validation.*

### PH1-T3 · Modéliser les axes C (Contraintes) et O (Objectifs)
- Modéliser les contraintes du noyau (précédence, compatibilité) en structures typées.
- Modéliser les objectifs (ex. minimisation du makespan) de façon extensible.
- Prévoir l'ouverture aux familles futures sans refonte (setup, calendriers, priorités).

*Definition of Done — Le schéma exprime proprement le noyau et laisse la place aux extensions.*

### PH1-T4 · Schéma de validation et jeux d'exemples
- Assembler les quatre axes en un modèle T-R-C-O canonique unique.
- Constituer une bibliothèque de payloads valides (petites instances FJSP).
- Constituer une bibliothèque de payloads invalides couvrant chaque type d'erreur.

*Definition of Done — Les payloads valides passent, les invalides sont rejetés avec un message clair.*

---

## Phase 2 — Vérificateur de faisabilité

**Semaines :** 3-4
**Objectif :** Écrire la brique déterministe qui juge la légalité d'un planning. C'est la brique la plus rentable du projet : elle sert deux fois, en validation hors ligne et en garde-fou de production.

### PH2-T1 · Cœur du vérificateur
- Prendre en entrée une instance T-R-C-O et un planning proposé.
- Vérifier qu'aucune relation de précédence n'est violée.
- Vérifier qu'aucune ressource n'exécute deux opérations en chevauchement.
- Vérifier qu'aucune tâche n'est affectée à une ressource incompatible.

*Definition of Done — Le vérificateur rend un verdict légal/illégal sur tout planning du noyau.*

### PH2-T2 · Diagnostic des violations
- Retourner non pas un simple booléen mais la liste des violations constatées.
- Nommer précisément chaque violation (type, tâche/ressource concernée).
- Structurer la sortie pour réutilisation par la cascade de validation.

*Definition of Done — Un planning illégal produit un rapport nommant chaque contrainte violée.*

### PH2-T3 · Suite de tests exhaustive
- Couvrir par pytest chaque type de violation par au moins un cas dédié.
- Ajouter des plannings légaux de contrôle acceptés sans faux positif.
- Documenter le vérificateur comme dépendance socle des phases suivantes.

*Definition of Done — La suite de tests couvre tous les types de violation et passe au vert.*

---

## Phase 3 — Banc d'essai synthétique à vérité terrain

**Semaines :** 5-6
**Objectif :** Produire des instances dont l'optimum est connu par construction, afin de disposer d'une vérité terrain gratuite malgré la NP-difficulté du FJSP.

### PH3-T1 · Générateur par construction inverse
- Partir d'un planning optimal choisi et construire l'instance T-R-C-O autour.
- Garantir que l'optimum est connu par construction, sans calcul coûteux.
- Paramétrer la taille des instances (nombre de tâches, de ressource).

*Definition of Done — Le générateur produit une instance dont l'optimum est connu et documenté.*

### PH3-T2 · Catalogue d'instances versionné
- Générer un catalogue d'instances de tailles croissantes.
- Filtrer chaque optimum par le vérificateur de faisabilité (Phase 2).
- Versionner le catalogue pour reproductibilité des mesures.

*Definition of Done — N instances filtrées et versionnées sont disponibles avec leur optimum.*

### PH3-T3 · Second niveau de validation (faisabilité seule)
- Prévoir des instances sans optimum connu mais vérifiables en faisabilité.
- Documenter l'usage de ce niveau plus faible mais toujours utile.
- Intégrer ces instances au banc pour élargir la couverture.

*Definition of Done — Le banc propose deux niveaux : optimum connu et faisabilité seule.*

---

## Phase 4 — Solveur de référence écrit à la main

**Semaines :** 6-7
**Objectif :** Écrire soi-même un solveur CP-SAT du noyau, pour prouver que le problème est résoluble, calibrer les performances attendues et fournir un cas de référence à la fidélité sémantique.

### PH4-T1 · Modèle CP-SAT du noyau
- Traduire précédence, compatibilité et durées en modèle OR-Tools CP-SAT.
- Implémenter l'affectation ressource et le séquencement (couplage FJSP).
- Poser l'objectif de minimisation du makespan.

*Definition of Done — Le solveur manuel résout une instance du noyau et rend un planning.*

### PH4-T2 · Benchmark sur le banc synthétique
- Exécuter le solveur sur le catalogue de la Phase 3.
- Comparer les résultats aux optima connus (écart mesuré accepté).
- Consigner les temps de calcul par taille d'instance.

*Definition of Done — Le solveur retrouve l'optimum connu à l'écart mesuré près, temps consignés.*

### PH4-T3 · Cas de référence pour la fidélité sémantique
- Constituer des paires (DSL, planning attendu) écrites à la main.
- Inclure des pièges sémantiques (ex. sens de précédence A avant B).
- Réserver ces cas pour la brique de fidélité de la Phase 5.

*Definition of Done — Une bibliothèque de cas de référence sémantiques est disponible.*

---

## Phase 5 — Cascade de validation du code

**Semaine :** 8
**Objectif :** Assembler les trois briques de test par sévérité croissante et produire un verdict diagnostique. C'est le jalon de bascule : rien d'IA avant que cette cascade soit fiable.

### PH5-T1 · Brique 1 — faisabilité
- Intégrer le vérificateur de la Phase 2 comme premier filtre.
- Rendre un verdict de légalité sur le planning produit par un solveur donné.
- Structurer la sortie diagnostique (quelle contrainte échoue).

*Definition of Done — La cascade filtre tout planning illégal en nommant la violation.*

### PH5-T2 · Brique 2 — optimalité sur banc
- Comparer le résultat du solveur à l'optimum connu du banc (Phase 3).
- Mesurer l'écart à l'optimum comme métrique de qualité.
- Distinguer code légal mais médiocre de code légal et performant.

*Definition of Done — La cascade quantifie l'écart à l'optimum sur les instances du banc.*

### PH5-T3 · Brique 3 — fidélité sémantique
- Confronter la génération aux cas de référence (PH4-T3).
- Détecter les erreurs vicieuses (bon planning, mauvais problème).
- Rendre un verdict de fidélité au problème réellement décrit.

*Definition of Done — Un solveur inversant une précédence est détecté par la brique de fidélité.*

### PH5-T4 · Test de stabilité de génération
- Implémenter l'exécution répétée sur un même DSL (N essais).
- Comparer l'équivalence des plannings produits (propriétés, qualité).
- Exposer la métrique « taux de générations valides sur N essais ».

*Definition of Done — La cascade fournit une métrique de stabilité quantifiable pour le mémoire.*

---

## Phase 6 — Générateur en tir unique

**Semaines :** 9-10
**Objectif :** Premier contact avec l'IA : une seule génération DSL → code CP-SAT, sans boucle, jugée par la cascade de la Phase 5. On mesure le point de départ.

### PH6-T1 · Agent Générateur (tir unique)
- Concevoir le prompt de traduction T-R-C-O → code CP-SAT.
- Appeler le fournisseur LLM via une couche d'abstraction (indépendance fournisseur).
- Produire un solveur candidat pour une instance du noyau.

*Definition of Done — L'agent génère un solveur qui compile et s'exécute sur une instance.*

### PH6-T2 · Validation statique du code généré
- Analyser le code par le module `ast` avant toute exécution.
- Interdire imports dangereux, `eval`, accès réseau, accès fichier.
- Rejeter tout code sortant du vocabulaire attendu.

*Definition of Done — Un code contenant une construction interdite est bloqué avant exécution.*

### PH6-T3 · Mesure du taux de succès brut
- Exécuter plusieurs générations et les passer à la cascade (Phase 5).
- Consigner le taux de solveurs valides en tir unique.
- Établir la ligne de base à améliorer par la boucle (Phase 7).

*Definition of Done — Le taux de succès du tir unique est mesuré et documenté comme référence.*

---

## Phase 7 — Boucle multi-agent generate-test-repair

**Semaines :** 11-13
**Objectif :** Transformer le tir unique en boucle bornée, hors ligne et diagnostique. C'est le cœur innovant du projet.

La boucle est encadrée par trois garde-fous impératifs : **bornée** (nombre maximal de tentatives puis échec honnête vers l'humain), **hors ligne** (au moment de la génération, jamais à chaque exécution) et **diagnostique** (le testeur indique quelle contrainte est violée).

### PH7-T1 · Orchestration de la boucle
- Mettre en place le graphe d'états (LangGraph ou boucle maison) : générer → tester → réparer.
- Câbler la cascade de la Phase 5 comme testeur de la boucle.
- Assurer le passage du diagnostic du testeur vers le réparateur.

*Definition of Done — La boucle enchaîne génération, test et réparation sur un même DSL.*

### PH7-T2 · Garde-fou de bornage et échec honnête
- Fixer un nombre maximal de tentatives.
- À l'épuisement de la borne, arrêter et remonter un échec lisible vers l'humain.
- Journaliser les tentatives pour analyse de convergence.

*Definition of Done — À l'épuisement de la borne, le système remonte un échec propre et explicite.*

### PH7-T3 · Agent Réparateur diagnostique
- Consommer le diagnostic (contrainte violée) plutôt qu'un simple « faux ».
- Produire une correction ciblée du code fautif.
- Éviter les cycles improductifs entre deux erreurs récurrentes.

*Definition of Done — Le réparateur corrige à partir d'un diagnostic précis, pas à l'aveugle.*

### PH7-T4 · Mesure de convergence
- Comparer le taux de succès boucle vs tir unique (Phase 6).
- Produire la courbe de convergence et les statistiques associées.
- Consolider la métrique phare pour le mémoire.

*Definition of Done — Le gain de la boucle sur le tir unique est chiffré et illustré.*

---

## Phase 8 — Store de code et sandbox éphémère

**Semaines :** 13-15
**Objectif :** Persister les solveurs validés et exécuter le code figé en conteneur jetable. L'exécution de code généré est le risque de sécurité numéro un du projet.

### PH8-T1 · Store de code
- Persister les solveurs validés comme artefacts durables (PostgreSQL/artefacts).
- Associer à chaque solveur son DSL, sa version et ses métadonnées de validation.
- Permettre la récupération d'un solveur figé pour réexécution.

*Definition of Done — Un solveur validé est stocké puis récupéré à l'identique pour exécution.*

### PH8-T2 · Runner en conteneur éphémère
- Démarrer un conteneur Docker neuf par exécution.
- Injecter le code figé et les données, calculer, détruire le conteneur.
- Restreindre privilèges, réseau (coupé), limites CPU/mémoire, user non-root.

*Definition of Done — Chaque exécution repart d'un conteneur propre qui meurt après calcul.*

### PH8-T3 · Garde-fous d'exécution
- Valider les données d'entrée en amont (payload T-R-C-O cohérent).
- Repasser le planning produit au vérificateur de faisabilité en aval.
- Attraper les résultats illégaux issus de données pathologiques.

*Definition of Done — Données corrompues et plannings illégaux sont interceptés par les garde-fous.*

### PH8-T4 · Tests de sécurité
- Injecter un code malveillant de test et vérifier l'absence d'accès réseau.
- Vérifier l'impossibilité de sortir du conteneur ou d'accéder à l'hôte.
- Documenter le modèle de menace et les mesures d'isolation.

*Definition of Done — Un code hostile injecté ne peut ni sortir du conteneur ni atteindre le réseau.*

---

## Phase 9 — API et adaptateur ERP

**Semaines :** 15-17
**Objectif :** Exposer l'API du cœur, construire un adaptateur ERP anti-corruption et les deux canaux de sortie.

### PH9-T1 · API FastAPI du cœur
- Exposer la réception d'un payload T-R-C-O canonique.
- Exposer le déclenchement d'exécution d'un solveur validé.
- Documenter automatiquement l'API (OpenAPI).

*Definition of Done — L'API reçoit un T-R-C-O, déclenche l'exécution et renvoie une sortie.*

### PH9-T2 · Adaptateur ERP (anti-corruption)
- Définir l'interface abstraite d'adaptateur commune à tout ERP.
- Implémenter un adaptateur réel traduisant un format propriétaire → T-R-C-O.
- Démontrer l'extensibilité par l'interface, sans multiplier les connecteurs.

*Definition of Done — Un format propriétaire simulé est traduit en T-R-C-O canonique par l'adaptateur.*

### PH9-T3 · Deux canaux de sortie
- Canal opérationnel : renvoyer le planning en JSON à chaque itération.
- Canal d'audit : exposer le code du solveur sur demande explicite.
- Séparer proprement usage courant rapide et transparence occasionnelle.

*Definition of Done — Le planning JSON et le code d'audit sont accessibles par des canaux distincts.*

### PH9-T4 · Démonstration bout en bout
- Enchaîner adaptateur → API → exécution sandboxée → planning JSON.
- Exporter le code du solveur via le canal d'audit.
- Documenter le scénario de démonstration.

*Definition of Done — Une donnée propriétaire entre et ressort en planning JSON, code exportable.*

---

## Phase 10 — Tableau de bord et boucle d'amélioration

**Semaines :** 18-20
**Objectif :** Matérialiser le fil directeur human-in-the-loop : alerte, déclenchement humain, validation humaine, et boucle d'amélioration diagnostique.

### PH10-T1 · Interface d'alerte et de déclenchement
- Construire le frontend React/Vite avec visualisation du planning (Gantt).
- Afficher les alertes d'aléa (panne, commande urgente, retard).
- Permettre le déclenchement humain explicite du réordonnancement.

*Definition of Done — Un aléa lève une alerte et l'opérateur déclenche le recalcul depuis l'interface.*

### PH10-T2 · Validation humaine des plannings
- Présenter le planning proposé pour inspection.
- Permettre la validation humaine avant application.
- Tracer la décision humaine (accepté/refusé).

*Definition of Done — Aucun planning n'est appliqué sans validation humaine explicite.*

### PH10-T3 · Boucle d'amélioration diagnostique
- Attribuer la cause d'un mauvais planning : code, données ou spécification DSL.
- S'appuyer sur KPI dégradés et signal humain combinés.
- Proposer une correction, l'humain décidant de l'action.

*Definition of Done — Le système attribue la cause dans l'ordre code→données→DSL et propose sous décision humaine.*

### PH10-T4 · Cycle complet démontré
- Dérouler : aléa → alerte → déclenchement → recalcul → proposition → validation → application.
- Vérifier le respect du human-in-the-loop à chaque point sensible.
- Documenter le scénario de bout en bout.

*Definition of Done — Le cycle réactif complet tourne avec l'humain dans la boucle à chaque décision à risque.*

---

## Phase 11 — Consolidation, mémoire et soutenance

**Semaines :** 21-24
**Objectif :** Durcir, documenter et préparer la soutenance. Conserver une marge : elle disparaît toujours.

### PH11-T1 · Durcissement et tests d'intégration
- Réaliser des tests d'intégration bout en bout sur le système complet.
- Nettoyer le code, corriger les dettes techniques identifiées.
- Stabiliser la démonstration de soutenance.

*Definition of Done — Le système passe un test d'intégration complet de façon reproductible.*

### PH11-T2 · Rédaction du mémoire
- Consolider les métriques (taux de succès, convergence, stabilité).
- Rédiger l'argumentaire d'architecture et les choix structurants.
- Intégrer résultats et limites.

*Definition of Done — Le mémoire est rédigé, appuyé sur des métriques mesurées.*

### PH11-T3 · Préparation de la soutenance
- Préparer le support et le scénario de démonstration en direct.
- Anticiper les questions sur sécurité, validation et périmètre.
- Répéter la démonstration dans les conditions réelles.

*Definition of Done — La démonstration est répétée et robuste, le support est prêt.*

---

## Vue synthétique des phases

| Phase | Semaines | Livrable clé | Dépend de |
|---|---|---|---|
| 0 | 1 | Socle reproductible | — |
| 1 | 2-3 | Modèles Pydantic T-R-C-O | 0 |
| 2 | 3-4 | Vérificateur de faisabilité + tests | 1 |
| 3 | 5-6 | Instances à vérité terrain | 1, 2 |
| 4 | 6-7 | Solveur CP-SAT de référence | 3 |
| 5 | 8 | Cascade de validation complète | 2, 3, 4 |
| 6 | 9-10 | Générateur tir unique + validation statique | 1, 5 |
| 7 | 11-13 | Boucle generate-test-repair | 6, 5 |
| 8 | 13-15 | Store + sandbox Docker sécurisé | 7, 2 |
| 9 | 15-17 | API + adaptateur ERP + 2 canaux | 8, 1 |
| 10 | 18-20 | Dashboard + boucle d'amélioration | 9, 5 |
| 11 | 21-24 | Mémoire + soutenance | tout |

### Points de vigilance transverses

- **Jalon de bascule (Phase 5) :** aucune brique IA n'est abordée tant que la cascade de validation n'est pas fiable.
- **Chemin critique :** 1 → 2 → 3 → 5 → 7 → 8 → 9 → 10. Les phases 4 et 6 disposent d'un peu de marge ; les phases 7 et 10 sont les plus risquées en durée.
- **Ligne de coupe :** en cas de retard, les extensions de contraintes (setup, calendriers, priorités) sautent en premier, jamais le noyau. Un noyau minimal qui boucle de bout en bout vaut mieux qu'un système large qui ne converge nulle part.

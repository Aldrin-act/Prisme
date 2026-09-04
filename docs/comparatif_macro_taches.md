# Comparatif macro-tâches — plan directeur vs réalisé

Chaque cellule « périmètre prévu » est reprise mot pour mot du plan directeur original
(`docs/DJOUROBI_Aldrin_pFE_Promo2026_Plan_directeur.pdf`, section VII.1 « Work Breakdown
Structure — Macro-tâches », p. 22-24, complétée par la section IV.2.b « Objectifs opérationnels et
livrables », p. 12-14, pour les nuances de contenu) — plus une paraphrase. Chaque cellule
« périmètre réellement réalisé » a été vérifiée contre le dépôt (fichiers, `git log`) au
2026-08-27. Trois lignes (MT3, MT4, MT7) corrigent une version précédente qui décrivait un état
différent de ce qui existe réellement dans le code, ou omettait un volet du périmètre prévu — le
détail de chaque correction est donné sous le tableau.

| Réf. | Macro-tâche (plan directeur) | Périmètre prévu | Périmètre réellement réalisé | Nature de l'écart |
|---|---|---|---|---|
| MT1 | Cadrage et analyse du besoin | Entretiens, modélisation BPMN du pilote, analyse fonctionnelle, cahier des charges, choix d'architecture. | Exécuté conformément. Analyse fonctionnelle externe produite (bête à cornes, pieuvre, FAST) et périmètre arrêté en revue J1. | Conforme |
| MT2 | Compréhension et modèle pivot | Agent de parsing BPMN, extraction structurée, définition du modèle pivot, agent de formalisation. | Modèle pivot formalisé à quatre axes (Tâches, Ressources, Contraintes, Objectifs) avec schémas de validation croisée inter-axes ; compréhension BPMN requalifiée en adaptateurs d'entrée génériques (CSV/JSON/ERP) et agent de compréhension LLM — aucun parseur BPMN dédié. | Reformulé et approfondi (+1 semaine) |
| MT3 | Estimation des charges | Prédire la durée de chaque opération (estimation unitaire) **et** calculer la charge prévisionnelle par ressource sur l'horizon de planification (Objectif 3, p. 12) ; exploration des historiques, choix d'approche, entraînement/évaluation. | **Partiellement réalisé** — le volet estimation unitaire est fait (`estimation/`, `GradientBoostingRegressor`, `EstimateurDuree.estimer`), entraîné sur données synthétiques faute d'historique réel de volume suffisant. Le second volet explicitement prévu, la charge prévisionnelle *par ressource* sur l'horizon, n'existe nulle part dans le code — vérifié : `estimation/modele.py` ne produit que des `EstimationDuree` par couple (tâche, ressource), jamais un agrégat par ressource. | Partiel — durée conforme (réserve sur les données), charge prévisionnelle par ressource non réalisée |
| MT4 | Répartition des charges | Agent d'affectation tâche-ressource avant séquencement (algorithme hongrois), avec benchmark contre la répartition manuelle. | **Aucun agent dédié, à aucun degré** — vérifié par recherche exhaustive dans `generation/agents/` et `generation/graph.py` : zéro composant ne produit une affectation tâche-ressource avant ou en dehors du solveur. Le rôle est entièrement absorbé par le solveur généré, comme objectif paramétrable (`EquilibrerCharge`, `dsl/schema/objectifs_parametrables.py`), résolu conjointement au séquencement. | Reformulé — abandon délibéré de l'agent séparé (décision prise et assumée en cours de projet), pas une réduction partielle fusionnée avec MT5. |
| MT5 | Génération et validation de solveur | Agent de génération de code, agent de validation, sandbox, boucle de réparation. | Exécuté conformément, précédé d'un lot non prévu : banc d'instances à optimum prouvé et mécanisme de vérification de légalité par recensement des violations. | Étendu (lot ajouté) |
| MT6 | Exécution, équilibrage et benchmark | Module d'exécution, calcul des indicateurs, benchmark contre baseline manuelle et règles de priorité. | Module d'exécution livré (bac à sable Docker éphémère, Étape 7) ; indicateurs de planning produits (makespan, etc.). Le benchmark contre une baseline manuelle / règles de priorité n'a pas encore été réalisé. | **En cours — seul chantier concret encore réellement ouvert** |
| MT7 | Supervision et amélioration continue | Agent de détection des dérives et des goulots, propositions de régénération. | **Engagée et livrée sous forme reformulée**, vérifié via `git log` (commits du 2026-07-15 et du 2026-08-05, tous deux antérieurs à la date de ce tableau) : trois détecteurs déterministes (signature orpheline, instance à replanifier, échecs répétés — `supervision/detecteurs.py`), un agent LLM qui propose une action priorisée sans jamais agir seul (`supervision/agent.py`), une route API (`api/routes/supervision.py`) et une page frontend dédiée. | Reformulé — supervision consultative sur signaux opérationnels du pipeline, pas de détection proactive de dérive/goulot en cours d'exécution du planning (ce volet-là n'a pas été engagé). |
| MT8 | Mise à disposition par service (API) | Architecture du service, points d'entrée, authentification, documentation, conteneurisation. | Traitée par anticipation dès fin juillet, et étendue d'une interface web non prévue au plan. | Avancé et étendu |
| MT9 | Validation, portabilité et clôture | Démonstration pilote, documentation, rapport de stage, soutenance. | Engagée par anticipation mi-août pour la partie rédactionnelle. Démonstration pilote à venir. | Avancé, en cours |

## Détail des trois corrections

**MT2 — précision, pas une correction de fond.** Le plan directeur ne se contente pas de prévoir
un agent BPMN dans le WBS (MT2) : la compréhension BPMN est aussi une **fonction contrainte**
nommée du cahier de spécification fonctionnel (FC1, Tableau 2, p. 17) : *« Compréhension BPMN :
ingérer et interpréter des modèles BPMN 2.0 hétérogènes [...] Tout BPMN 2.0 standard est traduit en
représentation structurée. »* Cette contrainte précise-là n'est pas satisfaite au sens littéral —
aucun parseur BPMN 2.0 n'existe dans le dépôt. Ce qui a été construit à la place (adaptateurs
CSV/JSON/ERP génériques + agent de compréhension LLM) répond au besoin général sous-jacent
(ingérer des données hétérogènes sur le processus) mais pas à la contrainte technique telle
qu'énoncée mot pour mot — d'où « reformulé », et non « conforme ».

**MT3.** La version précédente qualifiait cette ligne de « Conforme » sans remarque. Le plan
directeur (Objectif 3, p. 12-13) demande explicitement deux livrables sous ce même intitulé :
l'estimation unitaire de durée *et* le calcul d'une charge prévisionnelle par ressource sur
l'horizon de planification — cette seconde moitié devait ensuite alimenter l'agent de répartition
(MT4) avant séquencement. Vérification faite dans `estimation/modele.py` et
`estimation/__init__.py` : le module ne calcule que des durées unitaires par couple
(tâche, ressource) ; aucune fonction n'agrège une charge prévisionnelle par ressource. Le volet
manquant n'a même pas été tenté, contrairement à MT4 où l'abandon de l'agent séparé était une
décision explicite — ici, c'est un manque silencieux qu'il vaut mieux nommer que laisser sous
« conforme ».

**MT4.** La version précédente de ce tableau affirmait qu'un agent d'affectation était
« conservé comme producteur de contraintes d'affectation candidates », l'arbitrage final revenant
au solveur — c'est-à-dire un agent existant sous forme réduite. Ce n'est pas le cas : aucune trace
d'un tel agent, à aucun stade du projet. Les seules occurrences du mot « affectation » dans
`generation/` concernent `comparer_affectation`, un paramètre de tolérance de la cascade de
validation (comparaison de l'affectation tâche→ressource lors du test de fidélité contre les cas de
référence), sans rapport avec un agent de répartition. Cette lecture rejoint le tableau déjà présent
dans `docs/contexte_general.md` (« Résolu nativement par le solveur généré »).

**MT7.** La version précédente affirmait que cette macro-tâche n'était « pas engagée » à la date
d'arrêté, avec seulement une collecte de journaux en place. Le module `supervision/` existe pourtant
bien, livré en deux temps (`3da3084`, 2026-07-15 ; `294790b`, 2026-08-05) — bien avant la date de ce
comparatif. La nuance correcte n'est pas « non démarrée » mais « reformulée » : le périmètre livré
détecte des anomalies opérationnelles du pipeline (signature orpheline, échecs répétés, instance
modifiée sans être ré-exécutée), jamais une dérive de planning ou un goulot d'exécution en temps
réel — c'est ce second volet, plus proche de l'intention initiale du plan directeur, qui reste non
engagé.

## Ce qui reste réellement à faire (vue plan directeur)

Sur les neuf macro-tâches du plan directeur, **deux** ont un écart concret encore ouvert et
actionnable :
- **MT3** — calculer une charge prévisionnelle par ressource sur l'horizon de planification (le
  volet du plan directeur jamais tenté, distinct de l'estimation unitaire de durée qui, elle, est
  faite).
- **MT6** — le benchmark du planning généré contre une baseline manuelle / règles de priorité
  (SPT/EDD, p. 22).

Tout le reste (MT2, MT4, MT7) correspond à des reformulations déjà tranchées et déjà livrées sous
leur nouvelle forme, pas à des manques à combler.

---

## Macro-tâches redéfinies à partir du réel

Le tableau ci-dessus part du plan directeur et corrige ce qui a changé — utile pour justifier les
écarts, mais sa numérotation (MT1–MT9) reste celle d'un document écrit avant la réalisation. Le
tableau suivant part dans l'autre sens : il redéfinit les macro-tâches directement à partir de ce
qui a été construit sur PRISME (mêmes dix lots que la Figure 3.4 — Diagramme WBS), avec un renvoi
vers l'ancienne numérotation pour la traçabilité. L'estimation de charge, qui n'était qu'une ligne
noyée dans un lot plus large du WBS, est ici remise en macro-tâche à part entière (MT6) — comme
elle l'était déjà dans le plan directeur.

### Justification du recadrage

Trois raisons factuelles motivent ce second découpage, plutôt qu'un simple ravalement du premier.

**1. Le plan directeur a été écrit avant la réalisation, sur des hypothèses qui n'ont pas
survécu au contact du problème réel.** Trois de ses macro-tâches supposaient un composant
technique précis — un parseur BPMN (MT2), un agent d'affectation par algorithme hongrois (MT4), un
agent de détection de dérive en cours d'exécution (MT7) — qui n'a jamais été construit sous cette
forme, pour des raisons techniques documentées à chaque fois (le pivot T-R-C-O rend un parseur BPMN
dédié inutile ; l'équilibrage de charge est nativement résolu par le solveur généré comme objectif
paramétrable ; la détection de dérive de planning en temps réel n'a pas été engagée, contrairement à
la supervision consultative sur signaux opérationnels qui, elle, l'a été). Continuer à présenter ces
trois macro-tâches sous leur intitulé d'origine oblige à qualifier la moitié du tableau de
« reformulé », ce qui finit par masquer la vraie structure du travail plutôt que l'éclairer.

**2. Une partie du travail réellement livré n'a tout simplement aucune case dans la numérotation
d'origine.** Le frontend (`Front/prismatron-solver-forge/`) est explicitement désigné dans
`CLAUDE.md` comme « Phase 10, hors de l'ordre de la roadmap » — il ne correspond à aucune des neuf
macro-tâches. Il en va de même pour l'intégration continue et l'environnement (pipeline CI, image
Docker, orchestration Postgres) et pour les tests, transversaux par nature : les forcer dans une
case existante (comme l'ancien tableau le faisait pour le frontend, rattaché à MT8 sous
« étendue d'une interface web non prévue au plan ») revient à leur donner un statut de sous-produit
alors qu'ils représentent chacun un volume de travail comparable aux autres macro-tâches.

**3. Une table ancrée sur le plan directeur est fragile à tenir honnête dans la durée — une table
ancrée sur le dépôt réel s'auto-vérifie.** Les deux corrections apportées plus haut (MT4, MT7)
existent précisément parce qu'une version antérieure de ce document avait dérivé de ce que dit le
code. Une macro-tâche nommée d'après un module qui existe réellement (`estimation/`,
`supervision/`, `sandbox/`...) se vérifie en une commande (`git log`, une recherche de fichier) ;
une macro-tâche nommée d'après une intention de 2026 qui n'a pas abouti ne se vérifie que par la
mémoire de qui l'a écrite.

Le premier tableau (plan directeur → réalisé) reste nécessaire : c'est lui qui rend compte de
l'engagement initial et de ses écarts, question à laquelle le second tableau ne répond pas. Les deux
sont complémentaires, pas redondants — le recadrage n'a pas vocation à remplacer la table
d'écarts, seulement à donner une vue organisée autour de ce qui existe, pour la partie du rapport où
c'est cette question-là qui est posée (architecture livrée, répartition du travail, WBS).

| Réf. | Macro-tâche (réelle) | Contenu réellement livré | Correspondance plan directeur | Statut |
|---|---|---|---|---|
| MT1 | Gestion du projet | Cadrage initial (EIGSI × BARAA Consult), Note de Cadrage, planification en 9 étapes (`CLAUDE.md` §8), suivi hebdomadaire tuteur/maître de stage, arbitrages de périmètre. | Volet gestion de l'ancien MT1. | Fait, continu |
| MT2 | Analyse des besoins et modélisation du problème | Étude du FJSP, analyse fonctionnelle (bête à cornes, pieuvre, FAST), cahier des charges abstrait (FP1–FP2/FC1–FC5), étude des contraintes métier réelles (GreenSIG), choix du vocabulaire pivot T-R-C-O. | Volet analyse de l'ancien MT1 + volet modèle pivot de l'ancien MT2 (hors BPMN). | Fait |
| MT3 | Conception du DSL et de l'architecture | Modèle Pydantic v2 à quatre axes (Tâches/Ressources/Contraintes/Objectifs, `dsl/schema/`), validation croisée inter-axes, conception du pipeline multi-agents LangGraph, de la boucle de réparation bornée, du bac à sable éphémère. | Formalisation du modèle pivot (ancien MT2) + conception de l'ancien MT5. | Fait |
| MT4 | Moteur de génération multi-agents | Générateur single-shot, agents Analyste/Benchmarker/Architecte/Développeur/Testeur/Debugger (`generation/agents/`), intégration multi-fournisseurs LLM, outils agents (recherche web, documentation de référence), mémoire intra-boucle du Debugger. | Volet génération de l'ancien MT5. | Fait, étendu au-delà du prévu (outils, mémoire) |
| MT5 | Validation et exécution sandboxée | Vérificateur de faisabilité, banc synthétique par construction inverse à optimum prouvé, cascade de validation (faisabilité/optimalité/fidélité), registre des solveurs, exécution Docker éphémère isolée (`solver_store/`, `sandbox/`). | Volet validation/sandbox de l'ancien MT5. | Fait, avec un lot non prévu au départ (banc synthétique) |
| MT6 | Estimation de charge | Module `estimation/` (`GradientBoostingRegressor`, scikit-learn) : estimation unitaire de durée par couple (tâche, ressource), entraîné sur données synthétiques faute d'historique réel de volume suffisant, intégré aux adaptateurs CSV/JSON avec avertissement explicite sur toute durée complétée par le modèle. La charge prévisionnelle par ressource sur l'horizon (prévue par l'ancien MT3) n'a pas été calculée. | Reprend l'ancien MT3 — partiellement, dans son intention. | Partiel — durée faite (réserve sur les données), charge prévisionnelle par ressource non réalisée |
| MT7 | API et adaptateurs | API REST FastAPI (auth JWT, multi-tenant), routes instances/exécution/planning/audit, adaptateurs ERP (CSV, JSON, GreenSIG), agent de compréhension (mapping LLM). | Ancien MT8 + volet ingestion de l'ancien MT2. | Fait, en avance sur le planning initial |
| MT8 | Frontend | TanStack Start/Vite, authentification et gestion des clients, génération de solveur en flux (SSE), suivi des exécutions et plannings, tableau de bord. | Absent du plan directeur initial — ajouté en cours de projet. | Fait |
| MT9 | Supervision | Trois détecteurs déterministes (signature orpheline, instance à replanifier, échecs répétés — `supervision/detecteurs.py`), agent LLM de proposition d'action jamais automatique (`supervision/agent.py`), route API, page frontend dédiée. | Ancien MT7 — reformulé (signaux opérationnels du pipeline, pas de détection de dérive de planning en temps réel). | Fait, sous forme reformulée |
| MT10 | Tests, qualité et intégration continue | Tests unitaires/intégration, test de stabilité de génération, mesure du taux de succès de génération, épreuve de sécurité du bac à sable, pipeline CI (lint/format/tests), image Docker, orchestration Postgres. | Transversal — jamais isolé comme macro-tâche dans le plan directeur original. | Fait, continu |
| MT11 | Documentation, benchmark et clôture | Documentation des agents et du pipeline, nomenclature du DSL, rédaction du rapport de stage, ressources mobilisées. Benchmark du planning généré contre une baseline manuelle/règles de priorité : non réalisé à ce jour. Démonstration pilote : à venir. | Ancien MT6 (volet benchmark, non réalisé) + ancien MT9 (validation, portabilité, clôture). | En cours — le volet benchmark reste le seul écart concret restant |

### Ce qui reste réellement à faire (vue redéfinie)

Même conclusion que dans la vue plan directeur, formulée sur la nouvelle numérotation : **MT6**
(charge prévisionnelle par ressource, jamais calculée) et **MT11** (benchmark contre une baseline
manuelle / règles de priorité) portent les deux seuls chantiers concrets encore ouverts. Toutes les
autres macro-tâches redéfinies sont livrées.

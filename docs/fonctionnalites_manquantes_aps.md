# Fonctionnalités manquantes face à un APS industriel

Analyse comparative : ce qu'il manquerait à PRISME pour être plus complet qu'un ERP/APS
(Advanced Planning and Scheduling) du commerce en termes de fonctionnalités. Vérifié contre le
code réel (pas une supposition générique sur les APS) — voir les fichiers cités pour chaque point.

## Modélisation (ce que le DSL ne peut même pas représenter)

- **Temps de changement de série (setup times)** — hors périmètre par design (CLAUDE.md le dit
  explicitement). Un vrai APS industriel les modélise presque toujours (changement d'outillage,
  nettoyage entre lots).
- **Matières premières / stock / nomenclature (BOM)** — absent à 100%. Le DSL T-R-C-O n'a que
  4 axes (Tâches/Ressources/Contraintes/Objectifs), aucun axe "matière" — un ordonnancement qui
  ignore une rupture de stock amont n'est pas réaliste pour un vrai atelier.
- **Multi-site** — `InstanceTRCO` est implicitement un seul site : pas de champ site/usine sur
  `Ressource`, pas de groupement.
- **Calendriers de ressources** — `ContrainteDisponibiliteRessource` n'est qu'une liste de jours
  indisponibles (`jours_indisponibles: list[int]`), pas de motif récurrent ("lun-ven 8h-17h"),
  granularité jour entier seulement, pas d'heures.

## Flux de travail du planificateur (ce qu'un utilisateur ne peut pas faire)

- **Scénarios comparatifs (what-if)** — absent : un `Planning` est une sortie unique jugée
  contre une seule instance, aucun concept de comparer 2-3 alternatives côte à côte avant de
  trancher.
- **Gantt interactif** — confirmé en lecture seule (`gantt-chart.tsx`, aucun handler de
  drag/clic sur une opération) — un planificateur ne peut pas ajuster manuellement puis
  revalider.
- **Horizon gelé / replanification glissante** — absent : pas de notion de "période proche
  figée, période lointaine replanifiable", un vrai APS l'a presque toujours pour éviter de
  perturber ce qui est déjà engagé.

## Intégration métier amont

- **Gestion de commandes/demande** — absent : `Tache` démarre déjà abstraite, aucun lien vers
  une commande client ou une prévision de demande.

## Ce que PRISME a déjà, qu'un APS classique n'a pas forcément

Agent de Supervision proactif (détecte et propose, jamais n'agit seul), connectivité
"n'importe quel ERP" via l'agent de compréhension LLM (prouvé par test réel), human-in-the-loop
structurel à chaque étape risquée — ce sont de vrais différenciateurs, pas juste des lacunes à
combler.

## Priorisation

**Setup times** et **horizon gelé/glissant** sont les deux qui bloquent le plus un usage
industriel réel — le reste (multi-site, BOM, what-if) touche plutôt l'ampleur du périmètre que
la crédibilité de ce qui existe déjà.

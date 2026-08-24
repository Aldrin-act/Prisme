# Estimation de charge par apprentissage supervisé

> **Statut : implémenté** (`estimation/`, voir `estimation/README.md`) — ce texte documentait à
> l'origine une évolution laissée hors périmètre (§3.3.2) ; il sert maintenant de justification de
> conception à l'implémentation réalisée, à réutiliser au chapitre « Réalisation » du rapport de
> stage plutôt qu'au chapitre « Perspectives ». Le chaînon manquant identifié ci-dessous (aucune
> durée réellement observée nulle part dans PRISME) reste, lui, non résolu : c'est pourquoi
> l'implémentation s'entraîne sur des données **synthétiques**, pas sur un historique réel — voir
> « Statut de l'implémentation » en fin de document.

## Rappel du choix actuel

Le plan directeur initial prévoyait un agent d'estimation par apprentissage supervisé
(`scikit-learn`/`XGBoost`) prédisant la durée de chaque opération à partir d'historiques
d'exécution (macro-tâche MT3). Ce choix a été reformulé en cours de projet (§3.3.2) : la durée
d'une opération reste aujourd'hui une donnée **déclarée** par le client ou **dérivée** de ses
compétences (`CompatibiliteRessourceTache.duree`, dérivation partagée dans
`adapters/competence_derivation.py`), jamais une prédiction d'un modèle entraîné. Cet abandon
n'est pas architectural — le DSL T-R-C-O n'exclut pas une source de durée différente — mais
pragmatique : un modèle fiable exige un historique suffisant par couple (type de tâche,
ressource), rarement disponible en l'état chez la cible visée (PME/ETI industrielle).

## Le chaînon manquant avant même le modèle

Un examen du schéma actuel montre qu'un obstacle précède la question du modèle lui-même :
`OperationPlanifiee` (`dsl/schema/planning.py`) ne porte que `tache`, `ressource` et `debut` — la
date de **début prévue**. Rien dans le modèle pivot ne capture aujourd'hui la **durée réellement
observée** une fois une opération exécutée sur le terrain. Le système produit des plannings, mais
ne referme pas la boucle vers le réel : il n'existe pas encore de mécanisme pour comparer un
planning prévisionnel à ce qui s'est effectivement passé.

Toute estimation par apprentissage suppose une vérité terrain (une durée observée à comparer à la
durée prédite) : sans ce chaînon, aucun historique exploitable ne peut se constituer, même après
des mois d'usage réel de PRISME chez un client. Cette capture serait donc, en toute rigueur, le
premier chantier à ouvrir — avant l'agent d'estimation lui-même — dans le droit fil du principe
méthodologique déjà suivi par le projet : construire ce qui *juge* avant ce qui *génère* (§1.9,
§3.2.2). Ici, juger un modèle de prédiction de durée nécessite d'abord de savoir mesurer son
erreur, ce qui suppose que la durée réelle existe quelque part dans le système.

## Comment l'implémentation s'intègre au système existant

L'estimation (`estimation/`) s'intègre sans redéfinir le système existant, exactement comme
envisagé ci-dessus :

- **Source de la durée, pas structure du DSL.** `CompatibiliteRessourceTache.duree` reste le seul
  porteur de durée du modèle pivot (§4.2.3) ; l'estimation ML en est une source de plus (déclarée →
  dérivée des compétences → **estimée**), au même niveau que les deux sources actuelles
  (`estimation/modele.py::vers_durees_estimees_par_tache` produit exactement la forme attendue par
  `adapters/competence_derivation.py::deriver_compatibilites_par_competence`) — `InstanceTRCO` et
  le solveur généré n'en savent rien.
- **Position dans le pipeline.** L'estimation prend place à la couche adaptateur/ingestion
  (`adapters/csv_import/traducteur.py`, `adapters/json_import/traducteur.py` — paramètre optionnel
  `estimateur_duree`), jamais au moment de l'exécution répétée du solveur figé — le principe
  fondateur *générer une fois, réexécuter plusieurs fois* (§1.6) reste intact.
- **Décision humaine préservée.** Conformément au principe transversal du projet (§1.6, FC4 de la
  Fig. 2.2), une durée estimée ne remplace jamais silencieusement une donnée déclarée : `traduire()`
  retourne désormais `ResultatTraduction(instance, avertissements)` plutôt qu'une `InstanceTRCO`
  nue, et chaque durée comblée par le modèle ajoute un avertissement explicite, visible par
  l'appelant (dashboard/API) — le système alerte et propose, il ne décide jamais seul.
- **Modèle et données.** Une régression supervisée (`GradientBoostingRegressor` scikit-learn —
  pas XGBoost, voir `estimation/README.md` pour la justification) sur des traits tâche/ressource
  (quantité, priorité, type de ressource, nombre de compétences) — pas la durée déjà déclarée
  comme trait d'entrée (elle n'existe justement pas dans le cas d'usage réel, combler une durée
  *manquante*).

## Limites et risques

- **Entraîné sur du synthétique, pas sur un historique réel.** `estimation/donnees_historique.py`
  dérive ses données d'entraînement du banc synthétique existant (Étape 3) plutôt que d'un
  historique client — voir « Le chaînon manquant » ci-dessus, toujours vrai : aucune donnée de
  durée réellement observée n'existe nulle part dans PRISME. La `confiance` rapportée par le modèle
  mesure un ajustement à ce synthétique, jamais une garantie sur des données réelles.
- **Démarrage à froid côté réel.** Une fois un historique réel disponible (une fois le chaînon
  manquant construit), un nouveau client n'en aurait, par construction, aucun le temps de quelques
  cycles d'exécution — repli sur la durée déclarée en attendant, déjà le comportement par défaut
  (`estimateur_duree=None`).
- **Dérive de contexte** : un changement de processus, d'équipement ou d'équipe rendrait un modèle
  entraîné sur un vrai historique obsolète sans qu'il le signale de lui-même — un ré-entraînement
  périodique et une surveillance de la qualité des prédictions resteraient nécessaires une fois du
  réel en jeu.
- **Auditabilité réduite** : contrairement à une durée déclarée ou dérivée des compétences,
  vérifiable par simple lecture, une durée estimée introduit une opacité que le reste de
  l'architecture s'est justement attaché à éviter (§5.3, §6) — d'où l'avertissement explicite
  plutôt qu'une fusion silencieuse dans la donnée déclarée.

## Statut de l'implémentation

Implémenté (`estimation/`), branché dans `csv_import`/`json_import`, testé
(`tests/unit/test_estimation.py`, `tests/unit/test_csv_import_adapter.py`,
`tests/unit/test_json_import_adapter.py`), démontrable (`uv run python -m
scripts.demo_estimation_charge`). Non fait, volontairement, et à traiter comme une perspective
distincte : le chaînon manquant lui-même (capture d'une durée réellement observée — `Planning`/
`OperationPlanifiee`, tables Postgres `operations_planifiees`), un registre de modèles persistés
par client, et tout entraînement sur un historique réel. Sans le premier de ces trois,
les deux autres n'ont pas de donnée à consommer — l'ordre de construction resterait le même que
celui déjà suivi par le projet (§1.9) : juger avant de générer, donc mesurer avant d'apprendre.

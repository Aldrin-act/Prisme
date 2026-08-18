# Perspective — Estimation de charge par apprentissage supervisé

> Destiné au chapitre « Perspectives » du rapport de stage (chapitre 9, renvoyé depuis §3.4 et
> §1.8 de `docs/contexte_general.md`). Ce texte décrit une évolution **non réalisée dans le cadre
> de ce PFE**, volontairement laissée hors périmètre (§3.3.2) — il ne modifie aucun code du dépôt.

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

## Ce qu'impliquerait l'ajout de cette brique

Si cette capture existait, l'estimation de charge s'intégrerait au système existant sans le
redéfinir :

- **Source de la durée, pas structure du DSL.** `CompatibiliteRessourceTache.duree` resterait le
  seul porteur de durée du modèle pivot (§4.2.3) ; l'estimation ML en deviendrait une source
  possible parmi d'autres (déclarée → dérivée des compétences → **estimée**), au même niveau que
  les deux sources actuelles, sans toucher à `InstanceTRCO` ni au solveur généré.
- **Position dans le pipeline.** L'estimation prendrait place en amont de la génération, au
  niveau de l'agent de compréhension (§3.3.1) — au moment où une instance T-R-C-O est construite à
  partir des données brutes du client — jamais au moment de l'exécution répétée du solveur figé,
  ce qui préserverait le principe fondateur *générer une fois, réexécuter plusieurs fois* (§1.6).
- **Décision humaine préservée.** Conformément au principe transversal du projet (§1.6, FC4 de la
  Fig. 2.2), une durée estimée par un modèle ne devrait jamais remplacer silencieusement une
  donnée déclarée : elle serait proposée avec une marque de provenance et un niveau de confiance
  explicites, à valider par un humain avant d'entrer dans l'instance — le système alerte et
  propose, il ne décide jamais seul.
- **Modèle et données.** Une régression supervisée (gradient boosting de type XGBoost, cohérent
  avec le choix initial) sur des variables tabulaires (type de tâche, ressource, compétences
  mobilisées, quantité/lot, éventuellement contexte temporel), entraînée sur l'historique propre à
  *chaque client* — un modèle par atelier, pas un modèle global, la structure des tâches variant
  trop d'un atelier à l'autre pour un apprentissage transférable.

## Limites et risques propres à cette évolution

- **Démarrage à froid** : un nouveau client n'a, par construction, aucun historique le temps de
  quelques cycles d'exécution — l'estimation ne pourrait s'activer qu'après une période de collecte,
  avec repli sur la durée déclarée en attendant.
- **Dérive de contexte** : un changement de processus, d'équipement ou d'équipe rend un modèle
  entraîné obsolète sans qu'il le signale de lui-même — un ré-entraînement périodique et une
  surveillance de la qualité des prédictions (au même titre que la cascade de validation surveille
  un solveur généré) seraient nécessaires.
- **Auditabilité réduite** : contrairement à une durée déclarée ou dérivée des compétences,
  vérifiable par simple lecture, une durée prédite introduit une opacité que le reste de
  l'architecture s'est justement attaché à éviter (§5.3, §6) — un argument supplémentaire pour la
  cantonner à une proposition explicitement marquée comme telle, jamais une vérité silencieuse.

## Pourquoi ce n'est pas un chantier retenu pour ce PFE

Le périmètre de la preuve de concept (§1.8) privilégie délibérément la démonstration bout en bout
de la boucle complète (description → génération → exécution → validation) plutôt que
l'exhaustivité des sources de données d'entrée. Ajouter l'estimation de charge sans disposer
d'abord d'un historique d'exécution réel reviendrait à entraîner un modèle sans vérité terrain —
un risque de fiabilité que le projet a précisément cherché à éviter en écartant cette voie dès le
cadrage (§3.3.2). Cette évolution reste donc une perspective cohérente avec l'architecture
existante, à ouvrir une fois PRISME en usage réel chez un ou plusieurs clients, et seulement après
qu'un mécanisme de capture du réel aura lui-même été construit et validé.

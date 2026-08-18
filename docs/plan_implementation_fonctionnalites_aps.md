# Plan d'implémentation — fonctionnalités manquantes face à un APS

Complète [`fonctionnalites_manquantes_aps.md`](fonctionnalites_manquantes_aps.md) : pour chacune
des 8 fonctionnalités listées, la conception concrète (comment l'ajouter), les fichiers touchés,
l'effort estimé et les risques. Organisé en 4 phases, de la moins invasive à la plus structurante.

## Comment lire ce plan

Chaque fonctionnalité est notée sur trois axes :
- **Effort** : 🟢 quelques jours · 🟡 1-2 semaines · 🔴 plusieurs semaines
- **Risque architectural** : à quel point ça bouscule des décisions déjà prises et documentées
  (CLAUDE.md, DSL, principe "generate once, re-execute many")
- **Dépendances** : ce qui doit exister avant

---

## Phase 1 — Gains rapides (aucun nouvel axe DSL, réutilise l'existant)

### Scénarios comparatifs (what-if)

✅ **Fait** · 🟢 Effort · 🟢 Risque · Aucune dépendance

Ne touche pas le DSL. Réutilise l'exécution/planning déjà existants.

- `groupe_scenario_id` sur `instances_trco` (FK auto-référencée, `ON DELETE SET NULL` —
  supprimer l'instance de base ne détruit jamais ses variantes, juste les orpheline de groupe).
  Distinct de l'ancien `instance_parente_id` (retiré) : celui-là suivait une modification en
  place (une seule lignée), ceci relie des variantes délibérées, créées pour coexister.
- `POST /ingestion/{instance_id}/scenarios` : crée une instance variante (payload T-R-C-O
  complet, même garde-fou §6.7), taguée au même groupe.
- `GET /ingestion/{instance_id}/scenarios/comparaison` : renvoie makespan, taux d'utilisation
  par ressource et tâches en retard (`api/comparaison_scenarios.py`) pour chaque instance du
  groupe, calculés sur sa **dernière exécution connue** — ne déclenche jamais d'exécution
  elle-même (§2.3, l'exécution reste une décision humaine explicite) ; une instance pas encore
  exécutée ressort avec `metriques: null`.
- 24 nouveaux tests (7 calcul de métriques, 7 route API, 4 `EtatPostgres` contre une vraie base),
  tous vérifiés avec Postgres réel, y compris le comportement `ON DELETE SET NULL`.

**Frontend fait** : nouvel onglet "Scénarios" sur le dialogue de détail d'instance
(`instances.tsx`) — tableau de comparaison (makespan, taux d'utilisation moyen, tâches en
retard, date d'exécution) + bouton "Créer un scénario" qui préremplit `IngestionDialog` à partir
de l'instance courante et poste vers `POST .../scenarios`. A révélé au passage une lacune
préexistante sans rapport avec cette fonctionnalité : aucun bouton "Nouvelle instance" n'existait
sur la page Instances, rendant tout le formulaire de création vierge (5 de ses 6 onglets, dont
Fichiers CSV) inatteignable — corrigé en même temps (bouton ajouté dans `PageHeader`, même
patron que "Modifier"/"Créer un scénario").

### Calendriers de ressources — motif récurrent

✅ **Fait** · 🟢 Effort · 🟢 Risque · Aucune dépendance

Additif pur sur `ContrainteDisponibiliteRessource` (`dsl/schema/contraintes.py`) :

```python
class ContrainteDisponibiliteRessource(BaseModel):
    ressource: Identifiant
    jours_indisponibles: list[int] = []
    jours_semaine_indisponibles: list[int] | None = None  # positions 0-6 d'un cycle de 7 jours
```

Implémenté avec la même polarité que le champ existant (indisponible, pas disponible) pour
rester cohérent — pas de notion de "lundi" calendaire (le DSL reste toujours relatif, jamais
une date), juste une position dans un cycle de 7 jours depuis le jour 0 de l'instance.

- `feasibility_checker.py` : matérialise le motif en jours concrets par modulo 7 sur toute la
  plage occupée, en plus de la liste explicite — les deux se combinent, y compris entre
  plusieurs `ContrainteDisponibiliteRessource` distinctes pour la même ressource (bug latent
  corrigé au passage : l'ancien code ne gardait que la dernière contrainte rencontrée par
  ressource au lieu de les fusionner).
- `generation/prompts/generation_solveur.md` : nouveau patron enseigné (matérialiser le motif
  sur l'horizon avant de fusionner avec `jours_indisponibles`), sinon les solveurs générés
  ignoreraient silencieusement ce nouveau champ.
- Rétrocompatible : les instances existantes (`jours_indisponibles` seul) continuent de
  fonctionner sans changement — 349 tests unitaires passent, 7 nouveaux ajoutés pour cette
  fonctionnalité.
- **Frontend fait** : `disponibilite_ressource` rejoint le sélecteur de type de contrainte du
  formulaire manuel (`ingestion-dialog.tsx`) — absent du picker jusque-là malgré son existence
  côté DSL. Les deux champs (`jours_indisponibles`/`jours_semaine_indisponibles`) se saisissent
  en entiers séparés par des virgules, parsés à la soumission — même convention que
  `competencesTexte` sur les ressources, pas de composant multi-valeurs dédié.

**Ne pas confondre avec** la granularité horaire (voir Phase 4) — ceci reste en jours entiers,
juste un motif au lieu d'une énumération.

### Gestion de commandes/demande — traçabilité, pas un nouvel axe solveur

✅ **Fait** · 🟢 Effort · 🟢 Risque · Aucune dépendance

Plutôt qu'un 5ᵉ axe DSL, une dérivation à la couche adaptateur (même patron que
`adapters/competence_derivation.py`) :

- `adapters/commande_derivation.py` : `Commande` (id, client, date_limite, tâches liées) — vit
  dans l'adaptateur, jamais dans `InstanceTRCO`. Dérive une `Echeance` par tâche liée (la plus
  contraignante si une tâche appartient à plusieurs commandes) ; une `Echeance` déjà explicite
  pour une tâche l'emporte toujours.
- Câblé dans `csv_import` (quatrième fichier optionnel `commandes.csv`) et `json_import` (champ
  optionnel `commandes`) — rétrocompatible, aucun appelant existant cassé.
- Traçabilité : la comparaison "quelle commande est en retard" se lit directement via les
  `taches_en_retard` de `GET /ingestion/{instance_id}/scenarios/comparaison` (phase 1 ci-dessus)
  — pas de mécanisme séparé nécessaire.
- 22 nouveaux tests (dérivation pure, csv_import, json_import, route API bout-en-bout).
- **Frontend fait** : 4ᵉ champ fichier optionnel "Commandes (.csv, optionnel)" sur l'onglet
  "Fichiers CSV" d'`ingestion-dialog.tsx`, en plus des 3 fichiers déjà requis — jamais inclus
  dans la condition `disabled` du bouton de soumission, cohérent avec son caractère optionnel
  côté backend. Scope volontairement limité à ce canal (route directe vers `adapters/csv_import`)
  — pas le flux CSV séparé de `donnees.tsx`, qui alimente `SourceDonnees`/l'agent de
  compréhension, un canal que ce backend ne touche pas.

**Pourquoi c'est le bon choix** : garde le vocabulaire DSL fini (§5.3) intact — la commande est
une métadonnée d'ingestion, pas une contrainte de plus à apprendre aux prompts de génération.

**Gap pré-existant noté au passage, pas corrigé ici** : `csv_import` n'a toujours pas de support
direct pour une `echeance` dans `contraintes.csv` (seulement via une commande) — un gap plus
basique que celui-ci, hors périmètre de cette fonctionnalité.

---

## Phase 2 — Priorité industrielle (les deux identifiés comme bloquants)

### Temps de changement de série (setup times)

✅ **Fait** · 🟡 Effort · 🟡 Risque · Dépend de : rien, mais **réouvre une décision documentée**

Nouveau type `ContrainteChangementSerie` (`ressource`, `tache_avant`, `tache_apres`,
`duree_setup`) — dirigé et propre à une ressource, sans effet tant que les deux tâches ne se
retrouvent pas consécutives sur cette ressource (`Precedence` garde seule le rôle d'imposer un
ordre).

1. `dsl/schema/contraintes.py` : `ContrainteChangementSerie` + validateur `_pas_d_autoreference`,
   ajouté à l'union `Contrainte`. `dsl/schema/instance.py` : vérifie que `ressource`/
   `tache_avant`/`tache_apres` référencent des entités déclarées (garde-fou §6.7).
2. `validation_engine/feasibility_checker.py` : nouvelle violation
   `changement_serie_insuffisant` — ne compare que les paires d'opérations **directement
   consécutives** sur une ressource (triées par `debut`), pas toute paire dans le même ordre.
3. `generation/prompts/generation_solveur.md` : patron CP-SAT enseigné — booléen d'ordre réifié
   (`ordre`) + `OnlyEnforceIf`, volontairement **conservateur** par rapport à la sémantique exacte
   du vérificateur (le délai s'applique dès que `tache_avant` précède `tache_apres` dans le
   temps sur la ressource, pas seulement si elles sont strictement adjacentes) — préféré à un
   séquençage exact par `AddCircuit` pour la fiabilité de génération LLM, documenté comme
   compromis délibéré directement dans le prompt. Patron symétrique pour un décodeur non-CP-SAT
   (dernière tâche placée + `duree_setup`).
4. `generation/prompts/architecte.md` : mention dans les deux branches (CP-SAT et
   décodeur/heuristique) — pas de changement à `benchmarker.md`, qui ne connaît pas le détail des
   contraintes, seulement la taille de l'instance.
5. **`CLAUDE.md`** : mention "hors périmètre par design" retirée, remplacée par une entrée dans
   la liste des extensions optionnelles.
6. 9 nouveaux tests (5 `test_dsl_schema.py`, 4 `test_feasibility_checker.py`), tous passants.
7. **Frontend fait** : nouveau type "Changement de série" dans le sélecteur de contrainte du
   formulaire manuel (`ingestion-dialog.tsx`) — champs ressource/avant/après/durée setup,
   réutilise les champs déjà existants (`ressource`/`avant`/`apres`/`duree`) plutôt que d'en
   ajouter de nouveaux, un seul type actif par ligne à la fois.

**Non fait, délibérément — pas un oubli** : pas de cas ajouté au banc synthétique
(`validation_engine/synthetic_bench/`) ni aux cas de référence
(`validation_engine/reference_cases/`). Ces deux bancs tournent contre **tout** solveur validé
par la boucle de réparation (`validation_engine/cascade.py::evaluer_cascade`, briques optimalité
et fidélité), y compris pour des instances qui ne contiennent aucun `ContrainteChangementSerie` —
un solveur est apparié par signature exacte de types de contraintes (Étape 8), donc rien ne
garantit qu'un solveur généré pour une instance sans changement de série sache l'encoder
correctement. Vérifié : **aucune** des six extensions optionnelles déjà existantes (`Echeance`,
`CompetenceRequise`, `ContrainteCapacite`, `ContrainteIncompatibilite`,
`ContrainteDisponibiliteRessource`, `ContrainteTailleLot`) n'apparaît dans l'un ou l'autre banc —
seulement dans les tests unitaires de `feasibility_checker.py`, comme fait ici. Ajouter un cas
changement de série y ferait exception et casserait potentiellement des générations sans rapport.

### Horizon gelé / replanification glissante

✅ **Fait** · 🔴 Effort · 🔴 Risque · Dépend de : rien, mais **touche le contrat public de `resoudre()`**

C'était le plus trompeur des 8 : ça a l'air d'un paramètre de plus, mais le principe fondateur
("generate once, re-execute many" — le **code** est figé, jamais le planning) veut dire que
c'est le contrat même du solveur généré qui a dû évoluer :

```python
def resoudre(
    instance: InstanceTRCO,
    planning_precedent: Planning | None = None,
    horizon_gele_jours: int = 0,
) -> Planning | None: ...
```

**Décision confirmée avec l'utilisateur avant implémentation** (seule fonctionnalité de ce plan à
avoir nécessité une confirmation séparée) : si `horizon_gele_jours > 0` est demandé mais que le
solveur enregistré ne supporte pas ces paramètres, l'exécution échoue **explicitement** — jamais
une dégradation silencieuse vers un solve normal, jamais une régénération automatique.

1. **Contrat** : `generation/prompts/generation_solveur.md` (nouvelle signature + section dédiée
   "Replanification à horizon glissant" — booléen d'ordre réifié + `Add(debut == valeur)` +
   littéral de présence forcé, patron décodeur non-CP-SAT symétrique), `architecte.md`
   (paragraphe cross-cutting avant la bifurcation cp_sat/heuristique), `developpeur.md`/
   `debugger.md`/`debugger_tests_sandbox.md` (exemples JSON incorporés mis à jour).
2. **Détection de compatibilité, sans jamais exécuter du code non fiable hors sandbox (§5.3)** :
   `sandbox/runner.py::_solveur_supporte_horizon_gele` — un simple `ast.parse` de
   `ArtefactSolveur.code_source` (déjà disponible, aucune nouvelle colonne de registre, aucune
   migration) pour vérifier si `resoudre` déclare les deux nouveaux paramètres. Fait côté hôte,
   avant de toucher Docker.
3. **Sandbox** : `sandbox/runner.py::executer_dans_sandbox`/`executer_solveur_valide` montent un
   `planning_precedent.json` optionnel et passent `horizon_gele_jours` en argv seulement quand
   `horizon_gele_jours > 0` — la commande/les volumes envoyés au conteneur restent strictement
   identiques à avant pour le cas par défaut. Le harnais
   (`sandbox/container/executer_dans_conteneur.py`) appelle `resoudre(instance)` exactement comme
   avant quand `horizon_gele_jours == 0` — c'est ce qui garantit qu'aucun des 9 solveurs déjà
   enregistrés n'a besoin d'être touché pour continuer à fonctionner normalement.
4. **État** : nouvelle méthode `dernier_planning_pour_instance(instance_id)` sur `EtatAPI` et
   `EtatPostgres` — ne considère que les exécutions *réussies*, la plus récente par date.
5. **API** (`api/routes/execution.py`) : `POST /execution/{instance_id}?horizon_gele_jours=N`
   (défaut 0) va chercher ce dernier planning et le transmet ; réponse enrichie de
   `horizon_gele_jours`/`planning_precedent_utilise` (transparence humaine — distingue "rien à
   figer" d'un vrai gel appliqué). Le cas incompatible traverse le canal existant
   `ResultatExecution.erreur`/`reussi=False`, jamais un nouveau code HTTP.
6. `scripts/_solveur_minimal.py` (dev/test fixture) étendu de façon additive avec une
   implémentation CP-SAT réelle du gel — permet de prouver le mécanisme bout-en-bout via le vrai
   sandbox Docker, pas seulement via la documentation du prompt.
7. 19 nouveaux tests : 6 unitaires (`_solveur_supporte_horizon_gele`), 6
   `dernier_planning_pour_instance` (3 `EtatAPI` + 3 `EtatPostgres`, réel), 4 sandbox (Docker
   réel — régression signature ancienne, rejet explicite, gel effectif de la ressource ET du
   début), 3 API bout en bout (Docker + Postgres réels), tous passants.
8. **Frontend fait** : champ numérique "Horizon gelé (jours, optionnel)" sur le dialogue
   d'exécution manuelle (`solvers.tsx`'s `DialogSolveur`, seul point d'entrée concerné — pas
   l'auto-exécution après ingestion, où il n'y a jamais d'historique à figer) ; message de
   transparence après exécution distinguant gel réellement appliqué (`planning_precedent_utilise`)
   de "rien à figer". `useDeclencherExecution`'s signature de mutation a changé (objet au lieu
   d'un `instanceId` nu) — répercuté sur ses 3 sites d'appel existants, aucun changement de
   comportement pour les deux qui n'utilisent pas ce paramètre.

**Non fait, délibérément — même politique que `ContrainteChangementSerie`** : pas de cas ajouté au
banc synthétique ni aux cas de référence (`validation_engine/cascade.py` appelle toujours
`solveur(cas.instance)` à un seul argument — chemin par défaut inchangé, mais le chemin figé
lui-même n'est testé que par les tests dédiés ci-dessus). Pas de régénération automatique des 9
solveurs existants — ils gagnent l'horizon gelé seulement s'ils sont un jour régénérés. Pas de
recalage calendaire entre deux instances différentes (`planning_precedent` vient toujours de la
même instance, même référentiel de jours relatifs par construction).

---

## Phase 3 — Expérience planificateur

### Gantt interactif

✅ **Fait** · 🟡 Effort · 🟢 Risque · Dépend de : rien (réutilise `verifier_faisabilite` tel quel)

Bon rapport effort/valeur confirmé : `validation_engine/feasibility_checker.py::verifier_faisabilite`
était déjà découplé du solveur — le planning modifié à la main est revalidé par la même fonction
déterministe, sans re-résoudre.

**Scope délibérément restreint** : le drag change uniquement le **jour de début** d'une
opération, à l'intérieur de sa propre ligne ressource — pas de réaffectation de ressource par
glisser-déposer inter-lignes (aurait demandé de re-résoudre `durees["tache|nouvelle_ressource"]`,
potentiellement inexistante, et une logique de drop-target bien plus lourde). Reste un axe
d'amélioration futur.

1. **Persistance** : nouvelle paire de tables `plannings_ajustes`/`operations_planifiees_ajustees`
   (`api/etat_postgres.py`), jamais l'original (`plannings.execution_id` a une contrainte
   `UNIQUE`, impossible d'y ajouter une deuxième ligne sans y toucher) — une seule révision
   "courante" par exécution, écrasée à chaque nouvel ajustement légal (jamais un historique de
   révisions). `enregistrer_planning_ajuste`/`recuperer_planning_ajuste` (même contrat sur
   `EtatAPI`/`EtatPostgres`) ; `supprimer_instance` purge la révision ajustée avec le reste de
   l'historique d'exécution, sur les deux implémentations.
2. **Deux nouvelles routes** (`api/routes/planning.py`) : `POST /{execution_id}/ajuster` (corps =
   `Planning` typé directement, Pydantic gère le 422 nativement) — `verifier_faisabilite`, puis
   **toujours 200** (`{legal, violations, planning}` — un refus métier n'est pas une erreur
   système, même convention que `ResultatExecution`/`POST /execution`) ; persiste seulement si
   légal. `GET /{execution_id}/ajuste` — `null` (jamais 404) si aucune révision n'existe encore.
3. **Frontend** (`gantt-chart.tsx`) : prop `editable`, drag via `onPointerDown`/`onPointerMove`/
   `onPointerUp` (`setPointerCapture`, pas de librairie — aucune dans `package.json`), délai
   pixel→jour figé au début du drag (évite les à-coups si le makespan bouge en cours de geste),
   clé stable `tache|ressource` par barre, surbrillance des barres modifiées, boutons Enregistrer/
   Réinitialiser affichés seulement si l'état local diverge de l'original. `schedules.tsx` et
   `solvers.tsx` affichent la révision ajustée par défaut si elle existe, avec une bascule
   "Voir l'original" non destructive (lecture seule dans ce sens, édition désactivée).
4. 9 nouveaux tests d'intégration (5 `test_api_planning.py` bout en bout, 4
   `enregistrer_planning_ajuste`/`recuperer_planning_ajuste` sur `EtatPostgres` — écrasement de
   révision, purge à la suppression d'instance) + 4 unitaires (`EtatAPI` équivalents), tous
   passants contre Postgres réel. Vérifié au navigateur : glisser une barre, tentative
   d'enregistrement illégale (chevauchement/précédence violée) correctement refusée avec le
   détail de la violation affiché, rien persisté (`planning: null`) — confirmé aussi par le test
   d'intégration du chemin légal (persistance + relecture via `GET .../ajuste`).

---

## Phase 4 — Structurant (nouveaux axes DSL, plusieurs semaines chacun)

### Matières premières / stock / nomenclature (BOM)

🔴 Effort · 🔴 Risque · Dépend de : rien, mais c'est le plus gros morceau

1. Nouvelle entité top-level `Materiau` sur `InstanceTRCO` (id, stock_initial, unité) — 5ᵉ axe,
   décision architecturale à documenter dans CLAUDE.md au même titre que T-R-C-O.
2. Nouveaux types de contrainte `ConsommationMatiere(tache, materiau, quantite)` et
   potentiellement `ProductionMatiere`.
3. `feasibility_checker.py` : la faisabilité devient **stateful dans le temps** — simulation
   chronologique du planning pour vérifier qu'aucun stock ne passe négatif. Rien de comparable
   n'existe aujourd'hui (tout y est local, par ressource/opération).
4. CP-SAT : `AddReservoirConstraint` (OR-Tools) — patron nouveau à enseigner aux prompts.
5. Tous les adaptateurs (`erp_reference`, `csv_import`, `json_import`, `greensig`) doivent
   apprendre à extraire cette nouvelle donnée si la source ERP la fournit.

### Multi-site

🟢 (mode étiquette) ou 🔴 (mode complet) · Dépend de : rien pour le mode étiquette

- **MVP recommandé** : `site: str | None` optionnel sur `Ressource`/`Tache`, jamais lu par le
  solveur — filtrage/regroupement au niveau Gantt et Analytique uniquement.
- **Mode complet** (coordination réelle inter-site) : redevient une variante du problème de
  changement de série (Phase 2) — temps de transfert entre sites, calendriers séparés. À ne
  faire qu'après Phase 2 si le besoin se confirme.

### Calendriers — granularité horaire

🔴 Effort · 🔴 Risque · **Migration inverse d'une décision déjà prise**

Le DSL est passé des minutes aux jours cette session même (voir mémoire projet). Revenir à
l'heure défait cette décision partout : `duree`/`echeance`/`debut` sur chaque contrainte
existante, tous les adaptateurs, tout le banc synthétique, tous les prompts de génération. Ne
pas entreprendre sans un besoin confirmé et un budget de migration explicite — c'est
l'équivalent d'un second passage complet sur tout ce que la migration jours a déjà traversé.

---

## Résumé — ordre recommandé

| # | Fonctionnalité | Statut | Effort | Risque | Phase |
|---|---|---|---|---|---|
| 1 | Scénarios comparatifs | ✅ Fait | 🟢 | 🟢 | 1 |
| 2 | Calendriers — motif récurrent | ✅ Fait | 🟢 | 🟢 | 1 |
| 3 | Gestion de commandes | ✅ Fait | 🟢 | 🟢 | 1 |
| 4 | Temps de changement de série | ✅ Fait | 🟡 | 🟡 | 2 |
| 5 | Horizon gelé / glissant | ✅ Fait | 🔴 | 🔴 | 2 |
| 6 | Gantt interactif | ✅ Fait | 🟡 | 🟢 | 3 |
| 7 | Multi-site (étiquette) | — | 🟢 | 🟢 | 4 |
| 8 | BOM / matières | — | 🔴 | 🔴 | 4 |
| 9 | Calendriers — granularité horaire | — | 🔴 | 🔴 | 4 |

**Phase 1 terminée** (3/3, backend) — 45 nouveaux tests au total entre les trois, tous vérifiés
réellement (Postgres réel pour les scénarios, route API bout-en-bout pour les commandes).

Phase 2 est la suite recommandée pour l'argument "crédible en industrie" du rapport — mais
**horizon gelé casse le contrat public de `resoudre()`** (voir plus haut) : à confirmer
explicitement avant de s'y engager, contrairement à la phase 1 qui était purement additive.

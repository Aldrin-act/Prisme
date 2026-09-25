/**
 * Types TypeScript pour l'API PRISME
 * Correspond aux modèles Pydantic du backend Python (FastAPI)
 */

// ============================================================================
// CLIENTS (tenants)
// ============================================================================

export interface Client {
  client_id: string;
  nom: string | null;
}

// ============================================================================
// MODÈLES DE BASE (DSL T-R-C-O)
// ============================================================================

export interface Tache {
  id: string;
  nom?: string;
  priorite?: number; // 1-5, informatif seulement
  produit?: string; // étiquette de regroupement produit/sous-produit, informatif seulement
}

export interface Ressource {
  id: string;
  nom?: string;
  competences: string[];
  // Durée de travail quotidienne, en heures (1 à 24) — optionnel. L'ingestion en dérive une
  // indisponibilité récurrente (le reste de chaque journée), uniquement pour un atelier en heures :
  // voir adapters/heures_travail.py.
  heures_par_jour?: number;
}

export type TypeContrainte =
  | "precedence"
  | "compatibilite_ressource_tache"
  | "echeance"
  | "competence_requise"
  | "changement_serie"
  | "disponibilite_ressource";

export interface ContraintePrecedence {
  type: "precedence";
  avant: string;
  apres: string;
}

export interface CompatibiliteRessourceTache {
  type: "compatibilite_ressource_tache";
  tache: string;
  ressource: string;
  duree: number; // jours, > 0 — seul endroit où la durée existe
}

export interface ContrainteEcheance {
  type: "echeance";
  tache: string;
  echeance: number; // >= 0
}

export interface CompetenceRequise {
  type: "competence_requise";
  tache: string;
  competence: string;
}

export interface ContrainteCapacite {
  type: "capacite";
  ressource: string;
  capacite: number; // >= 1 — nombre d'opérations simultanées supportées
}

export interface ContrainteDisponibiliteRessource {
  type: "disponibilite_ressource";
  ressource: string;
  jours_indisponibles: number[]; // jours relatifs, jamais une date calendaire
  // Motif récurrent (cycle de 7 jours depuis le jour 0 de l'instance) : positions 0-6 où la
  // ressource est indisponible chaque semaine. Combiné avec jours_indisponibles, jamais un
  // remplacement — au moins un des deux doit être renseigné (validé côté backend).
  jours_semaine_indisponibles?: number[];
}

export interface ContrainteChangementSerie {
  type: "changement_serie";
  ressource: string;
  tache_avant: string;
  tache_apres: string;
  duree_setup: number; // jours, > 0 — délai entre la fin de tache_avant et le début de tache_apres
}

export interface ContrainteIncompatibilite {
  type: "incompatibilite";
  tache: string;
  tache_incompatible: string;
}

export interface ContrainteTailleLot {
  type: "taille_lot";
  tache: string;
  lot_min: number;
  lot_max: number;
}

export type Contrainte =
  | ContraintePrecedence
  | CompatibiliteRessourceTache
  | ContrainteEcheance
  | CompetenceRequise
  | ContrainteCapacite
  | ContrainteDisponibiliteRessource
  | ContrainteIncompatibilite
  | ContrainteTailleLot
  | ContrainteChangementSerie;

export interface ObjectifMinimiserMakespan {
  type: "minimiser_makespan";
  poids?: number;
  makespan_cible?: number | null;
  penalite_depassement?: number;
}

export interface ObjectifEquilibrerCharge {
  type: "equilibrer_charge";
  poids?: number;
  methode?: "ecart_max" | "variance" | "gini";
  ressources_cibles?: string[] | null;
}

export interface ObjectifMinimiserRetards {
  type: "minimiser_retards";
  poids?: number;
  fonction_penalite?: "lineaire" | "quadratique" | "exponentielle";
  seuil_grace?: number;
}

export interface ObjectifMaximiserUtilisation {
  type: "maximiser_utilisation";
  poids?: number;
  ressources_prioritaires?: string[];
}

export interface ObjectifMinimiserChangements {
  type: "minimiser_changements";
  poids?: number;
}

export type TypeObjectif =
  | "minimiser_makespan"
  | "equilibrer_charge"
  | "minimiser_retards"
  | "maximiser_utilisation"
  | "minimiser_changements";

export type Objectif =
  | ObjectifMinimiserMakespan
  | ObjectifEquilibrerCharge
  | ObjectifMinimiserRetards
  | ObjectifMaximiserUtilisation
  | ObjectifMinimiserChangements;

export interface InstanceTRCO {
  taches: Tache[];
  ressources: Ressource[];
  contraintes: Contrainte[];
  objectifs: Objectif[];
  // Unité des entiers duree/echeance/debut/duree_setup de cette instance — "jours" par défaut
  // (absent = "jours", rétrocompatible). Affecte le cycle de disponibilite_ressource.
  // jours_semaine_indisponibles (7 en jours, 168 en heures) — voir dsl/schema/instance.py.
  unite_temps?: "jours" | "heures";
  // Jours de la semaine fermés par défaut (0=dimanche..6=samedi, convention Date.getDay() —
  // même convention ici et côté backend) — consommé uniquement par la correction post-solveur
  // (validation_engine/jours_non_ouvres.py), jamais par le solveur généré. Absent/omis = défaut
  // serveur (`[0, 6]`, samedi+dimanche) — voir dsl/schema/instance.py.
  jours_fermes?: number[];
}

// ============================================================================
// PLANNING & OPÉRATIONS
// ============================================================================

// Pas de champ `fin` ni `makespan` sur le fil — `dsl/schema/planning.py` ne
// les définit pas (volontairement permissif, voir ce module) : `fin` se
// déduit de `debut + durees["tache|ressource"]`, `makespan` du max des `fin`.
export interface OperationPlanifiee {
  tache: string;
  ressource: string;
  debut: number;
}

export interface Planning {
  operations: OperationPlanifiee[];
}

export interface PlanningAvecDurees extends Planning {
  durees: Record<string, number>; // Format: "tache|ressource" -> duree
  // Horodatage réel de l'exécution qui a produit ce planning (ISO-8601) — ancrage calendaire
  // stable du Gantt ("jour 0" = cette date, voir src/components/planning/gantt-chart.tsx),
  // jamais recalculé côté client. Une révision ajustée porte le même horodatage que l'original :
  // même exécution, pas une nouvelle date "au moment de l'ajustement".
  date_execution: string;
}

// Gantt interactif (Phase 3) : une contrainte violée par un planning ajusté à la main. `type`
// reste `string` plutôt qu'une union stricte dupliquée depuis
// `validation_engine/feasibility_checker.py::TypeViolation` (13 valeurs) — n'est jamais lu que
// pour affichage, jamais dans un switch exhaustif côté frontend.
export interface Violation {
  type: string;
  message: string;
  tache: string | null;
  ressource: string | null;
  tache_secondaire: string | null;
}

export interface ReponseAjustementPlanning {
  legal: boolean;
  violations: Violation[];
  // Absent (null) quand legal est faux — rien n'est persisté, et l'appelant garde son propre
  // état local (jamais écrasé) pour laisser l'utilisateur corriger et re-tenter.
  planning: PlanningAvecDurees | null;
}

// ============================================================================
// INGESTION
// ============================================================================

export interface ReponseIngestion {
  instance_id: string;
  structure_contraintes: string;
}

export interface InstanceDetail extends InstanceTRCO {
  instance_id: string;
  client_id: string;
  structure_contraintes: string;
  // Unité d'affichage des durées/échéances — "jours" implicite si `null`
  // (voir src/lib/unite-duree.ts). Purement cosmétique, jamais lu par le DSL.
  unite_duree: string | null;
  // Résumé en langage naturel de ce que fait l'atelier, proposé par l'agent de compréhension
  // (§5.4 bis) — `null` pour toute instance ingérée hors de ce chemin (payload T-R-C-O direct,
  // adaptateur écrit à la main...). Jamais lu par le DSL/solveur, purement informatif.
  description_metier: string | null;
}

// ============================================================================
// PROCESSUS D'ATELIER
// ============================================================================

// Une étape du processus unique d'un atelier — jamais vue par le solveur : chaque nouvelle
// commande en reçoit sa propre copie en tâches concrètes (voir api/routes/ingestion.py,
// POST /ingestion/{instance_id}/commandes). `predecesseurs` référence d'autres `id` d'étapes du
// même processus ; plusieurs prédécesseurs pour une étape = fusion. `duree_par_piece` est dans
// l'unité de temps de l'atelier : une commande de N pièces la multiplie par N.
export interface EtapeProcessus {
  id: string;
  nom: string | null;
  competences: string[];
  predecesseurs: string[];
  duree_par_piece: number;
}

// GET/PUT /ingestion/{instance_id}/processus — `etapes` vide tant qu'il n'a jamais été défini.
export interface ProcessusAtelier {
  etapes: EtapeProcessus[];
}

// ============================================================================
// COMMANDES
// ============================================================================

// Une commande éclate le processus de l'atelier (cas normal, `taches` absent) ou référence des
// tâches déjà présentes dans l'atelier (`taches`, import de données existantes) — jamais les deux.
// Dérive une Echeance commune à toutes ses tâches (api/routes/ingestion.py).
export interface RequeteNouvelleCommande {
  taches?: string[];
  // Durée propre à chaque tâche choisie, dans l'unité de l'instance (ex. { T1: 25, T2: 12 }) —
  // remplace la durée de la tâche sur toutes ses ressources compatibles, donc le planning en
  // tient compte. Une tâche absente garde ses durées actuelles.
  durees_taches?: Record<string, number>;
  // Nombre de pièces quand la commande éclate le processus de l'atelier (1 par défaut) : chaque
  // étape dure duree_par_piece × quantite. Ignoré pour une commande sur tâches existantes.
  quantite?: number;
  date_limite?: number;
  // Durée globale prévue pour la commande, saisie librement par l'utilisateur (heures) — pure
  // métadonnée de traçabilité, jamais dérivée en Echeance ni lue par le DSL/solveur.
  duree_heures?: number;
  // Métadonnées de traçabilité supplémentaires (même principe que duree_heures ci-dessus) :
  // numero est un libellé métier libre (ex. "P1"), distinct de commande_id (identifiant système,
  // jamais saisi) ; nom_client est le client *commercial* de la commande, sans rapport avec
  // client_id (le client PRISME propriétaire de l'instance).
  numero?: string;
  date_debut_au_plus_tot?: number;
  est_prospect?: boolean;
  description?: string;
  nom_client?: string;
}

export interface ResultatNouvelleCommande {
  instance_id: string;
  commande_id: string;
  // Tâches de la commande : créées par l'éclatement du processus, ou référencées telles quelles.
  taches: string[];
  structure_contraintes: string;
  // Avertissements de dérivation (§FC4) — ex. étape du processus ignorée parce qu'aucune
  // ressource de l'atelier ne sait la faire, jamais silencieux.
  avertissements: string[];
  // Exécution automatique déclenchée juste après l'ajout (best-effort, voir
  // api/routes/ingestion.py::ajouter_commande) — jamais de génération à la volée : execution_id
  // reste null et erreur_execution porte le motif (ex. "aucun solveur validé") si aucun solveur
  // ne correspond déjà à la structure résultante. L'ajout de la commande lui-même a toujours
  // réussi à ce stade, quel que soit le contenu de ces trois champs.
  execution_id: string | null;
  execution_reussie: boolean | null;
  erreur_execution: string | null;
}

// Une tâche de la commande positionnée dans le temps (début/fin résolus contre le dernier
// planning réussi) — de quoi tracer sa timeline. Absent tant que la commande n'est pas planifiee.
export interface OperationCommande {
  tache: string;
  debut: number;
  fin: number;
}

// GET /ingestion/commandes/{commande_id} — statut recalculé à la volée contre le dernier
// planning réussi de l'instance, jamais mis en cache.
export interface StatutCommande {
  commande_id: string;
  instance_id: string;
  // L'« atelier » d'une commande, c'est son instance (voir CLAUDE.md / api/routes/ingestion.py) —
  // client_id ajouté ici pour la vue transverse (GET /ingestion/commandes, tous ateliers), utile
  // à un admin qui voit plusieurs clients ; toujours son propre client_id pour un compte non-admin.
  client_id: string;
  date_limite: number | null;
  taches: string[];
  date_creation: string;
  // Durée globale prévue pour la commande, saisie librement par l'utilisateur (heures) — pure
  // métadonnée de traçabilité, jamais dérivée en Echeance ni lue par le DSL/solveur.
  duree_heures: number | null;
  // Métadonnées de traçabilité supplémentaires — voir RequeteNouvelleCommande ci-dessus.
  numero: string | null;
  date_debut_au_plus_tot: number | null;
  est_prospect: boolean;
  description: string | null;
  nom_client: string | null;
  // Nombre de pièces d'une commande éclatée depuis le processus de l'atelier (déjà appliqué aux
  // durées de ses tâches) — null pour une commande qui référence des tâches existantes.
  quantite: number | null;
  // Horodatage réel de la dernière exécution réussie de l'instance (même valeur que
  // PlanningAvecDurees.date_execution) — ancrage calendaire des jours relatifs de cette
  // commande (date_limite, operations[].debut/fin). `null` tant que l'instance n'a jamais été
  // exécutée avec succès (toujours le cas quand `planifiee` est faux) : le frontend retombe
  // alors sur une prévisualisation ancrée sur "aujourd'hui".
  date_execution: string | null;
  // Avancement réel dans l'atelier, DÉCLARÉ par un humain — à ne jamais confondre avec les
  // champs prévisionnels ci-dessous, calculés contre le planning. Une commande dont la fin
  // prévue est dépassée reste "non_debutee" tant que personne ne l'a confirmée : le système
  // ne déduit jamais une réalisation de l'écoulement du temps.
  statut_realisation: StatutRealisationCommande;
  // Horodatage de la déclaration "realisee" (ou date rétroactive saisie) — null pour tout
  // autre statut. C'est lui, comparé à date_limite, qui donne un vrai taux de service.
  date_realisation: string | null;
  planifiee: boolean;
  date_fin_prevue: number | null;
  en_retard: boolean | null;
  taches_manquantes: string[];
  operations: OperationCommande[];
}

export type StatutRealisationCommande = "non_debutee" | "en_cours" | "realisee";

export interface RequeteStatutCommande {
  statut: StatutRealisationCommande;
  // Déclaration rétroactive ("finie mardi dernier") — ignorée par l'API pour tout statut
  // autre que "realisee".
  date_realisation?: string | null;
}

// PRISME ne sait jamais qu'une tâche tourne en retard tout seul (aucun capteur ne remonte
// l'atelier en direct) — un humain corrige la durée réellement constatée sur la ressource sur
// laquelle la tâche tourne vraiment (jamais ses autres ressources compatibles, contrairement à
// `durees_taches` à la création d'une commande) — voir
// `api/routes/ingestion.py::declarer_retard_tache`. N'exécute rien : à l'appelant de relancer
// une exécution ensuite pour obtenir un planning qui en tient compte.
export interface RequeteRetardTache {
  ressource: string;
  nouvelle_duree: number;
}

// ============================================================================
// SCÉNARIOS COMPARATIFS
// ============================================================================

export interface MetriquesPlanning {
  makespan: number;
  taux_utilisation_par_ressource: Record<string, number>;
  taches_en_retard: string[];
}

export interface ScenarioComparaison {
  instance_id: string;
  est_instance_de_base: boolean;
  execution_id: string | null;
  date_execution: string | null;
  // null tant que ce scénario n'a jamais été exécuté avec succès — jamais déclenché
  // automatiquement par la simple lecture de la comparaison (§2.3).
  metriques: MetriquesPlanning | null;
  // Nombre de commandes en retard (calculer_statut_commande, même calcul que GET .../commandes
  // et le détecteur de supervision commande_en_retard) — pas les tâches individuelles en retard
  // (voir metriques.taches_en_retard). Même garde que metriques : null tant qu'aucune exécution
  // réussie n'existe, jamais 0 par défaut (0 signifierait à tort "vérifié, aucun retard").
  commandes_en_retard: number | null;
}

export interface ReponseComparaisonScenarios {
  instance_id: string;
  scenarios: ScenarioComparaison[];
}

// ============================================================================
// EXÉCUTION
// ============================================================================

export interface ReponseExecution {
  execution_id: string;
  reussi: boolean;
  erreur: string | null;
  // Replanification à horizon glissant (Phase 2) — horizon_gele_jours tel que demandé (0 =
  // aucun gel demandé) ; planning_precedent_utilise distingue "rien à figer" (aucun planning
  // précédent trouvé) d'un gel réellement appliqué, jamais silencieux.
  horizon_gele_jours: number;
  planning_precedent_utilise: boolean;
  // Voir PlanningAvecDurees.date_execution — même valeur, exposée ici aussi pour l'avoir
  // immédiatement après le déclenchement, sans attendre le premier GET /planning/{execution_id}.
  date_execution: string;
}

export interface ResultatExecution {
  reussi: boolean;
  planning: Planning | null;
  erreur: string | null;
}

// ============================================================================
// AUDIT
// ============================================================================

export interface CodeSource {
  id_solveur: string;
  code_source: string;
  // Choix de l'agent Benchmarker (ex. "tabu_search") + sa justification — `null` pour tout solveur
  // enregistré avant l'ajout de ces deux champs (voir solver_store/registry.py).
  algorithme: string | null;
  algorithme_raison: string | null;
}

// ============================================================================
// DIAGNOSTICS
// ============================================================================

export type CauseDiagnostic =
  "code_defectueux" | "donnees_corrompues" | "mauvaise_specification" | "inconnu";

export interface DiagnosticPayload {
  motif_declenchement: string;
}

export interface DiagnosticResultat {
  cause: CauseDiagnostic;
  motif_declenchement: string;
  details: string;
  proposition: string;
  humain_decide: boolean;
}

// ============================================================================
// SUPERVISION
// ============================================================================

export interface InstanceInfo {
  instance_id: string;
  client_id: string;
  structure_contraintes: string;
  executee: boolean;
  unite_duree: string | null;
  // Canal d'ingestion ayant produit cette instance — "manuel", "csv", "json",
  // "api", "agent_ia" ou "scenario". `null` pour toute instance enregistrée
  // avant l'ajout de ce champ — purement informatif, jamais lu par le solveur.
  canal_ingestion: string | null;
  // Résumé en langage naturel de l'atelier, proposé par l'agent de compréhension — `null` pour
  // toute instance ingérée hors de ce chemin (payload T-R-C-O direct, CSV, scénario...). Même
  // champ que `InstanceDetail.description_metier`.
  description_metier: string | null;
  // Instance de base du groupe de scénarios dont celle-ci est une variante — `null` si ce n'est
  // pas un scénario (y compris pour l'instance de base elle-même : voir
  // `api/etat.py::EtatAPI.lister_instances`, jamais sa propre clé dans `groupes_scenario`).
  groupe_scenario_id: string | null;
}

export interface ExecutionInfo {
  execution_id: string;
  id_solveur: string;
  // Toujours présent : une exécution appartient directement à son instance,
  // supprimer_instance cascade-supprime ses propres exécutions plutôt que de
  // les orpheliner (voir EtatAPI.supprimer_instance).
  instance_id: string;
  client_id: string;
  date_execution: string | null;
  reussi: boolean;
  erreur: string | null;
  // Décision humaine sur ce planning proposé (POST /executions/{id}/decision)
  // — null tant qu'aucune décision n'a été soumise, jamais automatique
  // (§ founding principle : human-in-the-loop non négociable).
  decision: "acceptee" | "refusee" | null;
}

export interface SolveurInfo {
  id: string;
  client_id: string;
  // Instance pour laquelle ce solveur a été généré — un solveur ne sert que celle-ci, jamais une
  // autre même de structure_contraintes/signature_objectifs identique. `null` pour un solveur
  // enregistré avant ce changement (orphelin, plus jamais proposé par /execution).
  instance_id: string | null;
  structure_contraintes: string;
  signature_objectifs: string;
  date_validation: string;
  empreinte_sha256: string;
  algorithme: string | null;
  algorithme_raison: string | null;
}

export interface Sante {
  api: boolean;
  sandbox_docker: boolean;
}

// --- Agent de supervision (MT7) --------------------------------------------
// Signaux détectés par du Python déterministe (supervision/detecteurs.py),
// habillés d'un résumé/priorité par un agent LLM (supervision/agent.py) —
// jamais appliqués automatiquement : `decision` reste null tant qu'un humain
// n'a pas accepté ou refusé via POST /supervision/propositions/{id}/decision.

export type TypeSignalSupervision =
  | "signature_orpheline"
  | "echecs_repetes"
  | "instance_a_replanifier"
  | "commande_en_retard"
  | "solveur_a_regenerer"
  | "instance_jugee_infaisable";

// Faut-il régénérer le solveur d'un atelier ? (POST /supervision/evaluer-solveur, voir
// supervision/adequation.py) — un constat argumenté par changement, jamais une règle mécanique.
// Seul un constat "bloquant" recommande de régénérer. Indication seulement, rien n'est lancé.
export type VerdictConstatSolveur = "bloquant" | "a_surveiller" | "sans_impact" | "non_verifie";

export interface ConstatSolveur {
  categorie: "contraintes" | "objectifs" | "algorithme" | "essai";
  sujet: string;
  verdict: VerdictConstatSolveur;
  argument: string;
  preuves: string[];
}

export interface EvaluationSolveurSupervision {
  instance_id: string;
  id_solveur: string;
  a_regenerer: boolean;
  raisons: string[];
  constats: ConstatSolveur[];
  contraintes_ajoutees: string[];
  contraintes_retirees: string[];
  objectifs_ajoutes: string[];
  objectifs_retires: string[];
  algorithme_utilise: string | null;
  algorithme_recommande: string | null;
  // Essai réel du solveur sur l'instance actuelle — null s'il n'a pas été lancé (contraintes
  // inchangées, ou bac à sable injoignable).
  essai: { reussi: boolean; erreur: string | null; nb_violations: number } | null;
}
// "aucune" : commande_en_retard — purement informatif, aucune route système déclenchée sur
// acceptation (voir api/routes/supervision.py::_dispatcher_action).
export type ActionSuggereeSupervision =
  "regenerer_solveur" | "executer" | "diagnostiquer" | "aucune";
export type PrioriteSupervision = "haute" | "moyenne" | "basse";

export interface PropositionSupervision {
  proposition_id: string;
  client_id: string;
  type_signal: TypeSignalSupervision;
  action_suggeree: ActionSuggereeSupervision;
  resume: string;
  priorite: PrioriteSupervision;
  details: string[];
  date_creation: string;
  instance_id: string | null;
  execution_ids: string[];
  structure_contraintes: string | null;
  signature_objectifs: string | null;
  decision: "acceptee" | "refusee" | null;
  horodatage_decision: string | null;
  commentaire: string | null;
  // Uniquement pour commande_en_retard — distingue plusieurs commandes en retard sur une même
  // instance.
  commande_id: string | null;
}

export interface RequeteAnalyseSupervision {
  client_id?: string;
  // Analyse d'un seul atelier : l'instance et le solveur de cet atelier à superviser.
  // `id_solveur` peut être omis pour un atelier qui n'a encore aucun solveur ; il exige toujours
  // `instance_id`. Sans `instance_id`, tous les ateliers sont analysés, l'un après l'autre.
  instance_id?: string;
  id_solveur?: string;
}

export interface RequeteDecisionProposition {
  decision: "acceptee" | "refusee";
  commentaire?: string;
}

// Au plus une des clés optionnelles ci-dessous est présente, selon `action_suggeree` de la
// proposition acceptée — aucune si `action_suggeree === "aucune"` (voir
// api/routes/supervision.py::_dispatcher_action).
export interface ReponseDecisionPropositionSupervision {
  proposition_id: string;
  decision: "acceptee" | "refusee";
  resultat?: {
    action: ActionSuggereeSupervision;
    job_id?: string;
    execution_id?: string;
    reussi?: boolean;
    cause?: string;
    proposition?: string;
  };
}

// ============================================================================
// VALIDATION
// ============================================================================

// Valeurs exactes attendues par POST /executions/{id}/decision
// (api/routes/validation.py, api/etat.py::Decision) — jamais "accepte"/"rejete".
export interface DecisionValidation {
  decision: "acceptee" | "refusee";
  commentaire?: string;
}

export interface ReponseValidation {
  execution_id: string;
  decision: "acceptee" | "refusee";
}

// ============================================================================
// ADAPTATEURS ERP
// ============================================================================

// Un adaptateur déterministe (ex. GreenSIG) n'attend aucun body : il lit sa
// source de données côté backend et renvoie directement une instance ingérée,
// à l'identique de POST /ingestion/{client_id}.
export type ReponseImportAdaptateur = ReponseIngestion;

// POST /adapters/csv/{client_id} renvoie aussi `avertissements` (ex. une
// durée comblée par estimation ML, §FC4) — absent de ReponseImportAdaptateur
// ci-dessus, qui reste inchangé pour ses autres appelants (tableur, adaptateur ERP).
export interface ReponseImportCsv extends ReponseIngestion {
  avertissements: string[];
  // Présente seulement si `genererDescription` a été demandé à l'import — best-effort, `null`
  // si non demandé ou si la génération a échoué (voir l'avertissement correspondant dans ce cas).
  description_metier: string | null;
}

export interface ReponseImportCsvLocal {
  instance_id: string;
  structure_contraintes: string;
  statistiques: {
    taches: number;
    ressources: number;
    contraintes: number;
    objectifs: number;
  };
  chemin_source: string;
}

// Agent de compréhension (LLM) : propose une traduction de données brutes
// (ERP sans adaptateur dédié) vers T-R-C-O, jamais une vérité — le même
// garde-fou déterministe que les autres canaux d'ingestion tranche derrière.
export interface Justification {
  contrainte: string;
  raison: string;
}

export interface ReponseComprehension {
  instance_id: string;
  structure_contraintes: string;
  // Résumé en langage naturel de ce que fait l'atelier, proposé par l'agent à partir des
  // données brutes — voir InstanceDetail.description_metier (même valeur, relue plus tard).
  description_metier: string;
  avertissements: string[];
  // Une entrée par contrainte precedence/echeance/competence_requise produite,
  // citant le champ des données brutes qui l'a justifiée (jamais pour
  // compatibilite_ressource_tache, trop nombreuses).
  justifications: Justification[];
}

// Conversion déterministe (sans agent LLM) d'une source déjà enregistrée —
// n'aboutit que si son texte brut est un JSON canonique ou un CSV
// Tâches/Ressources/Contraintes reconstituable (voir
// `POST /sources/{id}/generer-instance-deterministe`) ; pas d'avertissements
// ni de justifications, rien n'est interprété.
export interface ReponseConversionDeterministe {
  instance_id: string;
  structure_contraintes: string;
}

// Aperçu du prompt système + utilisateur réel qu'enverrait `genererInstanceDepuisSource` à
// l'agent de compréhension — construit sans jamais appeler le LLM (gratuit, voir
// GET /sources/{id}/prompt-comprehension), pour vérifier ce qui sera envoyé avant de
// déclencher une génération qui, elle, a un vrai coût en tokens.
export interface ApercuPromptComprehension {
  prompt_systeme: string;
  prompt_utilisateur: string;
}

// ============================================================================
// GÉNÉRATION DE SOLVEUR
// ============================================================================

// Pipeline multi-agents avec boucle de réparation bornée (jusqu'à 10
// tentatives) → cascade de validation → enregistrement
// (POST /generation/{instance_id} ou /stream, même résultat final).
export interface EchecCascade {
  nom: string;
  brique_en_echec: string | null;
  details: string[];
}

// Ce qui explique surtout la durée d'un appel au modèle (voir `MesureAppelLLM.cause_dominante`,
// generation/agents/client_llm.py) — `null` : appel court, rien à expliquer.
// `longueur` : réponse coupée à la limite de tokens de sortie — un échec, pas une lenteur.
export type CauseLatence = "reflexion" | "attente" | "refus" | "longueur" | null;

// Mesure d'un appel au modèle fait par un agent — miroir de `MesureAppelLLM.en_dict()`.
// `duree_s` couvre tout l'appel logique, attente d'une place et nouvelles tentatives comprises.
export interface MesureAppelLLM {
  reussi: boolean;
  duree_s: number;
  attente_file_s: number;
  tentatives: number;
  refus_429: number;
  modele: string | null;
  tokens_entree: number | null;
  tokens_sortie: number | null;
  tokens_reflexion: number | null;
  // `false` : le modèle a répondu, mais pas au format demandé — l'agent relance un appel.
  reponse_conforme: boolean | null;
  erreur: string | null;
  // Réponse coupée : le modèle a atteint sa limite de tokens de sortie avant d’avoir fini.
  limite_sortie_atteinte: boolean;
  cause: CauseLatence;
}

// Un évènement de progression par agent/sous-étape (POST /generation/{id}/stream,
// Server-Sent Events, event: "etape"). `statut: "mesure"` n'est pas un changement d'état de
// l'étape : c'est un appel au modèle fait par cet agent, décrit dans `details` — l'interface le
// rattache à la ligne de l'agent au lieu de la remplacer.
export interface EvenementGeneration {
  agent: string;
  statut: "en_cours" | "termine" | "echec" | "mesure";
  resume: string;
  details?: MesureAppelLLM | null;
}

export interface ReponseGenerationSolveur {
  reussi: boolean;
  id_solveur: string | null;
  structure_contraintes: string;
  signature_objectifs: string;
  // Algorithme recommandé par l'agent Benchmarker (toujours appelé,
  // generation/pipeline_avec_boucle.py) — connu même en cas d'échec, choisi
  // avant la boucle de réparation.
  algorithme: string;
  algorithme_raison: string;
  // Boucle de réparation bornée (generation/graph.py) : jusqu'à 10 tentatives,
  // Debugger corrigeant le code entre chaque essai (Reviewer désactivé).
  nombre_tentatives: number;
  erreur: string | null;
  echecs_cascade: EchecCascade[];
  // Dernier passage des tests générés par l'agent Testeur, réellement exécutés
  // en sandbox (§6.6bis) — `null` uniquement si le sandbox était indisponible.
  rapport_tests_sandbox: RapportTestsSandbox | null;
}

// Un job de génération connu du serveur (GET /generation/jobs) — pour savoir
// qu'une génération tourne en arrière-plan pour une instance sans dépendre
// du localStorage du navigateur qui l'a lancée (autre page, autre onglet...).
// `evenements`/`nombre_tentatives`/`cree_le` alimentent la page Analytique
// (statistiques réelles par agent) — mémoire process côté serveur, perdu au
// redémarrage du backend (voir api/routes/generation.py).
export interface JobGenerationInfo {
  job_id: string;
  instance_id: string;
  client_id: string;
  termine: boolean;
  reussi: boolean | null;
  nombre_tentatives: number | null;
  cree_le: string;
  evenements: EvenementGeneration[];
}

// KPI d'agrégat (GET /generation/statistiques) — calculés côté serveur depuis le stockage
// persisté (survit à un redémarrage, contrairement à JobGenerationInfo/mémoire process ci-
// dessus). `null` sur un champ = pas assez de données pour le calculer (aucune génération
// terminée, aucune tentative multiple à comparer...), jamais 0 par défaut trompeur. Miroir de
// `api/statistiques_generation.py::StatistiquesGeneration` — voir sa docstring pour ce qui
// n'est délibérément pas inclus (coût tokens, MTBF, CSAT...) et pourquoi.
export interface StatistiquesGeneration {
  generations_lancees: number;
  generations_terminees: number;
  taux_reussite: number | null;
  duree_moyenne_s: number | null;
  // Non-répétition (boucles) :
  tentatives_moyennes_convergence: number | null;
  taux_epuisement_boucle: number | null;
  taux_boucles_detectees: number | null;
  diversite_actions_moyenne: number | null;
  taux_stagnation: number | null;
}

// Historique complet et durable d'un job (GET /generation/jobs/{id}/historique),
// distinct de `JobGenerationInfo` (mémoire process, source du direct SSE) : celui-ci
// survit à un redémarrage du serveur et inclut le code candidat de chaque tentative
// de la boucle de réparation — y compris les rejetées, pas seulement le code final.
export interface EvenementGenerationHistorise {
  ordre: number;
  agent: string;
  statut: "en_cours" | "termine" | "echec" | "mesure";
  resume: string;
  details?: MesureAppelLLM | null;
}

export interface TentativeGenerationHistorisee {
  numero: number;
  code_candidat: string;
  reussi: boolean;
  erreur_execution: string | null;
  revue_approuve: boolean | null;
  revue_reponse_brute: string | null;
  revue_problemes: string[];
  validation_statique_valide: boolean | null;
  validation_statique_violations: string[];
}

export interface ResultatTestUnitaireSandbox {
  nom: string;
  reussi: boolean;
  message: string | null;
}

// Miroir de `sandbox.runner.RapportTestsSandbox.en_dict()` — canal d'audit des
// tests générés par l'agent Testeur, exécutés réellement dans le bac à sable
// Docker (§6.6bis) ; un échec renvoie déjà au Debugger côté pipeline, ceci
// n'est que la trace de ce qui s'est passé, pour lecture humaine.
export interface RapportTestsSandbox {
  tests: ResultatTestUnitaireSandbox[];
  erreur: string | null;
  reussi: boolean;
}

export interface HistoriqueJobGeneration {
  job_id: string;
  instance_id: string;
  client_id: string;
  cree_le: string;
  termine: boolean;
  reussi: boolean | null;
  id_solveur: string | null;
  specification: string | null;
  plan_technique: string | null;
  algorithme: string | null;
  algorithme_raison: string | null;
  algorithme_parametres: Record<string, unknown> | null;
  code_genere: string | null;
  tests_generes: string | null;
  code_final: string | null;
  rapport_tests_sandbox: RapportTestsSandbox | null;
  documentation: string | null;
  nombre_tentatives: number | null;
  erreur: string | null;
  termine_le: string | null;
  evenements: EvenementGenerationHistorise[];
  tentatives: TentativeGenerationHistorisee[];
}

// Sources de données : données brutes persistées + historique des instances
// générées à partir d'elles (une même donnée brute peut être reconvertie
// plusieurs fois, sans jamais devoir être re-saisie). Volontairement
// minimal : ni pointeur "instance courante" ni historique d'exécution —
// chaque instance générée s'exécute directement par son propre instance_id,
// indépendamment de la source qui l'a produite.
export interface SourceDonnees {
  source_id: string;
  client_id: string;
  nom: string | null;
  date_creation: string;
  nb_instances: number;
}

export interface InstanceDeSource {
  instance_id: string;
  structure_contraintes: string;
}

export interface SourceDetail extends SourceDonnees {
  donnees_brutes: string;
  // Objectifs déclarés avec les données : imposés à chaque instance générée depuis cette source,
  // à la place de ceux proposés par l'agent ou le fichier. Vide : rien n'est imposé.
  objectifs: Objectif[];
  instances: InstanceDeSource[];
}

export interface ReponseCreationSource {
  source_id: string;
}

// Extraction depuis une API HTTP quelconque (URL/authentification fournies à
// l'appel, jamais persistées côté serveur) — voir POST /sources/explorer-api.
// Un seul appel ; le corps de la réponse est renvoyé tel quel pour remplir le
// champ « Données brutes », pour relecture humaine avant tout enregistrement,
// jamais enregistré directement ici.
export type TypeAuthentificationAPI = "aucune" | "cle_api" | "porteur" | "basique";

export interface AuthentificationAPI {
  type: TypeAuthentificationAPI;
  en_tete?: string; // cle_api : nom de l'en-tête (ex. "X-API-Key")
  valeur?: string; // cle_api : valeur de la clé
  jeton?: string; // porteur : Authorization: Bearer <jeton>
  utilisateur?: string; // basique
  mot_de_passe?: string; // basique
}

export interface RequeteExplorationAPI {
  url: string;
  // Toujours GET depuis l'interface ; le serveur accepte encore POST pour un appelant direct.
  methode?: "GET" | "POST";
  authentification?: AuthentificationAPI;
  corps?: string; // POST uniquement
  en_tetes?: Record<string, string>;
  // Pagination par lots : absent, un seul appel est fait (une API paginée ne rend alors que sa
  // première page). Renseigné, le serveur réclame les pages les unes après les autres et
  // concatène leurs éléments en un seul tableau JSON.
  taille_lot?: number;
  lots_max?: number;
  param_taille?: string;
  param_decalage?: string;
}

export interface ReponseExplorationAPI {
  donnees_brutes: string;
}

// ============================================================================
// CLÉS API
// ============================================================================

export interface CleApi {
  cle_id: string;
  nom: string;
  prefixe: string;
  date_creation: string;
  derniere_utilisation: string | null;
}

// Le secret complet (`secret`) n'est renvoyé qu'une seule fois, à la création — jamais
// à nouveau via listerClesApi (voir CleApi ci-dessus, qui n'a que `prefixe`).
export interface ReponseCreationCleApi extends CleApi {
  secret: string;
}

// ============================================================================
// ERREURS API
// ============================================================================

// FastAPI/Pydantic renvoie soit une chaîne (erreurs métier explicites, ex.
// 503/502), soit le tableau standard de ValidationError.errors() sur 422,
// soit un objet {code, message} (toutes les erreurs d'authentification —
// voir api/routes/auth.py — pour que le frontend puisse distinguer les cas
// par code, ex. TOKEN_EXPIRED, sans parser le message humain).
export interface ErreurValidationChamp {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ErreurDetailCodee {
  code: string;
  message: string;
}

export interface ErreurAPI {
  detail: string | ErreurValidationChamp[] | ErreurDetailCodee;
  status?: number;
}

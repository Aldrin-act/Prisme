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
// SECTEUR D'ACTIVITÉ — vocabulaire fermé dupliqué à la main depuis
// api/etat.py::SecteurActivite (pas de pont codegen dans ce projet, même
// pratique déjà en place pour Contrainte/Objectif). Métadonnée opérationnelle
// (comme nom_projet), jamais lue par le solveur/DSL, mais avec trois effets
// réels : oriente le prompt de l'agent de compréhension, filtre les pages
// Instances/Données, alimente des suggestions de ressources à l'ingestion.
// ============================================================================

export type SecteurActivite =
  | "atelier_mecanique"
  | "assemblage_electronique"
  | "production_agroalimentaire"
  | "maintenance_industrielle"
  | "imprimerie"
  | "centre_appels";

export const LABELS_SECTEUR_ACTIVITE: Record<SecteurActivite, string> = {
  atelier_mecanique: "Atelier mécanique",
  assemblage_electronique: "Assemblage électronique",
  production_agroalimentaire: "Production agroalimentaire",
  maintenance_industrielle: "Maintenance industrielle",
  imprimerie: "Imprimerie",
  centre_appels: "Centre d'appels",
};

// ============================================================================
// MODÈLES DE BASE (DSL T-R-C-O)
// ============================================================================

export interface Tache {
  id: string;
  nom?: string;
  priorite?: number; // 1-5, informatif seulement
}

export interface Ressource {
  id: string;
  nom?: string;
  competences: string[];
}

export type TypeContrainte =
  "precedence" | "compatibilite_ressource_tache" | "echeance" | "competence_requise";

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
  | ContrainteTailleLot;

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
  // Étiquette libre pour retrouver/regrouper des instances liées (voir
  // InstanceInfo.nom_projet).
  nom_projet: string | null;
  // Un des 6 secteurs de SecteurActivite, ou un secteur personnalisé saisi
  // via "Autre" — jamais restreint au vocabulaire fermé côté stockage.
  secteur_activite: string | null;
}

// ============================================================================
// EXÉCUTION
// ============================================================================

export interface ReponseExecution {
  execution_id: string;
  reussi: boolean;
  erreur: string | null;
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
  // Étiquette libre choisie à l'ingestion pour retrouver/regrouper des
  // instances liées entre elles (réingestions successives d'un même
  // atelier), ou modifiée depuis lors via "Modifier".
  nom_projet: string | null;
  secteur_activite: string | null;
}

export interface NomProjetInfo {
  nom_projet: string;
  nb_instances: number;
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
  structure_contraintes: string;
  signature_objectifs: string;
  date_validation: string;
  empreinte_sha256: string;
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
  "signature_orpheline" | "echecs_repetes" | "instance_a_replanifier";
export type ActionSuggereeSupervision = "regenerer_solveur" | "executer" | "diagnostiquer";
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
}

export interface RequeteAnalyseSupervision {
  client_id?: string;
}

export interface RequeteDecisionProposition {
  decision: "acceptee" | "refusee";
  commentaire?: string;
}

// Exactement une des trois clés est présente, selon `action_suggeree` de la
// proposition acceptée (voir api/routes/supervision.py::_dispatcher_action).
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

// Un évènement de progression par agent/sous-étape (POST /generation/{id}/stream,
// Server-Sent Events, event: "etape").
export interface EvenementGeneration {
  agent: string;
  statut: "en_cours" | "termine" | "echec";
  resume: string;
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
  // Boucle de réparation bornée (generation/pipeline_avec_boucle.py) : 1 à 3
  // tentatives, Reviewer/Debugger corrigeant le code entre chaque essai.
  nombre_tentatives: number;
  erreur: string | null;
  echecs_cascade: EchecCascade[];
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

// Historique complet et durable d'un job (GET /generation/jobs/{id}/historique),
// distinct de `JobGenerationInfo` (mémoire process, source du direct SSE) : celui-ci
// survit à un redémarrage du serveur et inclut le code candidat de chaque tentative
// de la boucle de réparation — y compris les rejetées, pas seulement le code final.
export interface EvenementGenerationHistorise {
  ordre: number;
  agent: string;
  statut: "en_cours" | "termine" | "echec";
  resume: string;
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
  secteur_activite: string | null;
}

export interface InstanceDeSource {
  instance_id: string;
  structure_contraintes: string;
  nom_projet: string | null;
}

export interface SourceDetail extends SourceDonnees {
  donnees_brutes: string;
  instances: InstanceDeSource[];
}

export interface ReponseCreationSource {
  source_id: string;
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

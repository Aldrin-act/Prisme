/**
 * Types TypeScript pour l'API PRISME
 * Correspond aux modèles Pydantic du backend Python (FastAPI)
 */

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
  | 'precedence'
  | 'compatibilite_ressource_tache'
  | 'echeance'
  | 'competence_requise';

export interface ContraintePrecedence {
  type: 'precedence';
  avant: string;
  apres: string;
}

export interface CompatibiliteRessourceTache {
  type: 'compatibilite_ressource_tache';
  tache: string;
  ressource: string;
  duree: number; // minutes, > 0 — seul endroit où la durée existe
}

export interface ContrainteEcheance {
  type: 'echeance';
  tache: string;
  echeance: number; // >= 0
}

export interface CompetenceRequise {
  type: 'competence_requise';
  tache: string;
  competence: string;
}

export type Contrainte =
  | ContraintePrecedence
  | CompatibiliteRessourceTache
  | ContrainteEcheance
  | CompetenceRequise;

export interface ObjectifMinimiserMakespan {
  type: 'minimiser_makespan';
  poids?: number;
  makespan_cible?: number | null;
  penalite_depassement?: number;
}

export interface ObjectifEquilibrerCharge {
  type: 'equilibrer_charge';
  poids?: number;
  methode?: 'ecart_max' | 'variance' | 'gini';
  ressources_cibles?: string[] | null;
}

export interface ObjectifMinimiserRetards {
  type: 'minimiser_retards';
  poids?: number;
  fonction_penalite?: 'lineaire' | 'quadratique' | 'exponentielle';
  seuil_grace?: number;
}

export interface ObjectifMaximiserUtilisation {
  type: 'maximiser_utilisation';
  poids?: number;
  ressources_prioritaires?: string[];
}

export interface ObjectifMinimiserChangements {
  type: 'minimiser_changements';
  poids?: number;
}

export type TypeObjectif =
  | 'minimiser_makespan'
  | 'equilibrer_charge'
  | 'minimiser_retards'
  | 'maximiser_utilisation'
  | 'minimiser_changements';

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

export interface OperationPlanifiee {
  tache_id: string;
  ressource_id: string;
  debut: number;
  fin: number;
}

export interface Planning {
  operations: OperationPlanifiee[];
  makespan?: number;
}

export interface PlanningAvecDurees extends Planning {
  durees: Record<string, number>; // Format: "tache_id|ressource_id" -> duree
}

// ============================================================================
// INGESTION
// ============================================================================

export interface ReponseIngestion {
  instance_id: string;
  structure_contraintes: string;
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
  | 'code_defectueux'
  | 'donnees_corrompues'
  | 'mauvaise_specification'
  | 'inconnu';

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
}

export interface ExecutionInfo {
  execution_id: string;
  id_solveur: string;
  instance_id: string;
  date_execution: string;
  reussi: boolean;
  erreur: string | null;
}

export interface SolveurInfo {
  id: string;
  client_id: string;
  structure_contraintes: string;
  date_validation: string;
  empreinte_sha256: string;
}

export interface Sante {
  api: boolean;
  sandbox_docker: boolean;
}

// ============================================================================
// VALIDATION
// ============================================================================

export interface DecisionValidation {
  accepte: boolean;
  commentaire?: string;
}

export interface ReponseValidation {
  instance_id: string;
  decision: 'accepte' | 'rejete';
  commentaire?: string;
}

// ============================================================================
// ADAPTATEURS ERP
// ============================================================================

// Un adaptateur déterministe (ex. GreenSIG) n'attend aucun body : il lit sa
// source de données côté backend et renvoie directement une instance ingérée,
// à l'identique de POST /ingestion/{client_id}.
export type ReponseImportAdaptateur = ReponseIngestion;

// Agent de compréhension (LLM) : propose une traduction de données brutes
// (ERP sans adaptateur dédié) vers T-R-C-O, jamais une vérité — le même
// garde-fou déterministe que les autres canaux d'ingestion tranche derrière.
export interface ReponseComprehension {
  instance_id: string;
  structure_contraintes: string;
  avertissements: string[];
}

// Projets : données brutes persistées + historique des instances générées
// à partir d'elles (une même donnée brute peut être reconvertie plusieurs
// fois, sans jamais devoir être re-saisie).
export interface Projet {
  projet_id: string;
  client_id: string;
  nom: string | null;
  date_creation: string;
  nb_instances: number;
}

export interface InstanceDeProjet {
  instance_id: string;
  structure_contraintes: string;
}

export interface ProjetDetail {
  projet_id: string;
  client_id: string;
  nom: string | null;
  donnees_brutes: string;
  date_creation: string;
  instances: InstanceDeProjet[];
}

export interface ReponseCreationProjet {
  projet_id: string;
}

// ============================================================================
// ERREURS API
// ============================================================================

// FastAPI/Pydantic renvoie soit une chaîne (erreurs métier explicites, ex.
// 503/502), soit le tableau standard de ValidationError.errors() sur 422.
export interface ErreurValidationChamp {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ErreurAPI {
  detail: string | ErreurValidationChamp[];
  status?: number;
}

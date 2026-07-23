/**
 * Client API PRISME - Fonctions d'appel à l'API FastAPI
 */

import { PRISME_CONFIG } from './config';
import type * as Types from './types';

// ============================================================================
// ERREURS
// ============================================================================

export class PrismeAPIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public detail?: string | Types.ErreurValidationChamp[]
  ) {
    super(message);
    this.name = 'PrismeAPIError';
  }

  /** Erreurs de validation par champ (422), vide si `detail` est une simple chaîne. */
  get champs(): Types.ErreurValidationChamp[] {
    return Array.isArray(this.detail) ? this.detail : [];
  }
}

// ============================================================================
// FETCH WRAPPER
// ============================================================================

async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  timeoutMs = PRISME_CONFIG.timeout
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    // FormData (upload de fichier) : laisser le navigateur poser son propre
    // Content-Type (avec la boundary multipart) plutôt que forcer JSON.
    const estFormData = options?.body instanceof FormData;
    const response = await fetch(`${PRISME_CONFIG.baseURL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        ...(estFormData ? { Accept: PRISME_CONFIG.headers.Accept } : PRISME_CONFIG.headers),
        ...options?.headers,
      },
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      let errorDetail: string | Types.ErreurValidationChamp[];
      try {
        const errorData: Types.ErreurAPI = await response.json();
        errorDetail = errorData.detail;
      } catch {
        errorDetail = response.statusText;
      }
      const message = Array.isArray(errorDetail)
        ? errorDetail.map((e) => `${e.loc.join('.')} : ${e.msg}`).join(' ; ')
        : errorDetail;
      throw new PrismeAPIError(`Erreur API: ${message}`, response.status, errorDetail);
    }

    return response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof PrismeAPIError) throw error;
    if (error instanceof Error && error.name === 'AbortError') {
      throw new PrismeAPIError('Timeout: La requête a pris trop de temps', 408);
    }
    throw new PrismeAPIError(
      `Erreur réseau: ${error instanceof Error ? error.message : 'Inconnue'}`
    );
  }
}

// ============================================================================
// API CLIENT
// ============================================================================

export const prismeClient = {
  // INGESTION
  ingererInstance: (clientId: string, instance: Types.InstanceTRCO) =>
    apiFetch<Types.ReponseIngestion>(
      `${PRISME_CONFIG.routes.ingestion}/${clientId}`,
      { method: 'POST', body: JSON.stringify(instance) }
    ),

  // EXÉCUTION
  declencherExecution: (instanceId: string, clientId: string) =>
    apiFetch<Types.ReponseExecution>(
      `${PRISME_CONFIG.routes.execution}/${instanceId}?client_id=${clientId}`,
      { method: 'POST' }
    ),

  // PLANNING
  obtenirPlanning: (executionId: string) =>
    apiFetch<Types.PlanningAvecDurees>(
      `${PRISME_CONFIG.routes.planning}/${executionId}`
    ),

  // AUDIT
  obtenirCodeSource: (executionId: string) =>
    apiFetch<Types.CodeSource>(`${PRISME_CONFIG.routes.audit}/${executionId}`),

  // DIAGNOSTICS
  diagnostiquerExecution: (
    executionId: string,
    payload: Types.DiagnosticPayload
  ) =>
    apiFetch<Types.DiagnosticResultat>(
      `${PRISME_CONFIG.routes.diagnostics}/${executionId}`,
      { method: 'POST', body: JSON.stringify(payload) },
      PRISME_CONFIG.timeoutDiagnostics
    ),

  // SUPERVISION
  listerInstances: () =>
    apiFetch<Types.InstanceInfo[]>(
      `${PRISME_CONFIG.routes.supervision}/instances`
    ),

  listerExecutions: () =>
    apiFetch<Types.ExecutionInfo[]>(
      `${PRISME_CONFIG.routes.supervision}/executions`
    ),

  listerSolveurs: () =>
    apiFetch<Types.SolveurInfo[]>(
      `${PRISME_CONFIG.routes.supervision}/solveurs`
    ),

  verifierSante: () =>
    apiFetch<Types.Sante>(`${PRISME_CONFIG.routes.supervision}/sante`),

  // VALIDATION
  soumettreDecision: (
    executionId: string,
    decision: Types.DecisionValidation
  ) =>
    apiFetch<Types.ReponseValidation>(
      `${PRISME_CONFIG.routes.validation}/executions/${executionId}/decision`,
      { method: 'POST', body: JSON.stringify(decision) }
    ),

  // ADAPTATEURS ERP — chaque adaptateur déterministe expose POST /adapters/{nom}/ingerer,
  // sans body : il lit sa source de données côté backend (ex. GreenSIG lit sa propre DB).
  importerViaAdaptateur: (nomAdaptateur: string) =>
    apiFetch<Types.ReponseImportAdaptateur>(
      `${PRISME_CONFIG.routes.adapters}/${nomAdaptateur}/ingerer`,
      { method: 'POST' }
    ),

  // Import depuis le gabarit xlsx (POST /adapters/tableur/{client_id}, multipart).
  importerFichierTableur: (clientId: string, fichier: File) => {
    const corps = new FormData();
    corps.append('fichier', fichier);
    return apiFetch<Types.ReponseImportAdaptateur>(
      `${PRISME_CONFIG.routes.adapters}/tableur/${clientId}`,
      { method: 'POST', body: corps }
    );
  },
} as const;

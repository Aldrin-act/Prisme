/**
 * Client API PRISME - Fonctions d'appel à l'API FastAPI
 */

import { PRISME_CONFIG } from './config';
import { lireTokenStocke } from './auth/storage';
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
  // `null` = pas de timeout côté client (ex. agent de compréhension sur un
  // gros volume de données brutes) — la requête attend la réponse du
  // serveur aussi longtemps qu'il le faut, sans abandon automatique.
  timeoutMs: number | null = PRISME_CONFIG.timeout
): Promise<T> {
  const controller = new AbortController();
  const timeoutId = timeoutMs === null ? undefined : setTimeout(() => controller.abort(), timeoutMs);

  try {
    // FormData (upload de fichier) : laisser le navigateur poser son propre
    // Content-Type (avec la boundary multipart) plutôt que forcer JSON.
    const estFormData = options?.body instanceof FormData;
    const token = lireTokenStocke();
    const response = await fetch(`${PRISME_CONFIG.baseURL}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        ...(estFormData ? { Accept: PRISME_CONFIG.headers.Accept } : PRISME_CONFIG.headers),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
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

    // 204 No Content (ex. DELETE) : pas de corps à parser.
    if (response.status === 204) {
      return undefined as T;
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

  // Supprime une instance et son historique d'exécution (n'affecte jamais
  // les solveurs enregistrés, indépendants).
  supprimerInstance: (instanceId: string) =>
    apiFetch<void>(`${PRISME_CONFIG.routes.ingestion}/${instanceId}`, { method: 'DELETE' }),

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

  // Agent de compréhension : convertit des données brutes (texte libre, ERP
  // sans adaptateur dédié) en instance T-R-C-O via un LLM, sous le même
  // garde-fou de validation que les autres canaux d'ingestion.
  convertirDonneesBrutes: (clientId: string, donneesBrutes: string) =>
    apiFetch<Types.ReponseComprehension>(
      `${PRISME_CONFIG.routes.adapters}/comprehension/ingerer`,
      { method: 'POST', body: JSON.stringify({ client_id: clientId, donnees_brutes: donneesBrutes }) },
      PRISME_CONFIG.timeoutComprehension
    ),

  // PROJETS — données brutes persistées, reconvertibles à volonté. Le
  // client_id est dérivé du compte authentifié côté serveur ; `clientId`
  // n'est envoyé (et n'a d'effet) que pour un compte admin ciblant un
  // autre client (voir `api/routes/projets.py`).
  creerProjet: (donneesBrutes: string, nom?: string, clientId?: string) =>
    apiFetch<Types.ReponseCreationProjet>(PRISME_CONFIG.routes.projets, {
      method: 'POST',
      body: JSON.stringify({ donnees_brutes: donneesBrutes, nom: nom ?? null, client_id: clientId ?? null }),
    }),

  listerProjets: () => apiFetch<Types.Projet[]>(PRISME_CONFIG.routes.projets),

  obtenirProjet: (projetId: string) =>
    apiFetch<Types.ProjetDetail>(`${PRISME_CONFIG.routes.projets}/${projetId}`),

  // Pas de timeout (null) : demande explicite — une conversion sur un gros
  // volume de données brutes peut prendre plusieurs minutes, on laisse
  // l'utilisateur attendre plutôt que d'abandonner arbitrairement.
  genererInstanceDepuisProjet: (projetId: string) =>
    apiFetch<Types.ReponseComprehension>(
      `${PRISME_CONFIG.routes.projets}/${projetId}/generer-instance`,
      { method: 'POST' },
      null
    ),
} as const;

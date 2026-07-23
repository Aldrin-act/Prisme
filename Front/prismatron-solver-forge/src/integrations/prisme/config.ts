/**
 * Configuration de l'API PRISME
 */

export const PRISME_CONFIG = {
  // Base URL de l'API (backend FastAPI)
  baseURL: import.meta.env.VITE_PRISME_API_URL || 'http://localhost:8000',

  // Timeout par défaut (ms)
  timeout: 30000,

  // Timeout pour diagnostics (opération lente)
  timeoutDiagnostics: 120000,

  // Headers par défaut
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },

  // Routes
  routes: {
    ingestion: '/ingestion',
    execution: '/execution',
    planning: '/planning',
    audit: '/audit',
    diagnostics: '/diagnostics',
    supervision: '/supervision',
    validation: '/validation',
    adapters: '/adapters',
  },
} as const;

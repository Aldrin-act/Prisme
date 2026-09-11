/**
 * Configuration de l'API PRISME
 */

export const PRISME_CONFIG = {
  // Base URL de l'API (backend FastAPI)
  baseURL: import.meta.env.VITE_PRISME_API_URL || "http://localhost:8000",

  // Timeout par défaut (ms)
  timeout: 30000,

  // Timeout pour diagnostics (opération lente)
  timeoutDiagnostics: 120000,

  // Timeout pour la conversion via l'agent de compréhension (LLM sur des
  // données brutes potentiellement volumineuses — plus lent qu'un diagnostic).
  timeoutComprehension: 240000,

  // Headers par défaut
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },

  // Routes
  routes: {
    ingestion: "/ingestion",
    execution: "/execution",
    planning: "/planning",
    audit: "/audit",
    diagnostics: "/diagnostics",
    supervision: "/supervision",
    validation: "/validation",
    adapters: "/adapters",
    sources: "/sources",
    clients: "/clients",
    generation: "/generation",
    apiKeys: "/api-keys",
  },
} as const;

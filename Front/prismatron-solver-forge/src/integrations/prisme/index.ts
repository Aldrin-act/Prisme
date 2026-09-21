/**
 * Intégration PRISME - Point d'entrée unique
 *
 * @example
 * import { prismeClient, useInstances, useSante } from '@/integrations/prisme';
 */

// Client API
export {
  prismeClient,
  PrismeAPIError,
  STATUT_REQUETE_ANNULEE,
  demarrerGenerationSolveur,
  annulerGenerationSolveur,
  suivreJobGeneration,
  type EvenementGenererSolveurStream,
  type ReponseDemarrageJob,
} from "./client";

// Hooks TanStack Query
export * from "./hooks";

// Types
export * from "./types";

// Configuration
export { PRISME_CONFIG } from "./config";

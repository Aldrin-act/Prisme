/**
 * React hooks pour l'API PRISME (avec TanStack Query)
 */

import { useMutation, useQuery, type UseQueryOptions } from '@tanstack/react-query';
import { prismeClient } from './client';
import type * as Types from './types';

// ============================================================================
// QUERY KEYS
// ============================================================================

export const prismeKeys = {
  all: ['prisme'] as const,
  instances: () => [...prismeKeys.all, 'instances'] as const,
  executions: () => [...prismeKeys.all, 'executions'] as const,
  solveurs: () => [...prismeKeys.all, 'solveurs'] as const,
  sante: () => [...prismeKeys.all, 'sante'] as const,
  planning: (executionId: string) => [...prismeKeys.all, 'planning', executionId] as const,
  codeSource: (executionId: string) => [...prismeKeys.all, 'codeSource', executionId] as const,
} as const;

// ============================================================================
// QUERIES (Lecture)
// ============================================================================

/**
 * Liste les instances ingérées
 */
export function useInstances(
  options?: Omit<UseQueryOptions<Types.InstanceInfo[]>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: prismeKeys.instances(),
    queryFn: () => prismeClient.listerInstances(),
    ...options,
  });
}

/**
 * Liste les exécutions
 */
export function useExecutions(
  options?: Omit<UseQueryOptions<Types.ExecutionInfo[]>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: prismeKeys.executions(),
    queryFn: () => prismeClient.listerExecutions(),
    ...options,
  });
}

/**
 * Liste les solveurs validés
 */
export function useSolveurs(
  options?: Omit<UseQueryOptions<Types.SolveurInfo[]>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: prismeKeys.solveurs(),
    queryFn: () => prismeClient.listerSolveurs(),
    ...options,
  });
}

/**
 * Vérifie la santé du système
 */
export function useSante(
  options?: Omit<UseQueryOptions<Types.Sante>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: prismeKeys.sante(),
    queryFn: () => prismeClient.verifierSante(),
    refetchInterval: 30000, // Refresh toutes les 30s par défaut
    ...options,
  });
}

/**
 * Récupère le planning d'une exécution
 */
export function usePlanning(
  executionId: string | null,
  options?: Omit<UseQueryOptions<Types.PlanningAvecDurees>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: prismeKeys.planning(executionId || ''),
    queryFn: () => prismeClient.obtenirPlanning(executionId!),
    enabled: !!executionId,
    ...options,
  });
}

/**
 * Récupère le code source d'un solveur (audit)
 */
export function useCodeSource(
  executionId: string | null,
  options?: Omit<UseQueryOptions<Types.CodeSource>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: prismeKeys.codeSource(executionId || ''),
    queryFn: () => prismeClient.obtenirCodeSource(executionId!),
    enabled: !!executionId,
    ...options,
  });
}

// ============================================================================
// MUTATIONS (Écriture)
// ============================================================================

/**
 * Mutation pour ingérer une instance
 */
export function useIngererInstance() {
  return useMutation({
    mutationFn: ({ clientId, instance }: { clientId: string; instance: Types.InstanceTRCO }) =>
      prismeClient.ingererInstance(clientId, instance),
  });
}

/**
 * Mutation pour déclencher une exécution
 */
export function useDeclencherExecution() {
  return useMutation({
    mutationFn: ({ instanceId, clientId }: { instanceId: string; clientId: string }) =>
      prismeClient.declencherExecution(instanceId, clientId),
  });
}

/**
 * Mutation pour diagnostiquer une exécution
 */
export function useDiagnostiquer() {
  return useMutation({
    mutationFn: ({
      executionId,
      payload,
    }: {
      executionId: string;
      payload: Types.DiagnosticPayload;
    }) => prismeClient.diagnostiquerExecution(executionId, payload),
  });
}

/**
 * Mutation pour soumettre une décision de validation
 */
export function useSoumettreDecision() {
  return useMutation({
    mutationFn: ({
      executionId,
      decision,
    }: {
      executionId: string;
      decision: Types.DecisionValidation;
    }) => prismeClient.soumettreDecision(executionId, decision),
  });
}

/**
 * Mutation pour importer une instance via un adaptateur ERP déterministe
 * (ex. "greensig") — POST /adapters/{nom}/ingerer, sans body.
 */
export function useImporterViaAdaptateur() {
  return useMutation({
    mutationFn: (nomAdaptateur: string) => prismeClient.importerViaAdaptateur(nomAdaptateur),
  });
}

/**
 * Mutation pour importer une instance depuis un fichier xlsx rempli
 * (gabarit `docs/dsl/gabarit_ingestion_trco.xlsx`).
 */
export function useImporterFichierTableur() {
  return useMutation({
    mutationFn: ({ clientId, fichier }: { clientId: string; fichier: File }) =>
      prismeClient.importerFichierTableur(clientId, fichier),
  });
}

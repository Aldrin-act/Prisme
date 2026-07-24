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
  projets: () => [...prismeKeys.all, 'projets'] as const,
  projet: (projetId: string) => [...prismeKeys.all, 'projets', projetId] as const,
  clients: () => [...prismeKeys.all, 'clients'] as const,
  instance: (instanceId: string) => [...prismeKeys.all, 'instance', instanceId] as const,
} as const;

// ============================================================================
// QUERIES (Lecture)
// ============================================================================

/**
 * Liste les clients (tenants) — public, pas besoin d'être connecté.
 */
export function useClients(
  options?: Omit<UseQueryOptions<Types.Client[]>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: prismeKeys.clients(),
    queryFn: () => prismeClient.listerClients(),
    ...options,
  });
}

/**
 * Contenu T-R-C-O complet d'une instance déjà ingérée.
 */
export function useInstance(
  instanceId: string | null,
  options?: Omit<UseQueryOptions<Types.InstanceDetail>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: prismeKeys.instance(instanceId || ''),
    queryFn: () => prismeClient.obtenirInstance(instanceId!),
    enabled: !!instanceId,
    ...options,
  });
}

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
 * Liste les projets (données brutes persistées) d'un client
 */
export function useProjets(
  options?: Omit<UseQueryOptions<Types.Projet[]>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: prismeKeys.projets(),
    queryFn: () => prismeClient.listerProjets(),
    ...options,
  });
}

/**
 * Détail d'un projet : données brutes + instances déjà générées
 */
export function useProjet(
  projetId: string | null,
  options?: Omit<UseQueryOptions<Types.ProjetDetail>, 'queryKey' | 'queryFn'>
) {
  return useQuery({
    queryKey: prismeKeys.projet(projetId || ''),
    queryFn: () => prismeClient.obtenirProjet(projetId!),
    enabled: !!projetId,
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
 * Mutation pour supprimer une instance et son historique d'exécution.
 */
export function useSupprimerInstance() {
  return useMutation({
    mutationFn: (instanceId: string) => prismeClient.supprimerInstance(instanceId),
  });
}

/**
 * Mutation pour remplacer les objectifs d'une instance déjà ingérée.
 */
export function useModifierObjectifs() {
  return useMutation({
    mutationFn: ({ instanceId, objectifs }: { instanceId: string; objectifs: Types.Objectif[] }) =>
      prismeClient.modifierObjectifs(instanceId, objectifs),
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

/**
 * Mutation pour convertir des données brutes (ERP sans adaptateur dédié)
 * en instance T-R-C-O via l'agent de compréhension (LLM).
 */
export function useConvertirDonneesBrutes() {
  return useMutation({
    mutationFn: ({ clientId, donneesBrutes }: { clientId: string; donneesBrutes: string }) =>
      prismeClient.convertirDonneesBrutes(clientId, donneesBrutes),
  });
}

/**
 * Mutation pour créer un client (admin uniquement côté backend).
 */
export function useCreerClient() {
  return useMutation({
    mutationFn: ({ clientId, nom }: { clientId: string; nom?: string }) =>
      prismeClient.creerClient(clientId, nom),
  });
}

/**
 * Mutation pour créer un projet (persiste des données brutes sans les convertir).
 */
export function useCreerProjet() {
  return useMutation({
    mutationFn: ({
      donneesBrutes,
      nom,
      clientId,
    }: {
      donneesBrutes: string;
      nom?: string;
      clientId?: string;
    }) => prismeClient.creerProjet(donneesBrutes, nom, clientId),
  });
}

/**
 * Mutation pour générer une instance de plus à partir d'un projet existant —
 * rejouable à volonté, sans jamais re-saisir les données brutes.
 */
export function useGenererInstanceDepuisProjet() {
  return useMutation({
    mutationFn: (projetId: string) => prismeClient.genererInstanceDepuisProjet(projetId),
  });
}

/**
 * Mutation pour lancer le pipeline de génération de solveur depuis une
 * instance déjà ingérée (génération LLM → cascade → enregistrement).
 */
export function useGenererSolveur() {
  return useMutation({
    mutationFn: (instanceId: string) => prismeClient.genererSolveur(instanceId),
  });
}

/**
 * Mutation pour supprimer un projet (données brutes) — n'affecte jamais les
 * instances déjà générées à partir de lui.
 */
export function useSupprimerProjet() {
  return useMutation({
    mutationFn: (projetId: string) => prismeClient.supprimerProjet(projetId),
  });
}

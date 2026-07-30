/**
 * React hooks pour l'API PRISME (avec TanStack Query)
 */

import { useMutation, useQueries, useQuery, type UseQueryOptions } from "@tanstack/react-query";
import { prismeClient, listerJobsGeneration, obtenirHistoriqueJobGeneration } from "./client";
import type * as Types from "./types";

// ============================================================================
// QUERY KEYS
// ============================================================================

export const prismeKeys = {
  all: ["prisme"] as const,
  instances: () => [...prismeKeys.all, "instances"] as const,
  executions: () => [...prismeKeys.all, "executions"] as const,
  solveurs: () => [...prismeKeys.all, "solveurs"] as const,
  sante: () => [...prismeKeys.all, "sante"] as const,
  planning: (executionId: string) => [...prismeKeys.all, "planning", executionId] as const,
  codeSource: (executionId: string) => [...prismeKeys.all, "codeSource", executionId] as const,
  codeSourceSolveur: (idSolveur: string) =>
    [...prismeKeys.all, "codeSourceSolveur", idSolveur] as const,
  projets: () => [...prismeKeys.all, "projets"] as const,
  projet: (projetId: string) => [...prismeKeys.all, "projets", projetId] as const,
  clients: () => [...prismeKeys.all, "clients"] as const,
  instance: (instanceId: string) => [...prismeKeys.all, "instance", instanceId] as const,
  jobsGeneration: (instanceId?: string) =>
    [...prismeKeys.all, "jobsGeneration", instanceId ?? "tous"] as const,
  historiqueJobGeneration: (jobId: string) =>
    [...prismeKeys.all, "historiqueJobGeneration", jobId] as const,
} as const;

// ============================================================================
// QUERIES (Lecture)
// ============================================================================

/**
 * Liste les clients (tenants) — public, pas besoin d'être connecté.
 */
export function useClients(
  options?: Omit<UseQueryOptions<Types.Client[]>, "queryKey" | "queryFn">,
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
  options?: Omit<UseQueryOptions<Types.InstanceDetail>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.instance(instanceId || ""),
    queryFn: () => prismeClient.obtenirInstance(instanceId!),
    enabled: !!instanceId,
    ...options,
  });
}

/**
 * Liste les instances ingérées
 */
export function useInstances(
  options?: Omit<UseQueryOptions<Types.InstanceInfo[]>, "queryKey" | "queryFn">,
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
  options?: Omit<UseQueryOptions<Types.ExecutionInfo[]>, "queryKey" | "queryFn">,
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
  options?: Omit<UseQueryOptions<Types.SolveurInfo[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.solveurs(),
    queryFn: () => prismeClient.listerSolveurs(),
    ...options,
  });
}

/**
 * Jobs de génération en cours ou terminés (mémoire process du serveur) —
 * pour un indicateur "génération en cours" visible depuis n'importe quelle
 * page. Interrogé toutes les 4s tant qu'un job n'est pas terminé, comme
 * l'icône de chargement d'un onglet de navigateur.
 */
export function useJobsGeneration(
  instanceId?: string,
  options?: Omit<UseQueryOptions<Types.JobGenerationInfo[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.jobsGeneration(instanceId),
    queryFn: () => listerJobsGeneration(instanceId),
    refetchInterval: (query) => (query.state.data?.some((j) => !j.termine) ? 4000 : 15000),
    ...options,
  });
}

/**
 * Historique complet et durable d'un job de génération (§6.6) — code candidat
 * de chaque tentative de la boucle de réparation, y compris les rejetées.
 * Distinct de `useJobsGeneration` (mémoire process, source du direct SSE) :
 * celui-ci survit à un redémarrage du serveur. Désactivé tant que `jobId`
 * est nul (ex. onglet de génération jamais encore lancé).
 */
export function useHistoriqueJobGeneration(
  jobId: string | null,
  options?: Omit<UseQueryOptions<Types.HistoriqueJobGeneration>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.historiqueJobGeneration(jobId || ""),
    queryFn: () => obtenirHistoriqueJobGeneration(jobId!),
    enabled: !!jobId,
    ...options,
  });
}

/**
 * Vérifie la santé du système
 */
export function useSante(options?: Omit<UseQueryOptions<Types.Sante>, "queryKey" | "queryFn">) {
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
  options?: Omit<UseQueryOptions<Types.PlanningAvecDurees>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.planning(executionId || ""),
    queryFn: () => prismeClient.obtenirPlanning(executionId!),
    enabled: !!executionId,
    ...options,
  });
}

/**
 * Liste les projets (données brutes persistées) d'un client
 */
export function useProjets(
  options?: Omit<UseQueryOptions<Types.Projet[]>, "queryKey" | "queryFn">,
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
  options?: Omit<UseQueryOptions<Types.ProjetDetail>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.projet(projetId || ""),
    queryFn: () => prismeClient.obtenirProjet(projetId!),
    enabled: !!projetId,
    ...options,
  });
}

/**
 * "Nom du projet" pour chaque projet connu, par projet_id — pour tout
 * endroit affichant une exécution/un planning par son projet propriétaire
 * (`ExecutionInfo.projet_id`, §annexe modèle Instance/Projet) plutôt que
 * par l'instance historiquement exécutée. Contrairement à
 * `useLabelsInstances`, ne nécessite aucune reconstruction N+1 : le nom
 * est déjà sur `Projet` (`GET /projets`).
 */
export function useLabelsProjets(): Map<string, string> {
  const { data: projets } = useProjets();
  const labelParProjet = new Map<string, string>();
  (projets ?? []).forEach((projet) => {
    labelParProjet.set(projet.projet_id, projet.nom ?? "Sans nom");
  });
  return labelParProjet;
}

/**
 * Reconstruit "nom du projet + rang" pour chaque instance connue —
 * /supervision/instances ne relie pas les instances à leur projet, seul
 * GET /projets/{id} le fait (`instances: [{instance_id, ...}]`). Centralise
 * un calcul auparavant dupliqué dans plusieurs pages (Instances, Générateur
 * de solveurs, Solveurs générés) pour tout endroit affichant une instance
 * par un nom lisible plutôt que son UUID brut. Reflète la provenance
 * (génération), distincte de l'instance courante d'un projet
 * (`Projet.instance_id`) depuis l'inversion Instance/Projet.
 */
export function useLabelsInstances(): Map<string, string> {
  const { data: projets } = useProjets();
  const detailsProjets = useQueries({
    queries: (projets ?? []).map((projet) => ({
      queryKey: prismeKeys.projet(projet.projet_id),
      queryFn: () => prismeClient.obtenirProjet(projet.projet_id),
    })),
  });
  const labelParInstance = new Map<string, string>();
  detailsProjets.forEach((requete) => {
    const detail = requete.data as Types.ProjetDetail | undefined;
    if (!detail) return;
    const nom = detail.nom ?? "Sans nom";
    [...detail.instances].reverse().forEach((instance, index) => {
      labelParInstance.set(instance.instance_id, `${nom}-${index + 1}`);
    });
  });
  return labelParInstance;
}

/**
 * Récupère le code source d'un solveur (audit)
 */
export function useCodeSource(
  executionId: string | null,
  options?: Omit<UseQueryOptions<Types.CodeSource>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.codeSource(executionId || ""),
    queryFn: () => prismeClient.obtenirCodeSource(executionId!),
    enabled: !!executionId,
    ...options,
  });
}

/**
 * Récupère le code source d'un solveur directement par son id (audit) —
 * pour un solveur jamais encore exécuté, sans execution_id disponible.
 */
export function useCodeSourceSolveur(
  idSolveur: string | null,
  options?: Omit<UseQueryOptions<Types.CodeSource>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.codeSourceSolveur(idSolveur || ""),
    queryFn: () => prismeClient.obtenirCodeSourceParSolveur(idSolveur!),
    enabled: !!idSolveur,
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
 * Mutation pour déclencher une exécution — par projet, pas par instance
 * (§annexe modèle Instance/Projet) : chaque projet a son planning attitré.
 */
export function useDeclencherExecution() {
  return useMutation({
    mutationFn: ({ projetId, clientId }: { projetId: string; clientId: string }) =>
      prismeClient.declencherExecution(projetId, clientId),
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
 * Mutation pour importer une instance depuis trois fichiers CSV séparés —
 * Tâches, Ressources, Contraintes (gabarit `docs/dsl/gabarit_csv/`).
 */
export function useImporterFichiersCsv() {
  return useMutation({
    mutationFn: ({
      clientId,
      fichiers,
    }: {
      clientId: string;
      fichiers: { taches: File; ressources: File; contraintes: File };
    }) => prismeClient.importerFichiersCsv(clientId, fichiers),
  });
}

/**
 * Mutation pour importer une instance depuis un JSON "brut avec compétences" —
 * sur-ensemble du format T-R-C-O canonique, une tâche peut y porter une durée
 * estimée pour dériver sa compatibilité depuis des compétences plutôt que de
 * la déclarer à la main (gabarit `public/gabarits/instance_exemple.json`).
 */
export function useImporterJsonAvecCompetences() {
  return useMutation({
    mutationFn: ({ clientId, payload }: { clientId: string; payload: Record<string, unknown> }) =>
      prismeClient.importerJsonAvecCompetences(clientId, payload),
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
 * instances déjà générées à partir de lui, mais supprime en cascade son
 * propre historique d'exécution (plannings, décisions), désormais rattaché
 * au projet et non plus à l'instance (§annexe modèle Instance/Projet).
 */
export function useSupprimerProjet() {
  return useMutation({
    mutationFn: (projetId: string) => prismeClient.supprimerProjet(projetId),
  });
}

/**
 * Mutation pour faire d'une instance existante (gabarit métier réutilisable)
 * l'instance courante d'un projet — §annexe modèle Instance/Projet. Refusée
 * (403) si l'instance et le projet n'appartiennent pas au même client.
 */
export function useAssocierInstanceAuProjet() {
  return useMutation({
    mutationFn: ({ projetId, instanceId }: { projetId: string; instanceId: string }) =>
      prismeClient.associerInstanceAuProjet(projetId, instanceId),
  });
}

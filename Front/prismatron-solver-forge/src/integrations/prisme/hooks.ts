/**
 * React hooks pour l'API PRISME (avec TanStack Query)
 */

import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import {
  prismeClient,
  listerJobsGeneration,
  obtenirHistoriqueJobGeneration,
  obtenirStatistiquesGeneration,
} from "./client";
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
  planningAjuste: (executionId: string) =>
    [...prismeKeys.all, "planningAjuste", executionId] as const,
  codeSource: (executionId: string) => [...prismeKeys.all, "codeSource", executionId] as const,
  codeSourceSolveur: (idSolveur: string) =>
    [...prismeKeys.all, "codeSourceSolveur", idSolveur] as const,
  sources: () => [...prismeKeys.all, "sources"] as const,
  source: (sourceId: string) => [...prismeKeys.all, "sources", sourceId] as const,
  apercuPromptComprehension: (sourceId: string) =>
    [...prismeKeys.all, "apercuPromptComprehension", sourceId] as const,
  clients: () => [...prismeKeys.all, "clients"] as const,
  instance: (instanceId: string) => [...prismeKeys.all, "instance", instanceId] as const,
  jobsGeneration: (instanceId?: string) =>
    [...prismeKeys.all, "jobsGeneration", instanceId ?? "tous"] as const,
  statistiquesGeneration: (agent?: string) =>
    [...prismeKeys.all, "statistiquesGeneration", agent ?? "tous"] as const,
  historiqueJobGeneration: (jobId: string) =>
    [...prismeKeys.all, "historiqueJobGeneration", jobId] as const,
  propositionsSupervision: (enAttente?: boolean) =>
    [...prismeKeys.all, "propositionsSupervision", enAttente ?? false] as const,
  clesApi: () => [...prismeKeys.all, "clesApi"] as const,
  comparaisonScenarios: (instanceId: string) =>
    [...prismeKeys.all, "comparaisonScenarios", instanceId] as const,
  commande: (commandeId: string) => [...prismeKeys.all, "commande", commandeId] as const,
  commandesInstance: (instanceId: string) =>
    [...prismeKeys.all, "commandesInstance", instanceId] as const,
  processus: (instanceId: string) => [...prismeKeys.all, "processus", instanceId] as const,
  commandes: () => [...prismeKeys.all, "commandes"] as const,
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
 * KPI d'agrégat (page Analytique) — calculés côté serveur depuis le stockage persisté,
 * contrairement à `useJobsGeneration` (mémoire process). Pas de génération en cours à
 * suivre ici (données déjà terminées) : un rafraîchissement modéré suffit. `agent`
 * (optionnel, déjà normalisé) restreint le calcul aux générations où cet agent est
 * intervenu — voir `api/statistiques_generation.py::calculer_statistiques`.
 */
export function useStatistiquesGeneration(
  agent?: string,
  options?: Omit<UseQueryOptions<Types.StatistiquesGeneration>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.statistiquesGeneration(agent),
    queryFn: () => obtenirStatistiquesGeneration(agent),
    refetchInterval: 30000,
    ...options,
  });
}

/**
 * Historique complet et durable d'un job de génération (§6.6) — code candidat
 * de chaque tentative de la boucle de réparation, y compris les rejetées.
 * Distinct de `useJobsGeneration` (mémoire process, source du direct SSE) :
 * celui-ci survit à un redémarrage du serveur. Désactivé tant que `jobId`
 * est nul (ex. onglet de génération jamais encore lancé).
 *
 * Interrogé toutes les 4s tant que le job n'est pas terminé — sans ça, ouvrir
 * cette modale pendant qu'un agent tourne encore fige la vue sur l'instant de
 * l'ouverture : les sections (spécification, plan technique, code...) des
 * agents qui terminent ensuite n'apparaissent jamais tant que la modale reste
 * ouverte, même de longues minutes plus tard (même motif que `useJobsGeneration`
 * ci-dessus).
 */
export function useHistoriqueJobGeneration(
  jobId: string | null,
  options?: Omit<UseQueryOptions<Types.HistoriqueJobGeneration>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.historiqueJobGeneration(jobId || ""),
    queryFn: () => obtenirHistoriqueJobGeneration(jobId!),
    enabled: !!jobId,
    refetchInterval: (query) => (query.state.data && !query.state.data.termine ? 4000 : false),
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
 * Liste les propositions de l'agent de supervision (MT7) — scopées par le
 * client du compte authentifié côté backend (voir api/routes/supervision.py).
 */
export function usePropositionsSupervision(
  enAttente?: boolean,
  options?: Omit<UseQueryOptions<Types.PropositionSupervision[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.propositionsSupervision(enAttente),
    queryFn: () => prismeClient.listerPropositionsSupervision(enAttente),
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
 * Révision ajustée à la main du planning d'une exécution (Gantt interactif, Phase 3) — `null`
 * tant qu'aucun ajustement n'a encore été enregistré, jamais une erreur de requête.
 */
export function usePlanningAjuste(
  executionId: string | null,
  options?: Omit<UseQueryOptions<Types.PlanningAvecDurees | null>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.planningAjuste(executionId || ""),
    queryFn: () => prismeClient.obtenirPlanningAjuste(executionId!),
    enabled: !!executionId,
    ...options,
  });
}

/**
 * Mutation pour soumettre un planning ajusté à la main — voir `ReponseAjustementPlanning.legal`
 * pour savoir si la révision a bien été persistée (jamais une exception pour un refus métier).
 */
export function useAjusterPlanning() {
  return useMutation({
    mutationFn: ({ executionId, planning }: { executionId: string; planning: Types.Planning }) =>
      prismeClient.ajusterPlanning(executionId, planning),
  });
}

/**
 * Liste les sources de données (données brutes persistées) d'un client
 */
export function useSources(
  options?: Omit<UseQueryOptions<Types.SourceDonnees[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.sources(),
    queryFn: () => prismeClient.listerSources(),
    ...options,
  });
}

/**
 * Liste les clés API du compte authentifié (jamais celles d'un autre compte).
 */
export function useClesApi(
  options?: Omit<UseQueryOptions<Types.CleApi[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.clesApi(),
    queryFn: () => prismeClient.listerClesApi(),
    ...options,
  });
}

/**
 * Statut d'une commande — recalculé à la volée contre le dernier planning réussi de son
 * instance, jamais mis en cache côté serveur.
 */
export function useCommande(
  commandeId: string | null,
  options?: Omit<UseQueryOptions<Types.StatutCommande>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.commande(commandeId || ""),
    queryFn: () => prismeClient.obtenirCommande(commandeId!),
    enabled: !!commandeId,
    ...options,
  });
}

/**
 * Processus unique de l'atelier — `etapes` vide tant qu'il n'a jamais été défini.
 */
export function useProcessus(
  instanceId: string | null,
  options?: Omit<UseQueryOptions<Types.ProcessusAtelier>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.processus(instanceId || ""),
    queryFn: () => prismeClient.obtenirProcessus(instanceId!),
    enabled: !!instanceId,
    ...options,
  });
}

/**
 * Toutes les commandes de cet atelier (instance), chacune avec son statut recalculé à
 * la volée contre le dernier planning réussi — voir GET /ingestion/{instance_id}/commandes.
 */
export function useCommandesInstance(
  instanceId: string | null,
  options?: Omit<UseQueryOptions<Types.StatutCommande[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.commandesInstance(instanceId || ""),
    queryFn: () => prismeClient.listerCommandes(instanceId!),
    enabled: !!instanceId,
    ...options,
  });
}

/**
 * Toutes les commandes de tous les ateliers (instances) du compte authentifié — vue
 * transverse (page Commandes), voir GET /ingestion/commandes.
 */
export function useCommandes(
  options?: Omit<UseQueryOptions<Types.StatutCommande[]>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.commandes(),
    queryFn: () => prismeClient.listerToutesCommandes(),
    ...options,
  });
}

/**
 * Détail d'une source : données brutes + instances déjà générées
 */
export function useSource(
  sourceId: string | null,
  options?: Omit<UseQueryOptions<Types.SourceDetail>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.source(sourceId || ""),
    queryFn: () => prismeClient.obtenirSource(sourceId!),
    enabled: !!sourceId,
    ...options,
  });
}

export interface LabelInstance {
  label: string;
  sourceId: string | null;
  nomSource: string | null;
}

/**
 * Reconstruit "nom de la source + rang" pour chaque instance connue —
 * /supervision/instances ne relie pas les instances à leur source, seul
 * GET /sources/{id} le fait (`instances: [{instance_id, ...}]`). Centralise
 * un calcul autrement dupliqué dans plusieurs pages (Instances, Générateur
 * de solveurs, Solveurs générés, Plannings) pour tout
 * endroit affichant une instance ou une exécution par un nom lisible plutôt
 * que son UUID brut — une exécution n'a que `instance_id` (une source n'a
 * jamais d'historique d'exécution propre), donc le label se retrouve
 * toujours en passant par l'instance. `undefined` (via `.get()`) pour toute
 * instance sans provenance connue (ingérée par un autre canal que l'agent
 * de compréhension) — l'appelant se replie alors sur l'UUID brut.
 */
export function useLabelsInstances(): Map<string, LabelInstance> {
  const { data: sources } = useSources();
  const detailsSources = useQueries({
    queries: (sources ?? []).map((source) => ({
      queryKey: prismeKeys.source(source.source_id),
      queryFn: () => prismeClient.obtenirSource(source.source_id),
    })),
  });
  const labelParInstance = new Map<string, LabelInstance>();
  detailsSources.forEach((requete) => {
    const detail = requete.data as Types.SourceDetail | undefined;
    if (!detail) return;
    const nom = detail.nom ?? "Sans nom";
    [...detail.instances].reverse().forEach((instance, index) => {
      labelParInstance.set(instance.instance_id, {
        label: `${nom}-${index + 1}`,
        sourceId: detail.source_id,
        nomSource: nom,
      });
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
 * Mutation pour remplacer en place le contenu T-R-C-O complet d'une instance
 * déjà ingérée — même instance_id, historique d'exécution intact.
 */
export function useModifierInstance() {
  return useMutation({
    mutationFn: ({ instanceId, instance }: { instanceId: string; instance: Types.InstanceTRCO }) =>
      prismeClient.modifierInstance(instanceId, instance),
  });
}

/**
 * Mutation pour créer une instance variante d'instanceId (scénario comparatif)
 * — nouvelle instance à part entière, rattachée au même groupe que l'originale.
 */
export function useCreerScenario() {
  return useMutation({
    mutationFn: ({ instanceId, instance }: { instanceId: string; instance: Types.InstanceTRCO }) =>
      prismeClient.creerScenario(instanceId, instance),
  });
}

/**
 * Comparaison de toutes les instances du groupe de scénarios d'instanceId
 * (elle comprise) sur leur dernière exécution réussie connue.
 */
export function useComparaisonScenarios(
  instanceId: string | null,
  options?: Omit<UseQueryOptions<Types.ReponseComparaisonScenarios>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.comparaisonScenarios(instanceId || ""),
    queryFn: () => prismeClient.obtenirComparaisonScenarios(instanceId!),
    enabled: !!instanceId,
    ...options,
  });
}

/**
 * Mutation pour déclencher une exécution — directement par instance_id.
 * horizonGeleJours (Phase 2) : > 0 pour figer les opérations déjà planifiées
 * qui tombent dans cette fenêtre, sans effet si aucun planning précédent
 * n'existe encore pour cette instance.
 */
export function useDeclencherExecution() {
  return useMutation({
    mutationFn: ({
      instanceId,
      horizonGeleJours,
    }: {
      instanceId: string;
      horizonGeleJours?: number;
    }) => prismeClient.declencherExecution(instanceId, horizonGeleJours),
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
 * Mutation pour déclencher une passe d'analyse de l'agent de supervision
 * (MT7) — un ou plusieurs appels LLM selon le nombre de clients analysés.
 */
export function useDeclencherAnalyseSupervision() {
  return useMutation({
    mutationFn: (requete: Types.RequeteAnalyseSupervision) =>
      prismeClient.declencherAnalyseSupervision(requete),
  });
}

/**
 * Mutation (et non requête) : chaque vérification rejoue le Benchmarker, un appel LLM — lancée
 * uniquement sur clic, jamais automatiquement au changement d'atelier.
 */
export function useEvaluerSolveurSupervision() {
  return useMutation({
    mutationFn: ({ instanceId, idSolveur }: { instanceId: string; idSolveur?: string }) =>
      prismeClient.evaluerSolveurSupervision(instanceId, idSolveur),
  });
}

/**
 * Mutation pour accepter/refuser une proposition de l'agent de supervision —
 * sur acceptation, déclenche automatiquement l'action correspondante
 * (régénération, exécution ou diagnostic) côté serveur.
 */
export function useDeciderPropositionSupervision() {
  return useMutation({
    mutationFn: ({
      propositionId,
      requete,
    }: {
      propositionId: string;
      requete: Types.RequeteDecisionProposition;
    }) => prismeClient.deciderPropositionSupervision(propositionId, requete),
  });
}

/**
 * Mutation pour importer une instance via un adaptateur ERP déterministe
 * (ex. "greensig") — POST /adapters/{nom}/ingerer, sans body.
 */
export function useImporterViaAdaptateur() {
  return useMutation({
    mutationFn: ({ nomAdaptateur }: { nomAdaptateur: string }) =>
      prismeClient.importerViaAdaptateur(nomAdaptateur),
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
      delimiteur,
      uniteTemps,
      genererDescription,
    }: {
      clientId: string;
      fichiers: { taches: File; ressources: File; contraintes: File; commandes?: File };
      delimiteur?: string;
      uniteTemps?: string;
      genererDescription?: boolean;
    }) =>
      prismeClient.importerFichiersCsv(
        clientId,
        fichiers,
        delimiteur,
        uniteTemps,
        genererDescription,
      ),
  });
}

/**
 * Mutation pour importer une instance depuis un JSON "brut avec compétences" —
 * sur-ensemble du format T-R-C-O canonique, une tâche peut y exiger une
 * compétence pour dériver sa compatibilité (durée comblée par apprentissage
 * automatique) plutôt que de la déclarer à la main
 * (gabarit `public/gabarits/instance_exemple.json`).
 */
export function useImporterJsonAvecCompetences() {
  return useMutation({
    mutationFn: ({
      clientId,
      payload,
      uniteTemps,
    }: {
      clientId: string;
      payload: Record<string, unknown>;
      uniteTemps?: string;
    }) => prismeClient.importerJsonAvecCompetences(clientId, payload, uniteTemps),
  });
}

/**
 * Mutation pour importer une instance depuis des fichiers CSV locaux (côté serveur) —
 * pratique pour imports en masse, tests avec données de référence, ou scripts automatisés.
 */
export function useImporterCsvLocal() {
  return useMutation({
    mutationFn: ({
      clientId,
      cheminDossier,
      uniteTemps,
    }: {
      clientId: string;
      cheminDossier: string;
      uniteTemps?: string;
    }) => prismeClient.importerCsvLocal(clientId, cheminDossier, uniteTemps),
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
 * Mutation pour créer une clé API — le `secret` de la réponse n'est jamais
 * renvoyé à nouveau ensuite, à afficher immédiatement à l'utilisateur.
 */
export function useCreerCleApi() {
  return useMutation({
    mutationFn: (nom: string) => prismeClient.creerCleApi(nom),
  });
}

/**
 * Mutation pour révoquer une clé API — irréversible, la clé cesse
 * immédiatement de s'authentifier.
 */
export function useRevoquerCleApi() {
  return useMutation({
    mutationFn: (cleId: string) => prismeClient.revoquerCleApi(cleId),
  });
}

/**
 * Mutation pour créer une source (persiste des données brutes sans les convertir).
 */
export function useCreerSource() {
  return useMutation({
    mutationFn: ({
      donneesBrutes,
      nom,
      clientId,
      objectifs,
    }: {
      donneesBrutes: string;
      nom?: string;
      clientId?: string;
      objectifs?: Types.Objectif[];
    }) => prismeClient.creerSource(donneesBrutes, nom, clientId, objectifs),
  });
}

/**
 * Mutation pour extraire des données depuis une API HTTP quelconque — ne crée
 * rien : le texte renvoyé remplit le champ "Données brutes" du formulaire,
 * pour relecture humaine avant "Enregistrer la source".
 */
export function useExplorerAPI() {
  return useMutation({
    mutationFn: (requete: Types.RequeteExplorationAPI) => prismeClient.explorerAPI(requete),
  });
}

/**
 * Mutation pour générer une instance de plus à partir d'une source existante —
 * rejouable à volonté, sans jamais re-saisir les données brutes.
 */
export function useGenererInstanceDepuisSource() {
  return useMutation({
    mutationFn: ({
      sourceId,
      instructionsComplementaires,
      signal,
    }: {
      sourceId: string;
      instructionsComplementaires?: string;
      signal?: AbortSignal;
    }) => prismeClient.genererInstanceDepuisSource(sourceId, instructionsComplementaires, signal),
  });
}

/**
 * Mutation pour convertir une source existante sans agent LLM — déterministe,
 * n'aboutit que si le texte brut est déjà structuré (JSON canonique ou CSV
 * Tâches/Ressources/Contraintes) ; sinon 422, direction useGenererInstanceDepuisSource
 * (l'agent, qui interprète n'importe quel texte libre).
 */
export function useGenererInstanceDeterministeDepuisSource() {
  return useMutation({
    mutationFn: ({ sourceId }: { sourceId: string }) =>
      prismeClient.genererInstanceDeterministeDepuisSource(sourceId),
  });
}

/**
 * Aperçu du prompt système + utilisateur réel de l'agent de compréhension pour une source —
 * gratuit (aucun appel LLM), `enabled: false` par défaut : à activer explicitement (ex. quand
 * l'utilisateur ouvre le panneau d'aperçu), jamais chargé automatiquement à l'affichage de la
 * source.
 */
export function useApercuPromptComprehension(
  sourceId: string | null,
  instructionsComplementaires?: string,
  options?: Omit<UseQueryOptions<Types.ApercuPromptComprehension>, "queryKey" | "queryFn">,
) {
  return useQuery({
    queryKey: prismeKeys.apercuPromptComprehension(sourceId || ""),
    queryFn: () =>
      prismeClient.obtenirApercuPromptComprehension(sourceId!, instructionsComplementaires),
    enabled: false,
    ...options,
  });
}

/**
 * Même aperçu que useApercuPromptComprehension ci-dessus, mais pour le formulaire de création —
 * avant toute source enregistrée, sur le texte actuellement saisi/collé. Mutation plutôt que
 * requête : pas d'id de ressource persistée à quoi rattacher une clé de cache, déclenchée à la
 * demande sur le contenu courant du champ.
 */
export function useApercuPromptComprehensionSansSource() {
  return useMutation({
    mutationFn: ({
      donneesBrutes,
      instructionsComplementaires,
    }: {
      donneesBrutes: string;
      instructionsComplementaires?: string;
    }) =>
      prismeClient.obtenirApercuPromptComprehensionSansSource(
        donneesBrutes,
        instructionsComplementaires,
      ),
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
 * Mutation pour supprimer une source (données brutes) — n'affecte jamais les
 * instances déjà générées à partir d'elle ; une source ne porte aucun
 * historique d'exécution à cascader (voir `SourceDonnees`, `api/etat.py`).
 */
export function useSupprimerSource() {
  return useMutation({
    mutationFn: (sourceId: string) => prismeClient.supprimerSource(sourceId),
  });
}

/**
 * Mutation pour définir (ou remplacer) le processus de l'atelier. Les commandes déjà passées ne
 * sont jamais réécrites : seules les suivantes suivent le nouveau processus.
 */
export function useDefinirProcessus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ instanceId, etapes }: { instanceId: string; etapes: Types.EtapeProcessus[] }) =>
      prismeClient.definirProcessus(instanceId, etapes),
    onSuccess: (processus, { instanceId }) => {
      queryClient.setQueryData(prismeKeys.processus(instanceId), processus);
    },
  });
}

/**
 * Mutation pour créer une commande : éclate le processus de l'atelier (cas normal) ou référence
 * des tâches déjà présentes, et en dérive une échéance commune (voir `api/routes/ingestion.py`).
 */
export function useAjouterCommande() {
  return useMutation({
    mutationFn: ({
      instanceId,
      requete,
    }: {
      instanceId: string;
      requete: Types.RequeteNouvelleCommande;
    }) => prismeClient.ajouterCommande(instanceId, requete),
  });
}

/**
 * Mutation pour déclarer l'avancement réel d'une commande (non débutée / en cours / réalisée).
 * Invalide les trois vues qui affichent une commande, pour qu'un statut déclaré depuis la page
 * Commandes se voie aussi dans la page de l'atelier concerné, sans rechargement.
 */
export function useChangerStatutCommande() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      commandeId,
      requete,
    }: {
      commandeId: string;
      requete: Types.RequeteStatutCommande;
    }) => prismeClient.changerStatutCommande(commandeId, requete),
    onSuccess: (commande) => {
      queryClient.invalidateQueries({ queryKey: prismeKeys.commandes() });
      queryClient.invalidateQueries({
        queryKey: prismeKeys.commandesInstance(commande.instance_id),
      });
      queryClient.invalidateQueries({ queryKey: prismeKeys.commande(commande.commande_id) });
    },
  });
}

/**
 * Mutation pour déclarer un retard réellement constaté sur une tâche (voir
 * Types.RequeteRetardTache) — corrige sa durée sur une ressource précise, n'exécute rien :
 * l'appelant relance une exécution ensuite (`useDeclencherExecution`) pour en tenir compte.
 */
export function useDeclarerRetardTache() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      instanceId,
      tacheId,
      requete,
    }: {
      instanceId: string;
      tacheId: string;
      requete: Types.RequeteRetardTache;
    }) => prismeClient.declarerRetardTache(instanceId, tacheId, requete),
    onSuccess: (instance) => {
      queryClient.invalidateQueries({ queryKey: prismeKeys.instance(instance.instance_id) });
      queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
    },
  });
}

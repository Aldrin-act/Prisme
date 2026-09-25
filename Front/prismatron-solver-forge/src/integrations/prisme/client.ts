/**
 * Client API PRISME - Fonctions d'appel à l'API FastAPI
 */

import { PRISME_CONFIG } from "./config";
import { lireTokenStocke } from "./auth/storage";
import type * as Types from "./types";

// ============================================================================
// ERREURS
// ============================================================================

export class PrismeAPIError extends Error {
  constructor(
    message: string,
    public status?: number,
    public detail?: string | Types.ErreurValidationChamp[] | Types.ErreurDetailCodee,
  ) {
    super(message);
    this.name = "PrismeAPIError";
  }

  /** Erreurs de validation par champ (422), vide si `detail` est une simple chaîne. */
  get champs(): Types.ErreurValidationChamp[] {
    return Array.isArray(this.detail) ? this.detail : [];
  }
}

/** Statut posé sur une `PrismeAPIError` quand l'appelant a lui-même annulé la requête (pas une panne). */
export const STATUT_REQUETE_ANNULEE = 499;

// `detail` a 3 formes possibles selon la route (voir `Types.ErreurAPI`) — un
// objet {code, message} (toutes les erreurs d'auth) affiché tel quel donnait
// "Erreur API: [object Object]", le message humain n'était jamais extrait.
function formaterDetailErreur(
  detail: string | Types.ErreurValidationChamp[] | Types.ErreurDetailCodee | undefined,
): string {
  if (Array.isArray(detail)) {
    return detail.map((e) => `${e.loc.join(".")} : ${e.msg}`).join(" ; ");
  }
  if (detail && typeof detail === "object") {
    return detail.message;
  }
  return detail ?? "erreur inconnue";
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
  timeoutMs: number | null = PRISME_CONFIG.timeout,
): Promise<T> {
  const controller = new AbortController();
  const timeoutId =
    timeoutMs === null ? undefined : setTimeout(() => controller.abort(), timeoutMs);
  // Annulation demandée par l'appelant (ex. bouton "Arrêter") — relayée vers notre propre
  // controller, qui reste seul à être passé à fetch (voir `signal` plus bas).
  const signalAppelant = options?.signal;
  const relayerAnnulation = () => controller.abort();
  if (signalAppelant?.aborted) controller.abort();
  else signalAppelant?.addEventListener("abort", relayerAnnulation);

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
      let errorDetail: string | Types.ErreurValidationChamp[] | Types.ErreurDetailCodee;
      try {
        const errorData: Types.ErreurAPI = await response.json();
        errorDetail = errorData.detail;
      } catch {
        errorDetail = response.statusText;
      }
      throw new PrismeAPIError(
        `Erreur API: ${formaterDetailErreur(errorDetail)}`,
        response.status,
        errorDetail,
      );
    }

    // 204 No Content (ex. DELETE) : pas de corps à parser.
    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof PrismeAPIError) throw error;
    if (error instanceof Error && error.name === "AbortError") {
      if (signalAppelant?.aborted) {
        throw new PrismeAPIError("Requête annulée", STATUT_REQUETE_ANNULEE);
      }
      throw new PrismeAPIError("Timeout: La requête a pris trop de temps", 408);
    }
    throw new PrismeAPIError(
      `Erreur réseau: ${error instanceof Error ? error.message : "Inconnue"}`,
    );
  } finally {
    signalAppelant?.removeEventListener("abort", relayerAnnulation);
  }
}

// ============================================================================
// API CLIENT
// ============================================================================

export const prismeClient = {
  // CLIENTS — GET public (utilisé par le formulaire d'inscription), POST admin uniquement.
  listerClients: () => apiFetch<Types.Client[]>(PRISME_CONFIG.routes.clients),

  creerClient: (clientId: string, nom?: string) =>
    apiFetch<Types.Client>(PRISME_CONFIG.routes.clients, {
      method: "POST",
      body: JSON.stringify({ client_id: clientId, nom: nom ?? null }),
    }),

  // CLÉS API — personnelles au compte authentifié (jamais partagées entre
  // comptes d'un même client). Le `secret` de `creerCleApi` n'est renvoyé
  // qu'une seule fois, jamais reconstructible ensuite.
  listerClesApi: () => apiFetch<Types.CleApi[]>(PRISME_CONFIG.routes.apiKeys),

  creerCleApi: (nom: string) =>
    apiFetch<Types.ReponseCreationCleApi>(PRISME_CONFIG.routes.apiKeys, {
      method: "POST",
      body: JSON.stringify({ nom }),
    }),

  revoquerCleApi: (cleId: string) =>
    apiFetch<void>(`${PRISME_CONFIG.routes.apiKeys}/${cleId}`, { method: "DELETE" }),

  // INGESTION
  ingererInstance: (clientId: string, instance: Types.InstanceTRCO) =>
    apiFetch<Types.ReponseIngestion>(`${PRISME_CONFIG.routes.ingestion}/${clientId}`, {
      method: "POST",
      body: JSON.stringify(instance),
    }),

  // Supprime une instance et son historique d'exécution (n'affecte jamais
  // les solveurs enregistrés, indépendants).
  supprimerInstance: (instanceId: string) =>
    apiFetch<void>(`${PRISME_CONFIG.routes.ingestion}/${instanceId}`, { method: "DELETE" }),

  // Contenu T-R-C-O complet d'une instance déjà ingérée (tâches, ressources,
  // contraintes, objectifs).
  obtenirInstance: (instanceId: string) =>
    apiFetch<Types.InstanceDetail>(`${PRISME_CONFIG.routes.ingestion}/${instanceId}`),

  // Remplace les objectifs d'une instance déjà ingérée — seul champ pour
  // lequel une modification en place a du sens (taches/ressources/
  // contraintes définissent le problème, l'objectif ne fait qu'orienter le
  // solveur dessus).
  modifierObjectifs: (instanceId: string, objectifs: Types.Objectif[]) =>
    apiFetch<Types.InstanceDetail>(`${PRISME_CONFIG.routes.ingestion}/${instanceId}/objectifs`, {
      method: "PATCH",
      body: JSON.stringify({ objectifs }),
    }),

  // Remplace en place le contenu T-R-C-O complet d'une instance déjà
  // ingérée — même instance_id, historique d'exécution intact, rien n'est
  // dupliqué.
  modifierInstance: (instanceId: string, instance: Types.InstanceTRCO) =>
    apiFetch<Types.InstanceDetail>(`${PRISME_CONFIG.routes.ingestion}/${instanceId}`, {
      method: "PUT",
      body: JSON.stringify(instance),
    }),

  // Crée une instance variante d'instanceId (payload T-R-C-O complet, même
  // garde-fou qu'une ingestion normale) rattachée au même groupe de
  // scénarios comparatifs — jamais une modification de l'originale.
  creerScenario: (instanceId: string, instance: Types.InstanceTRCO) =>
    apiFetch<Types.ReponseIngestion>(`${PRISME_CONFIG.routes.ingestion}/${instanceId}/scenarios`, {
      method: "POST",
      body: JSON.stringify(instance),
    }),

  // Compare toutes les instances du groupe de scénarios d'instanceId (elle
  // comprise) sur leur dernière exécution réussie connue — ne déclenche
  // jamais d'exécution elle-même.
  obtenirComparaisonScenarios: (instanceId: string) =>
    apiFetch<Types.ReponseComparaisonScenarios>(
      `${PRISME_CONFIG.routes.ingestion}/${instanceId}/scenarios/comparaison`,
    ),

  // EXÉCUTION — déclenchée directement par instance_id, sans intermédiaire.
  // horizonGeleJours (Phase 2, replanification à horizon glissant) : si
  // fourni et > 0, le backend va chercher le dernier planning réussi de
  // cette même instance et le transmet au solveur comme planning_precedent.
  declencherExecution: (instanceId: string, horizonGeleJours?: number) => {
    const params = new URLSearchParams();
    if (horizonGeleJours && horizonGeleJours > 0) {
      params.set("horizon_gele_jours", String(horizonGeleJours));
    }
    const requete = params.toString();
    return apiFetch<Types.ReponseExecution>(
      `${PRISME_CONFIG.routes.execution}/${instanceId}${requete ? `?${requete}` : ""}`,
      { method: "POST" },
    );
  },

  // PLANNING
  obtenirPlanning: (executionId: string) =>
    apiFetch<Types.PlanningAvecDurees>(`${PRISME_CONFIG.routes.planning}/${executionId}`),

  // Gantt interactif (Phase 3) : soumet un planning ajusté à la main pour revalidation par le
  // même vérificateur déterministe que tout le reste du système — toujours 200, `legal`
  // distingue une révision persistée d'un refus métier (jamais une exception réseau).
  ajusterPlanning: (executionId: string, planning: Types.Planning) =>
    apiFetch<Types.ReponseAjustementPlanning>(
      `${PRISME_CONFIG.routes.planning}/${executionId}/ajuster`,
      {
        method: "POST",
        body: JSON.stringify(planning),
      },
    ),

  // null si cette exécution n'a encore aucune révision ajustée — jamais un 404.
  obtenirPlanningAjuste: (executionId: string) =>
    apiFetch<Types.PlanningAvecDurees | null>(
      `${PRISME_CONFIG.routes.planning}/${executionId}/ajuste`,
    ),

  // AUDIT
  obtenirCodeSource: (executionId: string) =>
    apiFetch<Types.CodeSource>(`${PRISME_CONFIG.routes.audit}/${executionId}`),

  // Même canal, mais par id de solveur directement — utile pour un solveur
  // enregistré mais jamais encore exécuté (pas d'execution_id qui y mène).
  obtenirCodeSourceParSolveur: (idSolveur: string) =>
    apiFetch<Types.CodeSource>(`${PRISME_CONFIG.routes.audit}/solveur/${idSolveur}`),

  // DIAGNOSTICS
  diagnostiquerExecution: (executionId: string, payload: Types.DiagnosticPayload) =>
    apiFetch<Types.DiagnosticResultat>(
      `${PRISME_CONFIG.routes.diagnostics}/${executionId}`,
      { method: "POST", body: JSON.stringify(payload) },
      PRISME_CONFIG.timeoutDiagnostics,
    ),

  // SUPERVISION
  listerInstances: () =>
    apiFetch<Types.InstanceInfo[]>(`${PRISME_CONFIG.routes.supervision}/instances`),

  listerExecutions: () =>
    apiFetch<Types.ExecutionInfo[]>(`${PRISME_CONFIG.routes.supervision}/executions`),

  listerSolveurs: () =>
    apiFetch<Types.SolveurInfo[]>(`${PRISME_CONFIG.routes.supervision}/solveurs`),

  verifierSante: () => apiFetch<Types.Sante>(`${PRISME_CONFIG.routes.supervision}/sante`),

  // Agent de supervision (MT7) — détecte des signaux et propose une action,
  // jamais ne l'applique elle-même (voir api/routes/supervision.py).
  listerPropositionsSupervision: (enAttente?: boolean) =>
    apiFetch<Types.PropositionSupervision[]>(
      `${PRISME_CONFIG.routes.supervision}/propositions${enAttente ? "?en_attente=true" : ""}`,
    ),

  // Analyse atelier par atelier — deux appels LLM par atelier au plus (détection puis
  // rédaction) : même budget de temps que l'agent de compréhension.
  declencherAnalyseSupervision: (requete: Types.RequeteAnalyseSupervision) =>
    apiFetch<Types.PropositionSupervision[]>(
      `${PRISME_CONFIG.routes.supervision}/analyser`,
      { method: "POST", body: JSON.stringify(requete) },
      PRISME_CONFIG.timeoutComprehension,
    ),

  // Verdict « faut-il régénérer ce solveur ? » — un appel LLM (Benchmarker) au plus.
  evaluerSolveurSupervision: (instanceId: string, idSolveur?: string) =>
    apiFetch<Types.EvaluationSolveurSupervision>(
      `${PRISME_CONFIG.routes.supervision}/evaluer-solveur`,
      {
        method: "POST",
        body: JSON.stringify({ instance_id: instanceId, id_solveur: idSolveur }),
      },
      PRISME_CONFIG.timeoutComprehension,
    ),

  deciderPropositionSupervision: (
    propositionId: string,
    requete: Types.RequeteDecisionProposition,
  ) =>
    apiFetch<Types.ReponseDecisionPropositionSupervision>(
      `${PRISME_CONFIG.routes.supervision}/propositions/${propositionId}/decision`,
      { method: "POST", body: JSON.stringify(requete) },
    ),

  // VALIDATION
  soumettreDecision: (executionId: string, decision: Types.DecisionValidation) =>
    apiFetch<Types.ReponseValidation>(
      `${PRISME_CONFIG.routes.validation}/executions/${executionId}/decision`,
      { method: "POST", body: JSON.stringify(decision) },
    ),

  // ADAPTATEURS ERP — chaque adaptateur déterministe expose POST /adapters/{nom}/ingerer,
  // sans body : il lit sa source de données côté backend (ex. GreenSIG lit sa propre DB).
  importerViaAdaptateur: (nomAdaptateur: string) =>
    apiFetch<Types.ReponseImportAdaptateur>(
      `${PRISME_CONFIG.routes.adapters}/${nomAdaptateur}/ingerer`,
      { method: "POST" },
    ),

  // Import depuis le gabarit xlsx (POST /adapters/tableur/{client_id}, multipart).
  importerFichierTableur: (clientId: string, fichier: File) => {
    const corps = new FormData();
    corps.append("fichier", fichier);
    return apiFetch<Types.ReponseImportAdaptateur>(
      `${PRISME_CONFIG.routes.adapters}/tableur/${clientId}`,
      { method: "POST", body: corps },
    );
  },

  // Import depuis trois fichiers CSV séparés — Tâches, Ressources, Contraintes,
  // plus un 4ᵉ optionnel Commandes (POST /adapters/csv/{client_id}, multipart,
  // voir adapters/csv_import/) — dérive des échéances par tâche, une échéance
  // déjà explicite l'emporte toujours sur une dérivée. `delimiteur` (un seul
  // caractère, "," par défaut) s'applique identiquement aux quatre fichiers.
  // `uniteTemps` ("jours" par défaut, ou "heures") devient InstanceTRCO.unite_temps.
  // `genererDescription` (optionnel, false par défaut côté serveur) : tente une description
  // métier automatique de l'atelier via l'agent de compréhension — best-effort, jamais bloquant.
  importerFichiersCsv: (
    clientId: string,
    fichiers: { taches: File; ressources: File; contraintes: File; commandes?: File },
    delimiteur?: string,
    uniteTemps?: string,
    genererDescription?: boolean,
  ) => {
    const corps = new FormData();
    corps.append("taches", fichiers.taches);
    corps.append("ressources", fichiers.ressources);
    corps.append("contraintes", fichiers.contraintes);
    if (fichiers.commandes) corps.append("commandes", fichiers.commandes);
    const params = new URLSearchParams();
    if (delimiteur) params.set("delimiteur", delimiteur);
    if (uniteTemps) params.set("unite_temps", uniteTemps);
    if (genererDescription) params.set("generer_description", "true");
    const requete = params.toString();
    return apiFetch<Types.ReponseImportCsv>(
      `${PRISME_CONFIG.routes.adapters}/csv/${clientId}${requete ? `?${requete}` : ""}`,
      { method: "POST", body: corps },
    );
  },

  // Import depuis un JSON "brut avec compétences" (POST /adapters/json/{client_id},
  // voir adapters/json_import/) — sur-ensemble du format T-R-C-O canonique :
  // une tâche peut porter une durée estimée, permettant de dériver sa
  // compatibilité depuis des compétences plutôt que de la déclarer à la main.
  // `uniteTemps` (optionnel) l'emporte sur le "unite_temps" éventuellement présent dans le
  // payload (query param unite_temps) — absent, le payload décide seul.
  importerJsonAvecCompetences: (
    clientId: string,
    payload: Record<string, unknown>,
    uniteTemps?: string,
  ) =>
    apiFetch<Types.ReponseImportAdaptateur>(
      `${PRISME_CONFIG.routes.adapters}/json/${clientId}${
        uniteTemps ? `?${new URLSearchParams({ unite_temps: uniteTemps }).toString()}` : ""
      }`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),

  // Import CSV local : convertit des fichiers CSV présents sur le serveur en instance TRCO
  // (POST /adapters/csv-local/ingerer) — utile pour imports en masse, tests, ou scripts automatisés.
  // `uniteTemps` : même rôle que pour importerFichiersCsv ci-dessus.
  importerCsvLocal: (clientId: string, cheminDossier: string, uniteTemps?: string) =>
    apiFetch<Types.ReponseImportCsvLocal>(`${PRISME_CONFIG.routes.adapters}/csv-local/ingerer`, {
      method: "POST",
      body: JSON.stringify({
        client_id: clientId,
        chemin_dossier: cheminDossier,
        ...(uniteTemps ? { unite_temps: uniteTemps } : {}),
      }),
    }),

  // Agent de compréhension : convertit des données brutes (texte libre, ERP
  // sans adaptateur dédié) en instance T-R-C-O via un LLM, sous le même
  // garde-fou de validation que les autres canaux d'ingestion.
  convertirDonneesBrutes: (clientId: string, donneesBrutes: string) =>
    apiFetch<Types.ReponseComprehension>(
      `${PRISME_CONFIG.routes.adapters}/comprehension/ingerer`,
      {
        method: "POST",
        body: JSON.stringify({ client_id: clientId, donnees_brutes: donneesBrutes }),
      },
      PRISME_CONFIG.timeoutComprehension,
    ),

  // SOURCES DE DONNÉES — données brutes persistées, reconvertibles à
  // volonté. Le client_id est dérivé du compte authentifié côté serveur ;
  // `clientId` n'est envoyé (et n'a d'effet) que pour un compte admin
  // ciblant un autre client (voir `api/routes/sources.py`).
  // `objectifs` (optionnel) : imposés à chaque instance générée depuis cette source.
  creerSource: (
    donneesBrutes: string,
    nom?: string,
    clientId?: string,
    objectifs?: Types.Objectif[],
  ) =>
    apiFetch<Types.ReponseCreationSource>(PRISME_CONFIG.routes.sources, {
      method: "POST",
      body: JSON.stringify({
        donnees_brutes: donneesBrutes,
        nom: nom ?? null,
        client_id: clientId ?? null,
        ...(objectifs && objectifs.length > 0 ? { objectifs } : {}),
      }),
    }),

  listerSources: () => apiFetch<Types.SourceDonnees[]>(PRISME_CONFIG.routes.sources),

  obtenirSource: (sourceId: string) =>
    apiFetch<Types.SourceDetail>(`${PRISME_CONFIG.routes.sources}/${sourceId}`),

  // Supprime les données brutes de la source — n'affecte jamais les instances
  // déjà générées à partir d'elle.
  supprimerSource: (sourceId: string) =>
    apiFetch<void>(`${PRISME_CONFIG.routes.sources}/${sourceId}`, { method: "DELETE" }),

  // Extraction depuis une API HTTP quelconque — URL/authentification
  // fournies ici, jamais enregistrées côté serveur ni renvoyées dans une
  // source. Ne crée rien : le texte renvoyé est destiné à remplir le champ
  // "Données brutes" du formulaire, pour relecture humaine avant
  // "Enregistrer la source".
  explorerAPI: (requete: Types.RequeteExplorationAPI) =>
    apiFetch<Types.ReponseExplorationAPI>(`${PRISME_CONFIG.routes.sources}/explorer-api`, {
      method: "POST",
      body: JSON.stringify(requete),
    }),

  // Pas de timeout (null) : demande explicite — une conversion sur un gros
  // volume de données brutes peut prendre plusieurs minutes, on laisse
  // l'utilisateur attendre plutôt que d'abandonner arbitrairement.
  // `instructionsComplementaires` (optionnel) : contexte métier libre injecté dans une section
  // dédiée du prompt — jamais un moyen de réécrire les règles de traduction elles-mêmes.
  // `signal` (optionnel) : bouton "Arrêter" — coupe la connexion, ce que le serveur détecte pour
  // abandonner la conversion sans enregistrer d'instance.
  genererInstanceDepuisSource: (
    sourceId: string,
    instructionsComplementaires?: string,
    signal?: AbortSignal,
  ) =>
    apiFetch<Types.ReponseComprehension>(
      `${PRISME_CONFIG.routes.sources}/${sourceId}/generer-instance`,
      {
        method: "POST",
        body: JSON.stringify({
          instructions_complementaires: instructionsComplementaires || null,
        }),
        signal,
      },
      null,
    ),

  // Alternative sans agent LLM — déterministe et instantanée, mais n'aboutit
  // que si le texte brut est déjà structuré (JSON canonique ou CSV
  // Tâches/Ressources/Contraintes) ; timeout par défaut, contrairement à
  // genererInstanceDepuisSource ci-dessus, aucun appel LLM à attendre.
  genererInstanceDeterministeDepuisSource: (sourceId: string) =>
    apiFetch<Types.ReponseConversionDeterministe>(
      `${PRISME_CONFIG.routes.sources}/${sourceId}/generer-instance-deterministe`,
      { method: "POST" },
    ),

  // Aperçu du prompt système + utilisateur réel de l'agent de compréhension, sans appeler le
  // LLM (gratuit) — voir genererInstanceDepuisSource ci-dessus, ce que la génération réelle
  // enverrait. `instructionsComplementaires` : mêmes instructions que celles qu'on passerait à
  // genererInstanceDepuisSource, pour que l'aperçu reflète vraiment ce qui serait envoyé.
  obtenirApercuPromptComprehension: (sourceId: string, instructionsComplementaires?: string) =>
    apiFetch<Types.ApercuPromptComprehension>(
      `${PRISME_CONFIG.routes.sources}/${sourceId}/prompt-comprehension${
        instructionsComplementaires
          ? `?${new URLSearchParams({ instructions_complementaires: instructionsComplementaires }).toString()}`
          : ""
      }`,
    ),

  // Même aperçu, mais sur des données brutes pas encore enregistrées en source — pour le
  // formulaire de création, avant toute soumission.
  obtenirApercuPromptComprehensionSansSource: (
    donneesBrutes: string,
    instructionsComplementaires?: string,
  ) =>
    apiFetch<Types.ApercuPromptComprehension>(
      `${PRISME_CONFIG.routes.sources}/prompt-comprehension`,
      {
        method: "POST",
        body: JSON.stringify({
          donnees_brutes: donneesBrutes,
          instructions_complementaires: instructionsComplementaires || null,
        }),
      },
    ),

  // GÉNÉRATION DE SOLVEUR — génération LLM + exécution sandboxée + cascade
  // de validation complète + enregistrement si vert (POST /generation/{instance_id}).
  // Pas de timeout (null) : peut prendre plusieurs dizaines de secondes,
  // même logique que genererInstanceDepuisSource ci-dessus.
  genererSolveur: (instanceId: string) =>
    apiFetch<Types.ReponseGenerationSolveur>(
      `${PRISME_CONFIG.routes.generation}/${instanceId}`,
      { method: "POST" },
      null,
    ),

  // Crée une commande : éclate le processus de l'atelier (cas normal) ou référence des tâches
  // déjà présentes (`taches`), et en dérive une échéance commune (api/routes/ingestion.py).
  ajouterCommande: (instanceId: string, requete: Types.RequeteNouvelleCommande) =>
    apiFetch<Types.ResultatNouvelleCommande>(
      `${PRISME_CONFIG.routes.ingestion}/${instanceId}/commandes`,
      { method: "POST", body: JSON.stringify(requete) },
    ),

  // Statut d'une commande, recalculé à la volée contre le dernier planning réussi.
  obtenirCommande: (commandeId: string) =>
    apiFetch<Types.StatutCommande>(`${PRISME_CONFIG.routes.ingestion}/commandes/${commandeId}`),

  // Avancement réel de la commande dans l'atelier, déclaré par un humain (non débutée, en
  // cours, réalisée) — la seule source possible : le planning ne dit que ce qui devrait
  // arriver (voir api/routes/ingestion.py::changer_statut_commande).
  changerStatutCommande: (commandeId: string, requete: Types.RequeteStatutCommande) =>
    apiFetch<Types.StatutCommande>(
      `${PRISME_CONFIG.routes.ingestion}/commandes/${commandeId}/statut`,
      { method: "PATCH", body: JSON.stringify(requete) },
    ),

  // Déclare un retard réellement constaté sur une tâche (voir Types.RequeteRetardTache) — ne
  // déclenche aucune exécution, à faire explicitement ensuite avec la durée corrigée.
  declarerRetardTache: (instanceId: string, tacheId: string, requete: Types.RequeteRetardTache) =>
    apiFetch<Types.InstanceDetail>(
      `${PRISME_CONFIG.routes.ingestion}/${instanceId}/taches/${tacheId}/retard`,
      { method: "PATCH", body: JSON.stringify(requete) },
    ),

  // PROCESSUS D'ATELIER — un seul par atelier, éclaté en tâches propres à chaque nouvelle
  // commande (voir ajouterCommande ci-dessus).
  obtenirProcessus: (instanceId: string) =>
    apiFetch<Types.ProcessusAtelier>(`${PRISME_CONFIG.routes.ingestion}/${instanceId}/processus`),

  // Remplace le processus de l'atelier. Les commandes déjà passées ne sont jamais réécrites :
  // seules les suivantes suivent le nouveau processus.
  definirProcessus: (instanceId: string, etapes: Types.EtapeProcessus[]) =>
    apiFetch<Types.ProcessusAtelier>(`${PRISME_CONFIG.routes.ingestion}/${instanceId}/processus`, {
      method: "PUT",
      body: JSON.stringify({ etapes }),
    }),

  // Toutes les commandes de cet atelier, chacune avec son statut recalculé à la volée.
  listerCommandes: (instanceId: string) =>
    apiFetch<Types.StatutCommande[]>(`${PRISME_CONFIG.routes.ingestion}/${instanceId}/commandes`),

  // Toutes les commandes de tous les ateliers (instances) du compte authentifié — sans filtre
  // pour un admin (page Commandes, vue transverse).
  listerToutesCommandes: () =>
    apiFetch<Types.StatutCommande[]>(`${PRISME_CONFIG.routes.ingestion}/commandes`),
} as const;

// ============================================================================
// STREAMING (Server-Sent Events)
// ============================================================================

interface EvenementSSEBrut {
  type: string;
  data: string;
}

/**
 * Lecteur SSE générique — `EventSource` natif ne permet pas d'envoyer l'en-
 * tête `Authorization`, donc on lit le flux à la main via `fetch` plutôt que
 * d'utiliser l'API EventSource. Ne décode pas le JSON de `data` : chaque
 * appelant sait quel type attendre pour chaque nom d'évènement.
 */
async function* lireFluxSSE(url: string, options?: RequestInit): AsyncGenerator<EvenementSSEBrut> {
  const token = lireTokenStocke();
  const response = await fetch(`${PRISME_CONFIG.baseURL}${url}`, {
    ...options,
    headers: {
      Accept: "text/event-stream",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  });

  if (!response.ok || !response.body) {
    let detail: string | Types.ErreurValidationChamp[] | Types.ErreurDetailCodee =
      response.statusText;
    try {
      const erreur: Types.ErreurAPI = await response.json();
      detail = erreur.detail;
    } catch {
      // garder response.statusText
    }
    throw new PrismeAPIError(
      `Erreur API: ${formaterDetailErreur(detail)}`,
      response.status,
      detail,
    );
  }

  const lecteur = response.body.getReader();
  const decodeur = new TextDecoder();
  let tampon = "";

  while (true) {
    const { done, value } = await lecteur.read();
    if (done) return;
    tampon += decodeur.decode(value, { stream: true });

    let indexSeparateur: number;
    // Un évènement SSE = un bloc terminé par une ligne vide (\n\n).
    while ((indexSeparateur = tampon.indexOf("\n\n")) !== -1) {
      const bloc = tampon.slice(0, indexSeparateur);
      tampon = tampon.slice(indexSeparateur + 2);

      let type = "";
      let data = "";
      for (const ligne of bloc.split("\n")) {
        if (ligne.startsWith("event: ")) type = ligne.slice("event: ".length);
        else if (ligne.startsWith("data: ")) data = ligne.slice("data: ".length);
      }
      if (data) yield { type, data };
    }
  }
}

export interface ReponseDemarrageJob {
  job_id: string;
}

/**
 * Démarre la génération de solveur dans un job serveur indépendant de la
 * requête HTTP (POST /generation/{id}/demarrer) — le job continue même si
 * la page est rechargée ou perd le réseau. Suivre avec `suivreJobGeneration`.
 */
export function demarrerGenerationSolveur(instanceId: string): Promise<ReponseDemarrageJob> {
  return apiFetch<ReponseDemarrageJob>(
    `${PRISME_CONFIG.routes.generation}/${instanceId}/demarrer`,
    {
      method: "POST",
    },
  );
}

/**
 * Demande d'arrêt d'un job en cours (POST /generation/jobs/{id}/annuler) —
 * coopératif : le pipeline s'arrête au prochain évènement produit, pas
 * instantanément (un appel LLM déjà en cours va jusqu'à son terme). Le flux
 * SSE déjà ouvert (`suivreJobGeneration`) reçoit alors un évènement `erreur`
 * explicite ("Génération annulée par l'utilisateur"), aucun canal séparé
 * n'est nécessaire pour que l'UI le reflète.
 */
export function annulerGenerationSolveur(jobId: string): Promise<{ annule: boolean }> {
  return apiFetch<{ annule: boolean }>(`${PRISME_CONFIG.routes.generation}/jobs/${jobId}/annuler`, {
    method: "POST",
  });
}

/**
 * Jobs de génération connus du serveur (GET /generation/jobs) — pour un
 * indicateur "génération en cours" visible depuis n'importe quelle page
 * (sidebar, liste d'instances...), pas seulement celle qui a lancé le job.
 */
export function listerJobsGeneration(instanceId?: string): Promise<Types.JobGenerationInfo[]> {
  const requete = instanceId ? `?instance_id=${encodeURIComponent(instanceId)}` : "";
  return apiFetch<Types.JobGenerationInfo[]>(`${PRISME_CONFIG.routes.generation}/jobs${requete}`);
}

/**
 * KPI d'agrégat sur les générations (GET /generation/statistiques) — page Analytique,
 * calculés côté serveur depuis le stockage persisté (survit à un redémarrage, contrairement
 * à `listerJobsGeneration` qui lit la mémoire process). `agent` (déjà normalisé, ex.
 * "debugger") restreint le calcul aux générations où cet agent est intervenu — voir
 * `api/statistiques_generation.py::calculer_statistiques`.
 */
export function obtenirStatistiquesGeneration(
  agent?: string,
): Promise<Types.StatistiquesGeneration> {
  const requete = agent ? `?agent=${encodeURIComponent(agent)}` : "";
  return apiFetch<Types.StatistiquesGeneration>(
    `${PRISME_CONFIG.routes.generation}/statistiques${requete}`,
  );
}

/**
 * Historique complet et durable d'un job (GET /generation/jobs/{id}/historique) —
 * contrairement au flux SSE (mémoire process), survit à un redémarrage du serveur
 * et inclut le code candidat de chaque tentative de la boucle de réparation.
 */
export function obtenirHistoriqueJobGeneration(
  jobId: string,
): Promise<Types.HistoriqueJobGeneration> {
  return apiFetch<Types.HistoriqueJobGeneration>(
    `${PRISME_CONFIG.routes.generation}/jobs/${jobId}/historique`,
  );
}

export type EvenementGenererSolveurStream =
  | { type: "etape"; data: Types.EvenementGeneration }
  | { type: "resultat"; data: Types.ReponseGenerationSolveur };

interface EvenementErreurBrut {
  message: string;
}

/**
 * Suit un job de génération déjà démarré (GET /generation/jobs/{id}/stream) —
 * rejoue l'historique déjà produit puis continue en direct. Se reconnecter
 * (après un rechargement de page) à un job en cours ou déjà terminé donne
 * la même chronologie que si on l'avait suivi depuis le début.
 */
export async function* suivreJobGeneration(
  jobId: string,
): AsyncGenerator<EvenementGenererSolveurStream> {
  let recuUnEvenementTerminal = false;

  for await (const { type, data } of lireFluxSSE(
    `${PRISME_CONFIG.routes.generation}/jobs/${jobId}/stream`,
  )) {
    if (type === "etape") {
      yield { type: "etape", data: JSON.parse(data) as Types.EvenementGeneration };
    } else if (type === "resultat") {
      recuUnEvenementTerminal = true;
      yield { type: "resultat", data: JSON.parse(data) as Types.ReponseGenerationSolveur };
    } else if (type === "erreur") {
      recuUnEvenementTerminal = true;
      const { message } = JSON.parse(data) as EvenementErreurBrut;
      throw new PrismeAPIError(`Erreur pendant la génération : ${message}`, undefined, message);
    }
  }

  // Le flux s'est fermé sans évènement `resultat` ni `erreur` — coupure
  // réseau, redémarrage du serveur en plein milieu (le job lui-même est
  // alors perdu, en mémoire process, voir api/routes/generation.py), etc.
  // Sans ça, l'appelant verrait juste la progression s'arrêter sans savoir
  // pourquoi.
  if (!recuUnEvenementTerminal) {
    throw new PrismeAPIError(
      "Erreur réseau: le suivi de la génération a été interrompu avant la fin, sans diagnostic du serveur.",
    );
  }
}

import { useEffect, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { z } from "zod";
import {
  AlertCircle,
  CheckCircle2,
  History,
  Loader2,
  Plus,
  Sparkles,
  Timer,
  X,
  XCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PageHeader, EmptyState } from "@/components/app-page";
import { BilanLatence, MesuresAgent } from "@/components/generation/latence-appels";
import {
  useInstances,
  useLabelsInstances,
  useSolveurs,
  useJobsGeneration,
  useHistoriqueJobGeneration,
  demarrerGenerationSolveur,
  annulerGenerationSolveur,
  suivreJobGeneration,
  PrismeAPIError,
  type EvenementGeneration,
  type EvenementGenerationHistorise,
  type MesureAppelLLM,
  type ReponseGenerationSolveur,
  type RapportTestsSandbox,
  type LabelInstance,
  type InstanceInfo,
} from "@/integrations/prisme";

// Onglets persistés — un par instance ouverte sur cette page, façon onglets
// de navigateur : survivent à un rechargement (le job, lui, tourne côté
// serveur indépendamment de toute connexion, voir api/routes/generation.py).
// Seuls id/instanceId/jobId sont utiles à retenir — le reste (évènements,
// résultat) est rejoué depuis le serveur à la reconnexion.
const CLE_STOCKAGE_ONGLETS = "prisme:onglets_generation";

interface OngletStocke {
  id: string;
  instanceId: string;
  jobId: string | null;
}

// Une ligne de la chronologie : l'état de l'étape d'un agent, plus les appels au modèle qu'il a
// faits (évènements `statut: "mesure"` rattachés à sa ligne, voir `fusionnerEvenement`).
type LigneChronologie = EvenementGeneration & { mesures?: MesureAppelLLM[] };

interface OngletGeneration extends OngletStocke {
  evenements: LigneChronologie[];
  resultat: ReponseGenerationSolveur | null;
  erreur: PrismeAPIError | null;
  enCours: boolean;
}

function creerOnglet(instanceId = ""): OngletGeneration {
  return {
    id: crypto.randomUUID(),
    instanceId,
    jobId: null,
    evenements: [],
    resultat: null,
    erreur: null,
    enCours: false,
  };
}

function hydrater(stocke: OngletStocke): OngletGeneration {
  return { ...stocke, evenements: [], resultat: null, erreur: null, enCours: !!stocke.jobId };
}

function lireOngletsStockes(): OngletGeneration[] | null {
  try {
    const brut = localStorage.getItem(CLE_STOCKAGE_ONGLETS);
    if (!brut) return null;
    const stockes = JSON.parse(brut) as OngletStocke[];
    return stockes.length > 0 ? stockes.map(hydrater) : null;
  } catch {
    return null;
  }
}

function ecrireOngletsStockes(onglets: OngletGeneration[]): void {
  try {
    const minimal: OngletStocke[] = onglets.map((o) => ({
      id: o.id,
      instanceId: o.instanceId,
      jobId: o.jobId,
    }));
    localStorage.setItem(CLE_STOCKAGE_ONGLETS, JSON.stringify(minimal));
  } catch {
    // stockage indisponible (navigation privée...) — tant pis, pas de reprise possible après rechargement
  }
}

// Permet un lien direct vers cette page avec une instance déjà sélectionnée
// (ex. depuis la boîte "aucun solveur validé" de IngestionDialog) — même
// patron que ?source= sur la page Données.
const searchSchema = z.object({
  instanceId: z.string().optional(),
});

export const Route = createFileRoute("/_authenticated/solver-generator")({
  head: () => ({ meta: [{ title: "Générateur de solveurs — PRISME" }] }),
  validateSearch: searchSchema,
  component: SolverGeneratorPage,
});

function IconeStatut({ statut }: { statut: EvenementGeneration["statut"] }) {
  if (statut === "en_cours")
    return <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />;
  if (statut === "termine") return <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />;
  if (statut === "mesure") return <Timer className="h-4 w-4 shrink-0 text-muted-foreground" />;
  return <XCircle className="h-4 w-4 shrink-0 text-destructive" />;
}

function IconeOnglet({ onglet }: { onglet: OngletGeneration }) {
  if (onglet.enCours) return <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />;
  if (onglet.erreur) return <XCircle className="h-3.5 w-3.5 shrink-0 text-destructive" />;
  if (onglet.resultat) {
    return onglet.resultat.reussi ? (
      <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-primary" />
    ) : (
      <XCircle className="h-3.5 w-3.5 shrink-0 text-destructive" />
    );
  }
  return null;
}

// Liste des tests générés par l'agent Testeur, réellement exécutés dans le
// bac à sable Docker (§6.6bis) — un échec renvoie déjà au Debugger côté
// pipeline (Reviewer désactivé), ceci n'est que la trace du dernier passage.
// Partagé entre le panneau résultat immédiat et le dialogue d'historique.
function RapportTestsSandboxAffichage({ rapport }: { rapport: RapportTestsSandbox }) {
  if (rapport.erreur) {
    return <p className="text-xs text-destructive">Collecte impossible : {rapport.erreur}</p>;
  }
  return (
    <ul className="space-y-1.5">
      {rapport.tests.map((t) => (
        <li key={t.nom} className="flex items-start gap-2 text-xs">
          {t.reussi ? (
            <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
          ) : (
            <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-destructive" />
          )}
          <div>
            <span className="font-mono">{t.nom}</span>
            {t.message && <p className="mt-0.5 text-muted-foreground">{t.message}</p>}
          </div>
        </li>
      ))}
    </ul>
  );
}

// Une ligne par agent : l'évènement "termine"/"echec" remplace le "en_cours"
// du même agent plutôt que de s'empiler, pour une chronologie lisible.
// Recherche dans toute la liste, pas seulement le dernier élément : Analyste
// et Benchmarker tournent en parallèle (`generation/graph.py`, `START ->
// analyste`/`START -> benchmarker` simultanés), leurs évènements s'entrelacent
// — l'évènement "termine" de l'un peut arriver après celui de l'autre, donc
// ne plus être en dernière position au moment de la fusion. Générique pour
// être réutilisée à la fois sur le flux SSE en direct (repli élément par
// élément, voir plus bas) et sur la liste complète déjà persistée de
// `DialogHistoriqueGeneration` (repli via `reduce`, voir `fusionnerEvenements`).
//
// Une mesure (`statut: "mesure"`) ne remplace jamais une ligne : elle décrit un appel au modèle
// fait par l'agent, et s'ajoute à la **dernière** ligne de cet agent. Le nom du nœud qui l'émet
// (`debugger`) est un préfixe de celui de l'étape (`debugger (tentative 3/10)`), d'où la
// recherche par préfixe ; la plus récente est celle de la tentative en cours. Quand l'étape passe
// de "en_cours" à "termine", ses mesures déjà rattachées sont conservées.
type Fusionnable = {
  agent: string;
  statut: string;
  details?: MesureAppelLLM | null;
  mesures?: MesureAppelLLM[];
};

function remplacerA<T>(liste: T[], index: number, element: T): T[] {
  return [...liste.slice(0, index), element, ...liste.slice(index + 1)];
}

function fusionnerEvenement<T extends Fusionnable>(precedents: T[], nouveau: T): T[] {
  if (nouveau.statut === "mesure") {
    let index = -1;
    for (let i = precedents.length - 1; i >= 0; i--) {
      const e = precedents[i];
      if (
        e.statut !== "mesure" &&
        (e.agent === nouveau.agent || e.agent.startsWith(`${nouveau.agent} `))
      ) {
        index = i;
        break;
      }
    }
    if (index === -1 || !nouveau.details) return [...precedents, nouveau];
    const ligne = precedents[index];
    return remplacerA(precedents, index, {
      ...ligne,
      mesures: [...(ligne.mesures ?? []), nouveau.details],
    });
  }
  const index = precedents.findIndex((e) => e.agent === nouveau.agent);
  if (index === -1) {
    return [...precedents, nouveau];
  }
  return remplacerA(precedents, index, { ...nouveau, mesures: precedents[index].mesures });
}

// Toutes les mesures d'une chronologie déjà fusionnée — rattachées ou restées orphelines.
function mesuresDe(lignes: Fusionnable[]): MesureAppelLLM[] {
  return lignes.flatMap((l) =>
    l.statut === "mesure" ? (l.details ? [l.details] : []) : (l.mesures ?? []),
  );
}

function fusionnerEvenements<T extends Fusionnable>(bruts: T[]): T[] {
  return bruts.reduce<T[]>((acc, e) => fusionnerEvenement(acc, e), []);
}

function SolverGeneratorPage() {
  const { instanceId: instanceIdDepuisUrl } = Route.useSearch();
  const { data: instances, isLoading } = useInstances();
  const { data: solveurs } = useSolveurs();
  const { data: jobsGeneration } = useJobsGeneration();

  const [onglets, setOnglets] = useState<OngletGeneration[]>(
    () => lireOngletsStockes() ?? [creerOnglet()],
  );
  const [ongletActifId, setOngletActifId] = useState<string>(onglets[0].id);

  // "Nom de la source + rang" pour ne plus afficher que des UUID bruts
  // illisibles — même hook que la page Instances.
  const labelParInstance = useLabelsInstances();

  // Un solveur ne sert que l'instance qui l'a fait générer (plus de partage par signature entre
  // instances) — indicateur "a déjà un solveur" basé directement sur instance_id.
  const instancesAvecSolveur = new Set(
    (solveurs ?? []).map((s) => s.instance_id).filter((id): id is string => id !== null),
  );
  const instancesEnGeneration = new Set(
    (jobsGeneration ?? []).filter((j) => !j.termine).map((j) => j.instance_id),
  );
  const instancesTriees = [...(instances ?? [])].sort((a, b) => {
    const aEn = instancesAvecSolveur.has(a.instance_id) ? 1 : 0;
    const bEn = instancesAvecSolveur.has(b.instance_id) ? 1 : 0;
    return aEn - bEn;
  });

  function mettreAJourOnglet(
    id: string,
    patch: Partial<OngletGeneration> | ((o: OngletGeneration) => Partial<OngletGeneration>),
  ) {
    setOnglets((prev) =>
      prev.map((o) =>
        o.id === id ? { ...o, ...(typeof patch === "function" ? patch(o) : patch) } : o,
      ),
    );
  }

  // Persiste id/instanceId/jobId à chaque changement — c'est tout ce qu'il
  // faut pour reconstruire les onglets après un rechargement.
  useEffect(() => {
    ecrireOngletsStockes(onglets);
  }, [onglets]);

  // Évite une double reprise en StrictMode (l'effet de montage tourne deux
  // fois en dev) — une seule reconnexion par onglet et par montage réel.
  const dejaRepris = useRef(false);

  async function suivre(ongletId: string, jobId: string) {
    mettreAJourOnglet(ongletId, { jobId, enCours: true });
    try {
      for await (const item of suivreJobGeneration(jobId)) {
        if (item.type === "etape") {
          mettreAJourOnglet(ongletId, (o) => ({
            evenements: fusionnerEvenement(o.evenements, item.data),
          }));
        } else {
          mettreAJourOnglet(ongletId, { resultat: item.data });
        }
      }
    } catch (e) {
      mettreAJourOnglet(ongletId, { erreur: e as PrismeAPIError });
    } finally {
      mettreAJourOnglet(ongletId, { enCours: false });
    }
  }

  // Au montage : reconnecter chaque onglet qui avait un job en cours.
  useEffect(() => {
    if (dejaRepris.current) return;
    dejaRepris.current = true;
    onglets.forEach((o) => {
      if (o.jobId) suivre(o.id, o.jobId);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function lancer(ongletId: string) {
    const onglet = onglets.find((o) => o.id === ongletId);
    if (!onglet || !onglet.instanceId || onglet.enCours) return;
    mettreAJourOnglet(ongletId, { evenements: [], resultat: null, erreur: null, enCours: true });
    try {
      const { job_id } = await demarrerGenerationSolveur(onglet.instanceId);
      await suivre(ongletId, job_id);
    } catch (e) {
      mettreAJourOnglet(ongletId, { erreur: e as PrismeAPIError, enCours: false });
    }
  }

  // Demande d'arrêt coopérative (voir client.ts::annulerGenerationSolveur) — ne touche pas
  // `onglet` ici : le flux SSE déjà ouvert par `suivre` reçoit l'évènement `erreur` que le
  // serveur produit une fois le job réellement arrêté, et met `enCours`/`erreur` à jour lui-même.
  async function arreter(ongletId: string) {
    const onglet = onglets.find((o) => o.id === ongletId);
    if (!onglet?.jobId) return;
    try {
      await annulerGenerationSolveur(onglet.jobId);
    } catch {
      // best-effort — le flux SSE déjà ouvert reflète l'état réel du job de toute façon
    }
  }

  // Choisir une instance depuis le sélecteur "+" : rejoint l'onglet existant
  // si cette instance en a déjà un, sinon en crée un nouveau — c'est ça,
  // "ajouter une instance crée l'onglet".
  function ouvrirOngletPourInstance(instanceId: string) {
    const existant = onglets.find((o) => o.instanceId === instanceId);
    if (existant) {
      setOngletActifId(existant.id);
      return;
    }
    const nouveau = creerOnglet(instanceId);
    setOnglets((prev) => [...prev, nouveau]);
    setOngletActifId(nouveau.id);
  }

  // Lien direct depuis l'extérieur (?instanceId=...) : ouvre l'onglet une
  // seule fois au montage — une ref plutôt qu'un simple `useEffect([])` pour
  // survivre au double-montage React 18 StrictMode en dev sans ouvrir
  // l'onglet deux fois (même motif que `dejaRepris` plus haut).
  const ongletDepuisUrlOuvert = useRef(false);
  useEffect(() => {
    if (!instanceIdDepuisUrl || ongletDepuisUrlOuvert.current) return;
    ongletDepuisUrlOuvert.current = true;
    ouvrirOngletPourInstance(instanceIdDepuisUrl);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- une seule fois par montage, voir commentaire
  }, [instanceIdDepuisUrl]);

  function fermerOnglet(id: string) {
    setOnglets((prev) => {
      const reste = prev.filter((o) => o.id !== id);
      const suivant = reste.length > 0 ? reste : [creerOnglet()];
      if (id === ongletActifId) {
        setOngletActifId(suivant[suivant.length - 1].id);
      }
      return suivant;
    });
  }

  const ongletActif = onglets.find((o) => o.id === ongletActifId) ?? onglets[0];

  return (
    <>
      <PageHeader
        title="Générateur de solveurs"
        desc="Pipeline multi-agents avec boucle de réparation bornée (jusqu'à 10 tentatives, Reviewer et Debugger corrigeant le code entre chaque essai), suivi en direct agent par agent — un onglet par instance, comme un navigateur : chacun garde sa progression, même après un rechargement de page."
      />

      <Tabs value={ongletActifId} onValueChange={setOngletActifId}>
        <div className="mb-4 flex items-center gap-2 overflow-x-auto pb-1">
          <TabsList className="h-auto flex-nowrap gap-1 bg-transparent p-0">
            {onglets.map((o) => (
              <TabsTrigger
                key={o.id}
                value={o.id}
                className="group relative gap-2 pr-7 data-[state=active]:bg-muted"
              >
                <IconeOnglet onglet={o} />
                <span className="max-w-[9rem] truncate">
                  {o.instanceId
                    ? (labelParInstance.get(o.instanceId)?.label ?? o.instanceId)
                    : "Nouvel onglet"}
                </span>
                <span
                  role="button"
                  aria-label="Fermer l'onglet"
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-0.5 opacity-0 hover:bg-border group-hover:opacity-100"
                  onClick={(e) => {
                    e.stopPropagation();
                    fermerOnglet(o.id);
                  }}
                >
                  <X className="h-3 w-3" />
                </span>
              </TabsTrigger>
            ))}
          </TabsList>

          <Select value="" onValueChange={ouvrirOngletPourInstance}>
            <SelectTrigger
              className="w-9 shrink-0 justify-center px-0 [&>svg]:hidden"
              aria-label="Nouvel onglet pour une instance"
            >
              <Plus className="h-4 w-4" />
            </SelectTrigger>
            <SelectContent>
              {instancesTriees.map((i) => {
                const label = labelParInstance.get(i.instance_id)?.label;
                const aDejaUnSolveur = instancesAvecSolveur.has(i.instance_id);
                const enGeneration = instancesEnGeneration.has(i.instance_id);
                return (
                  <SelectItem key={i.instance_id} value={i.instance_id}>
                    <span className="flex min-w-0 items-center gap-2">
                      {enGeneration ? (
                        <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
                      ) : aDejaUnSolveur ? (
                        <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-primary" />
                      ) : (
                        <span className="h-3.5 w-3.5 shrink-0" />
                      )}
                      <span className="truncate">
                        {label ?? <span className="font-mono text-xs">{i.instance_id}</span>} —{" "}
                        {i.client_id} ({i.structure_contraintes})
                        {enGeneration && " · génération en cours"}
                      </span>
                    </span>
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
        </div>

        {onglets.map((o) => (
          <TabsContent key={o.id} value={o.id} className="mt-0 space-y-4">
            <ContenuOnglet
              onglet={o}
              instances={instances}
              instancesLoading={isLoading}
              labelParInstance={labelParInstance}
              instancesAvecSolveur={instancesAvecSolveur}
              instancesEnGeneration={instancesEnGeneration}
              onChangerInstance={(instanceId) => mettreAJourOnglet(o.id, { instanceId })}
              onLancer={() => lancer(o.id)}
              onArreter={() => arreter(o.id)}
            />
          </TabsContent>
        ))}
      </Tabs>
    </>
  );
}

function ContenuOnglet({
  onglet,
  instances,
  instancesLoading,
  labelParInstance,
  instancesAvecSolveur,
  instancesEnGeneration,
  onChangerInstance,
  onLancer,
  onArreter,
}: {
  onglet: OngletGeneration;
  instances: InstanceInfo[] | undefined;
  instancesLoading: boolean;
  labelParInstance: Map<string, LabelInstance>;
  instancesAvecSolveur: Set<string>;
  instancesEnGeneration: Set<string>;
  onChangerInstance: (instanceId: string) => void;
  onLancer: () => void;
  onArreter: () => void;
}) {
  // Verrouillé dès qu'une génération a été lancée dans cet onglet — changer
  // d'instance en cours de route n'a pas de sens, on ouvre un autre onglet.
  const verrouille = onglet.enCours || !!onglet.jobId || !!onglet.resultat;
  const [historiqueOuvert, setHistoriqueOuvert] = useState(false);
  // Certaines erreurs (ex. réponse d'agent non conforme au schéma) embarquent
  // le JSON brut reçu du LLM — bien trop long pour le bandeau d'erreur en ligne.
  const [erreurDetailOuverte, setErreurDetailOuverte] = useState(false);
  const erreurLongue = (onglet.erreur?.message.length ?? 0) > 200;
  // Désactive le bouton dès le clic (évite un double envoi) — se réinitialise tout seul
  // quand `onglet.enCours` repasse à faux et que le bouton disparaît avec lui.
  const [arretDemande, setArretDemande] = useState(false);
  function gererArret() {
    setArretDemande(true);
    onArreter();
  }

  return (
    <div className="space-y-4">
      <div className="glass flex flex-col gap-4 rounded-2xl p-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0 flex-1">
          <Label htmlFor={`instance_${onglet.id}`}>Instance</Label>
          {!instancesLoading && instances && instances.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">
              Aucune instance disponible — ingérez-en une d'abord depuis la page Instances.
            </p>
          ) : (
            <Select
              value={onglet.instanceId}
              onValueChange={onChangerInstance}
              disabled={verrouille}
            >
              <SelectTrigger id={`instance_${onglet.id}`} className="mt-2 w-full sm:w-96">
                <SelectValue placeholder="Choisir une instance..." />
              </SelectTrigger>
              <SelectContent>
                {(instances ?? []).map((i) => {
                  const label = labelParInstance.get(i.instance_id)?.label;
                  const aDejaUnSolveur = instancesAvecSolveur.has(i.instance_id);
                  const enGeneration = instancesEnGeneration.has(i.instance_id);
                  return (
                    <SelectItem key={i.instance_id} value={i.instance_id}>
                      <span className="flex min-w-0 items-center gap-2">
                        {enGeneration ? (
                          <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />
                        ) : aDejaUnSolveur ? (
                          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-primary" />
                        ) : (
                          <span className="h-3.5 w-3.5 shrink-0" />
                        )}
                        <span className="truncate">
                          {label ?? <span className="font-mono text-xs">{i.instance_id}</span>} —{" "}
                          {i.client_id} ({i.structure_contraintes})
                          {enGeneration && " · génération en cours"}
                        </span>
                      </span>
                    </SelectItem>
                  );
                })}
              </SelectContent>
            </Select>
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            <CheckCircle2 className="mr-1 inline h-3 w-3 text-primary" />= cette instance a déjà son
            propre solveur généré. Un solveur ne sert que l'instance pour laquelle il a été généré,
            jamais partagé avec une autre instance même de structure/objectifs identiques — voir
            l'onglet Solveurs d'une instance pour le détail.
          </p>
        </div>
        <Button
          className="shrink-0 bg-gradient-to-r from-primary to-accent"
          onClick={onLancer}
          disabled={!onglet.instanceId || verrouille}
        >
          {onglet.enCours ? "Génération en cours..." : "Lancer la génération"}
        </Button>
      </div>

      {onglet.enCours && onglet.evenements.length === 0 && !onglet.resultat && (
        <div className="glass flex items-center gap-3 rounded-2xl p-6">
          <Loader2 className="h-5 w-5 shrink-0 animate-spin text-primary" />
          <span className="text-sm text-muted-foreground">
            Connexion à la génération en cours...
          </span>
        </div>
      )}

      {onglet.evenements.length > 0 && (
        <div className="glass rounded-2xl p-6">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h4 className="text-sm font-semibold">Progression en temps réel</h4>
            <div className="flex items-center gap-2">
              {onglet.enCours && onglet.jobId && (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5 text-destructive hover:text-destructive"
                  onClick={gererArret}
                  disabled={arretDemande}
                >
                  <XCircle className="h-3.5 w-3.5" />
                  {arretDemande ? "Arrêt demandé..." : "Arrêter la génération"}
                </Button>
              )}
              {onglet.jobId && (
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-1.5"
                  onClick={() => setHistoriqueOuvert(true)}
                >
                  <History className="h-3.5 w-3.5" /> Voir le raisonnement complet
                </Button>
              )}
            </div>
          </div>
          <p className="mb-3 text-xs text-muted-foreground">
            Cliquez sur "Voir le raisonnement complet" pour consulter les détails de chaque agent
            (spécification de l'Analyste, choix du Benchmarker, plan de l'Architecte, code généré,
            etc.)
          </p>
          <BilanLatence mesures={mesuresDe(onglet.evenements)} />
          <ul className="space-y-2">
            {onglet.evenements.map((e, i) => (
              <li
                key={i}
                className="flex items-start gap-3 rounded-lg border border-border/50 p-3 text-sm"
              >
                <IconeStatut statut={e.statut} />
                <div className="min-w-0 flex-1">
                  <div className="font-medium capitalize">{e.agent}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">{e.resume}</div>
                  {e.mesures && <MesuresAgent mesures={e.mesures} />}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {onglet.erreur && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          <div className="flex items-center gap-2 font-medium">
            <AlertCircle className="h-4 w-4" /> Échec de la requête
          </div>
          <p className={erreurLongue ? "mt-1 line-clamp-3" : "mt-1"}>{onglet.erreur.message}</p>
          {erreurLongue && (
            <Button
              variant="outline"
              size="sm"
              className="mt-2 gap-1.5"
              onClick={() => setErreurDetailOuverte(true)}
            >
              Voir plus
            </Button>
          )}
        </div>
      )}

      {onglet.resultat && (
        <div
          className={`glass rounded-2xl p-6 ${onglet.resultat.reussi ? "border border-primary/40" : "border border-destructive/40"}`}
        >
          {onglet.resultat.reussi ? (
            <>
              <div className="flex items-center gap-2 font-medium text-primary">
                <CheckCircle2 className="h-4 w-4" /> Solveur généré et enregistré
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Réussi en {onglet.resultat.nombre_tentatives} tentative
                {onglet.resultat.nombre_tentatives > 1 ? "s" : ""}.
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <span className="text-muted-foreground">id_solveur :</span>
                <Badge variant="secondary" className="font-mono text-xs">
                  {onglet.resultat.id_solveur}
                </Badge>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <span className="text-muted-foreground">structure / objectifs :</span>
                <Badge variant="outline" className="font-mono text-xs">
                  {onglet.resultat.structure_contraintes}
                </Badge>
                <Badge variant="outline" className="font-mono text-xs">
                  {onglet.resultat.signature_objectifs}
                </Badge>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                <span className="text-muted-foreground">algorithme :</span>
                <Badge variant="outline" className="font-mono text-xs">
                  {onglet.resultat.algorithme}
                </Badge>
              </div>
              {onglet.resultat.algorithme_raison && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {onglet.resultat.algorithme_raison}
                </p>
              )}
              {onglet.resultat.rapport_tests_sandbox && (
                <div className="mt-3 border-t border-border/50 pt-3">
                  <h5 className="mb-1.5 text-xs font-semibold">
                    🧫 Tests sandbox (exécution réelle)
                  </h5>
                  <RapportTestsSandboxAffichage rapport={onglet.resultat.rapport_tests_sandbox} />
                </div>
              )}
            </>
          ) : (
            <>
              <div className="flex items-center gap-2 font-medium text-destructive">
                <AlertCircle className="h-4 w-4" /> Échec après {onglet.resultat.nombre_tentatives}{" "}
                tentative
                {onglet.resultat.nombre_tentatives > 1 ? "s" : ""} — rien n'a été enregistré
              </div>
              {onglet.resultat.algorithme && (
                <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-muted-foreground">algorithme tenté :</span>
                  <Badge variant="outline" className="font-mono text-xs">
                    {onglet.resultat.algorithme}
                  </Badge>
                </div>
              )}
              {onglet.resultat.erreur && (
                <p className="mt-2 text-sm text-muted-foreground">{onglet.resultat.erreur}</p>
              )}
              {onglet.resultat.echecs_cascade.length > 0 && (
                <ul className="mt-3 space-y-2">
                  {onglet.resultat.echecs_cascade.map((e, i) => (
                    <li key={i} className="rounded-md border border-border/50 p-2 text-sm">
                      <div className="font-medium">
                        {e.nom}
                        {e.brique_en_echec && (
                          <Badge variant="outline" className="ml-2 text-xs">
                            {e.brique_en_echec}
                          </Badge>
                        )}
                      </div>
                      <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">
                        {e.details.map((d, j) => (
                          <li key={j}>{d}</li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>
              )}
              {onglet.resultat.rapport_tests_sandbox && (
                <div className="mt-3 border-t border-border/50 pt-3">
                  <h5 className="mb-1.5 text-xs font-semibold">
                    🧫 Tests sandbox (exécution réelle)
                  </h5>
                  <RapportTestsSandboxAffichage rapport={onglet.resultat.rapport_tests_sandbox} />
                </div>
              )}
            </>
          )}
        </div>
      )}

      {!onglet.enCours && onglet.evenements.length === 0 && !onglet.resultat && !onglet.erreur && (
        <EmptyState
          icon={Sparkles}
          title="Aucune génération lancée"
          desc="Choisissez une instance et lancez la génération pour voir chaque agent progresser en direct."
        />
      )}

      {onglet.jobId && (
        <DialogHistoriqueGeneration
          jobId={onglet.jobId}
          open={historiqueOuvert}
          onOpenChange={setHistoriqueOuvert}
        />
      )}

      {onglet.erreur && (
        <Dialog open={erreurDetailOuverte} onOpenChange={setErreurDetailOuverte}>
          <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Détail de l'erreur</DialogTitle>
            </DialogHeader>
            <pre className="whitespace-pre-wrap wrap-break-word rounded-lg bg-muted/50 p-3 font-mono text-xs text-foreground">
              {onglet.erreur.message}
            </pre>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

function DialogHistoriqueGeneration({
  jobId,
  open,
  onOpenChange,
}: {
  jobId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  // N'interroge le serveur que dialogue ouvert — pas de sens de charger tout
  // le code candidat de chaque tentative tant que personne ne le regarde.
  const { data: historique, isLoading, error } = useHistoriqueJobGeneration(open ? jobId : null);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Historique complet de la génération</DialogTitle>
        </DialogHeader>

        {isLoading && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Chargement de l'historique...
          </div>
        )}

        {error && (
          <p className="text-sm text-destructive">
            Impossible de charger l'historique : {(error as PrismeAPIError).message}
          </p>
        )}

        {historique && (
          <div className="space-y-6">
            {historique.specification && (
              <div>
                <h4 className="mb-2 text-sm font-semibold">📋 Spécification (Analyste)</h4>
                <div className="rounded-lg border border-border/50 bg-muted/30 p-3">
                  <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">
                    {historique.specification}
                  </pre>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Analyse du problème par l'agent Analyste
                </p>
              </div>
            )}

            {historique.algorithme && (
              <div>
                <h4 className="mb-2 text-sm font-semibold">
                  🎯 Algorithme recommandé (Benchmarker)
                </h4>
                <Badge variant="outline" className="font-mono text-xs">
                  {historique.algorithme}
                </Badge>
                {historique.algorithme_raison && (
                  <p className="mt-2 text-xs text-muted-foreground">
                    {historique.algorithme_raison}
                  </p>
                )}
                {historique.algorithme_parametres &&
                  Object.keys(historique.algorithme_parametres).length > 0 && (
                    <div className="mt-2">
                      <p className="text-xs font-medium text-muted-foreground">Paramètres :</p>
                      <pre className="mt-1 rounded-md bg-muted/50 p-2 text-xs">
                        {JSON.stringify(historique.algorithme_parametres, null, 2)}
                      </pre>
                    </div>
                  )}
              </div>
            )}

            {historique.plan_technique && (
              <div>
                <h4 className="mb-2 text-sm font-semibold">🏗️ Plan technique (Architecte)</h4>
                <div className="rounded-lg border border-border/50 bg-muted/30 p-3">
                  <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">
                    {historique.plan_technique}
                  </pre>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Architecture proposée par l'agent Architecte
                </p>
              </div>
            )}

            {historique.code_genere && (
              <div>
                <h4 className="mb-2 text-sm font-semibold">💻 Code initial (Développeur)</h4>
                <div className="rounded-lg border border-border/50 bg-muted/30 p-3">
                  <pre className="max-h-80 overflow-auto text-xs">
                    <code>{historique.code_genere}</code>
                  </pre>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Première implémentation avant la boucle de réparation
                </p>
              </div>
            )}

            {historique.tests_generes && (
              <div>
                <h4 className="mb-2 text-sm font-semibold">🧪 Tests générés (Testeur)</h4>
                <div className="rounded-lg border border-border/50 bg-muted/30 p-3">
                  <pre className="max-h-64 overflow-auto text-xs">
                    <code>{historique.tests_generes}</code>
                  </pre>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Suite de tests proposée par l'agent Testeur
                </p>
              </div>
            )}

            {historique.rapport_tests_sandbox && (
              <div>
                <h4 className="mb-2 text-sm font-semibold">🧫 Tests sandbox (exécution réelle)</h4>
                <RapportTestsSandboxAffichage rapport={historique.rapport_tests_sandbox} />
                <p className="mt-1 text-xs text-muted-foreground">
                  Exécution réelle des tests ci-dessus dans le bac à sable Docker — un échec renvoie
                  déjà au Debugger (voir Événements et Tentatives ci-dessous), ceci est la trace du
                  dernier passage
                </p>
              </div>
            )}

            <div>
              {(() => {
                const evenementsFusionnes = fusionnerEvenements<
                  EvenementGenerationHistorise & { mesures?: MesureAppelLLM[] }
                >(historique.evenements);
                return (
                  <>
                    <h4 className="mb-2 text-sm font-semibold">
                      Évènements ({evenementsFusionnes.filter((e) => e.statut !== "mesure").length})
                    </h4>
                    <BilanLatence mesures={mesuresDe(evenementsFusionnes)} />
                    <ul className="space-y-1.5">
                      {evenementsFusionnes.map((e) => (
                        <li key={e.ordre} className="flex items-start gap-2 text-xs">
                          <IconeStatut statut={e.statut} />
                          <div className="min-w-0 flex-1">
                            <span className="font-medium capitalize">{e.agent}</span>{" "}
                            <span className="text-muted-foreground">{e.resume}</span>
                            {e.mesures && <MesuresAgent mesures={e.mesures} />}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </>
                );
              })()}
            </div>

            <div>
              <h4 className="mb-2 text-sm font-semibold">
                Tentatives de réparation ({historique.tentatives.length})
              </h4>
              {historique.tentatives.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Aucune tentative enregistrée — le pipeline n'a pas encore atteint la boucle de
                  réparation, ou n'a pas eu besoin de plus d'un essai.
                </p>
              ) : (
                <Accordion type="single" collapsible className="w-full">
                  {historique.tentatives.map((t) => (
                    <AccordionItem key={t.numero} value={`tentative-${t.numero}`}>
                      <AccordionTrigger className="text-sm">
                        <span className="flex items-center gap-2">
                          {t.reussi ? (
                            <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />
                          ) : (
                            <XCircle className="h-4 w-4 shrink-0 text-destructive" />
                          )}
                          Tentative {t.numero}
                        </span>
                      </AccordionTrigger>
                      <AccordionContent className="space-y-3">
                        {t.erreur_execution && (
                          <p className="text-xs text-destructive">
                            Erreur d'exécution : {t.erreur_execution}
                          </p>
                        )}
                        {t.validation_statique_valide === false &&
                          t.validation_statique_violations.length > 0 && (
                            <div className="text-xs text-destructive">
                              Validation statique rejetée :
                              <ul className="mt-1 list-disc space-y-0.5 pl-5">
                                {t.validation_statique_violations.map((v, i) => (
                                  <li key={i}>{v}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                        {t.revue_approuve !== null && (
                          <p className="text-xs">
                            Revue :{" "}
                            <Badge variant={t.revue_approuve ? "secondary" : "outline"}>
                              {t.revue_approuve ? "approuvée" : "problèmes relevés"}
                            </Badge>
                          </p>
                        )}
                        {t.revue_problemes.length > 0 && (
                          <ul className="list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">
                            {t.revue_problemes.map((p, i) => (
                              <li key={i}>{p}</li>
                            ))}
                          </ul>
                        )}
                        <pre className="max-h-64 overflow-auto rounded-lg border border-border/50 bg-muted/30 p-3 text-xs">
                          <code>{t.code_candidat}</code>
                        </pre>
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              )}
            </div>

            {historique.code_final && (
              <div>
                <h4 className="mb-2 text-sm font-semibold">Code final retenu</h4>
                <pre className="max-h-80 overflow-auto rounded-lg border border-primary/30 bg-muted/30 p-3 text-xs">
                  <code>{historique.code_final}</code>
                </pre>
              </div>
            )}

            {historique.documentation && (
              <div>
                <h4 className="mb-2 text-sm font-semibold">📚 Documentation</h4>
                <div className="rounded-lg border border-border/50 bg-muted/30 p-3">
                  <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">
                    {historique.documentation}
                  </pre>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Documentation produite par l'agent Documentation
                </p>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

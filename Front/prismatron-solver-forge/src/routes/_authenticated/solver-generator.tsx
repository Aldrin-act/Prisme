import { useEffect, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQueries } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  History,
  Loader2,
  Plus,
  Sparkles,
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
import {
  prismeKeys,
  prismeClient,
  useInstances,
  useProjets,
  useSolveurs,
  useJobsGeneration,
  useHistoriqueJobGeneration,
  demarrerGenerationSolveur,
  suivreJobGeneration,
  PrismeAPIError,
  type EvenementGeneration,
  type ReponseGenerationSolveur,
  type ProjetDetail,
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

interface OngletGeneration extends OngletStocke {
  evenements: EvenementGeneration[];
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

export const Route = createFileRoute("/_authenticated/solver-generator")({
  head: () => ({ meta: [{ title: "Générateur de solveurs — PRISME" }] }),
  component: SolverGeneratorPage,
});

function IconeStatut({ statut }: { statut: EvenementGeneration["statut"] }) {
  if (statut === "en_cours")
    return <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />;
  if (statut === "termine") return <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />;
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

// Une ligne par agent : l'évènement "termine"/"echec" remplace le "en_cours"
// du même agent plutôt que de s'empiler, pour une chronologie lisible.
function fusionnerEvenement(
  precedents: EvenementGeneration[],
  nouveau: EvenementGeneration,
): EvenementGeneration[] {
  const dernier = precedents[precedents.length - 1];
  if (dernier && dernier.agent === nouveau.agent) {
    return [...precedents.slice(0, -1), nouveau];
  }
  return [...precedents, nouveau];
}

function SolverGeneratorPage() {
  const { data: instances, isLoading } = useInstances();
  const { data: projets } = useProjets();
  const { data: solveurs } = useSolveurs();
  const { data: jobsGeneration } = useJobsGeneration();

  const [onglets, setOnglets] = useState<OngletGeneration[]>(
    () => lireOngletsStockes() ?? [creerOnglet()],
  );
  const [ongletActifId, setOngletActifId] = useState<string>(onglets[0].id);

  // Même reconstruction "nom du projet + rang" que la page Instances, pour
  // ne plus afficher que des UUID bruts illisibles.
  const detailsProjets = useQueries({
    queries: (projets ?? []).map((projet) => ({
      queryKey: prismeKeys.projet(projet.projet_id),
      queryFn: () => prismeClient.obtenirProjet(projet.projet_id),
    })),
  });
  const labelParInstance = new Map<string, string>();
  detailsProjets.forEach((requete) => {
    const detail = requete.data as ProjetDetail | undefined;
    if (!detail) return;
    const nom = detail.nom ?? "Sans nom";
    [...detail.instances].reverse().forEach((instance, index) => {
      labelParInstance.set(instance.instance_id, `${nom}-${index + 1}`);
    });
  });

  // Approximation (client_id + structure_contraintes seulement — les
  // objectifs ne sont pas dans /supervision/instances) : suffisant pour un
  // indicateur visuel, la page Instances fait le matching exact.
  const clesAvecSolveur = new Set(
    (solveurs ?? []).map((s) => `${s.client_id}::${s.structure_contraintes}`),
  );
  const instancesEnGeneration = new Set(
    (jobsGeneration ?? []).filter((j) => !j.termine).map((j) => j.instance_id),
  );
  const instancesTriees = [...(instances ?? [])].sort((a, b) => {
    const aEn = clesAvecSolveur.has(`${a.client_id}::${a.structure_contraintes}`) ? 1 : 0;
    const bEn = clesAvecSolveur.has(`${b.client_id}::${b.structure_contraintes}`) ? 1 : 0;
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
                    ? (labelParInstance.get(o.instanceId) ?? o.instanceId)
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
                const label = labelParInstance.get(i.instance_id);
                const aDejaUnSolveur = clesAvecSolveur.has(
                  `${i.client_id}::${i.structure_contraintes}`,
                );
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
              clesAvecSolveur={clesAvecSolveur}
              instancesEnGeneration={instancesEnGeneration}
              onChangerInstance={(instanceId) => mettreAJourOnglet(o.id, { instanceId })}
              onLancer={() => lancer(o.id)}
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
  clesAvecSolveur,
  instancesEnGeneration,
  onChangerInstance,
  onLancer,
}: {
  onglet: OngletGeneration;
  instances: InstanceInfo[] | undefined;
  instancesLoading: boolean;
  labelParInstance: Map<string, string>;
  clesAvecSolveur: Set<string>;
  instancesEnGeneration: Set<string>;
  onChangerInstance: (instanceId: string) => void;
  onLancer: () => void;
}) {
  // Verrouillé dès qu'une génération a été lancée dans cet onglet — changer
  // d'instance en cours de route n'a pas de sens, on ouvre un autre onglet.
  const verrouille = onglet.enCours || !!onglet.jobId || !!onglet.resultat;
  const [historiqueOuvert, setHistoriqueOuvert] = useState(false);

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
                  const label = labelParInstance.get(i.instance_id);
                  const aDejaUnSolveur = clesAvecSolveur.has(
                    `${i.client_id}::${i.structure_contraintes}`,
                  );
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
            <CheckCircle2 className="mr-1 inline h-3 w-3 text-primary" />= un solveur existe déjà
            pour ce client et cette structure de contraintes (approximatif, sans les objectifs —
            voir l'onglet Solveurs d'une instance pour le matching exact). Le code généré est
            générique à tout le DSL, pas spécifique aux données de cette instance — elle sert
            seulement à déterminer sous quelle clé (client, structure des contraintes, objectifs)
            enregistrer le solveur, pour que <code className="font-mono">/execution</code> le
            retrouve ensuite.
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
            <h4 className="text-sm font-semibold">Progression</h4>
            {onglet.jobId && (
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                onClick={() => setHistoriqueOuvert(true)}
              >
                <History className="h-3.5 w-3.5" /> Historique complet
              </Button>
            )}
          </div>
          <ul className="space-y-2">
            {onglet.evenements.map((e, i) => (
              <li
                key={i}
                className="flex items-start gap-3 rounded-lg border border-border/50 p-3 text-sm"
              >
                <IconeStatut statut={e.statut} />
                <div className="min-w-0">
                  <div className="font-medium capitalize">{e.agent}</div>
                  <div className="truncate text-xs text-muted-foreground">{e.resume}</div>
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
          <p className="mt-1">{onglet.erreur.message}</p>
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
                <span className="text-muted-foreground">clé de matching :</span>
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
                <p className="mt-1 text-xs text-muted-foreground">{onglet.resultat.algorithme_raison}</p>
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
            {historique.algorithme && (
              <div>
                <h4 className="mb-2 text-sm font-semibold">Algorithme recommandé</h4>
                <Badge variant="outline" className="font-mono text-xs">
                  {historique.algorithme}
                </Badge>
                {historique.algorithme_raison && (
                  <p className="mt-1 text-xs text-muted-foreground">{historique.algorithme_raison}</p>
                )}
              </div>
            )}

            <div>
              <h4 className="mb-2 text-sm font-semibold">Évènements ({historique.evenements.length})</h4>
              <ul className="space-y-1.5">
                {historique.evenements.map((e) => (
                  <li key={e.ordre} className="flex items-start gap-2 text-xs">
                    <IconeStatut statut={e.statut} />
                    <span className="font-medium capitalize">{e.agent}</span>
                    <span className="text-muted-foreground">{e.resume}</span>
                  </li>
                ))}
              </ul>
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
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

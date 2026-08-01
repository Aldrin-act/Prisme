import { useEffect, useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import readXlsxFile from "read-excel-file/browser";
import { z } from "zod";
import {
  ArrowRightLeft,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Download,
  FolderOpen,
  Lightbulb,
  Loader2,
  Plus,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { PageHeader, EmptyState } from "@/components/app-page";
import {
  prismeKeys,
  useCreerSource,
  useGenererInstanceDepuisSource,
  useSource,
  useSources,
  useSupprimerSource,
  PrismeAPIError,
  type Justification,
} from "@/integrations/prisme";
import { useAuth } from "@/integrations/prisme/auth";

const searchSchema = z.object({
  source: z.string().optional(),
});

export const Route = createFileRoute("/_authenticated/donnees")({
  head: () => ({ meta: [{ title: "Données — PRISME" }] }),
  validateSearch: searchSchema,
  component: DonneesPage,
});

function DonneesPage() {
  const { source } = Route.useSearch();
  const [tab, setTab] = useState<"actif" | "historique">("actif");
  // Pré-rempli depuis l'URL (?source=<id>) — permet un lien direct depuis la
  // page Instances vers le détail de la source qui a généré une instance donnée.
  const [sourceActiveId, setSourceActiveId] = useState<string | null>(source ?? null);

  function ouvrirSource(sourceId: string) {
    setSourceActiveId(sourceId);
    setTab("actif");
  }

  return (
    <>
      <PageHeader
        title="Données"
        desc="Enregistrez des données brutes provenant d'un ERP sans adaptateur dédié — un agent de compréhension propose une traduction en instance T-R-C-O, toujours revalidée par le même garde-fou que les autres canaux d'ingestion. Un même enregistrement peut être reconverti plusieurs fois, sans jamais recoller les données."
      />

      <Tabs value={tab} onValueChange={(v) => setTab(v as typeof tab)}>
        <TabsList>
          <TabsTrigger value="actif">Source en cours</TabsTrigger>
          <TabsTrigger value="historique">Historique</TabsTrigger>
        </TabsList>

        <TabsContent value="actif" className="max-w-3xl">
          {sourceActiveId ? (
            <SourceActivePanel sourceId={sourceActiveId} onNouveau={() => setSourceActiveId(null)} />
          ) : (
            <FormulaireNouvelleSource onCree={setSourceActiveId} />
          )}
        </TabsContent>

        <TabsContent value="historique">
          <ListeSources onOuvrir={ouvrirSource} />
        </TabsContent>
      </Tabs>
    </>
  );
}

type FormatFichierBrut = "csv" | "json" | "excel";

const ACCEPT_PAR_FORMAT: Record<FormatFichierBrut, string> = {
  csv: ".csv,text/csv",
  json: ".json,application/json",
  excel: ".xlsx",
};

// CSV/Excel : un export ERP tient rarement en un seul fichier (tâches,
// ressources, contraintes sont souvent des tables séparées) — JSON reste à
// un seul fichier, une instance déjà structurée n'a pas besoin d'être scindée.
const NB_FICHIERS_PAR_FORMAT: Record<FormatFichierBrut, number> = { csv: 3, json: 1, excel: 3 };

// Gabarits d'exemple téléchargeables (Front/prismatron-solver-forge/public/gabarits/,
// voir scripts/generer_gabarit_csv.py et scripts/generer_gabarit_ingestion.py pour
// la source de vérité régénérée côté backend — copie manuelle après changement).
const GABARITS_PAR_FORMAT: Record<FormatFichierBrut, { nom: string; href: string }[]> = {
  csv: [
    { nom: "taches.csv", href: "/gabarits/taches.csv" },
    { nom: "ressources.csv", href: "/gabarits/ressources.csv" },
    { nom: "contraintes.csv", href: "/gabarits/contraintes.csv" },
  ],
  json: [{ nom: "instance_exemple.json", href: "/gabarits/instance_exemple.json" }],
  excel: [{ nom: "gabarit_ingestion_trco.xlsx", href: "/gabarits/gabarit_ingestion_trco.xlsx" }],
};

// Convertit chaque feuille en un bloc texte lisible (comma-séparé) — l'agent
// de compréhension attend du texte brut, jamais un classeur binaire tel quel.
function feuillesExcelEnTexte(feuilles: Awaited<ReturnType<typeof readXlsxFile>>): string {
  return feuilles
    .map(
      ({ sheet, data }) =>
        `# ${sheet}\n` + data.map((ligne) => ligne.map((cellule) => cellule ?? "").join(",")).join("\n"),
    )
    .join("\n\n");
}

function FormulaireNouvelleSource({ onCree }: { onCree: (sourceId: string) => void }) {
  const creer = useCreerSource();
  const inputFichierRefs = [useRef<HTMLInputElement>(null), useRef<HTMLInputElement>(null), useRef<HTMLInputElement>(null)];
  const { utilisateur } = useAuth();
  const estAdmin = utilisateur?.role === "admin";

  const [clientId, setClientId] = useState(utilisateur?.client_id ?? "");
  const [nom, setNom] = useState("");
  const [donneesBrutes, setDonneesBrutes] = useState("");
  const [formatFichier, setFormatFichier] = useState<FormatFichierBrut>("csv");
  const [fichiers, setFichiers] = useState<(File | null)[]>([null, null, null]);
  const [chargementFichier, setChargementFichier] = useState(false);
  const [erreurFichier, setErreurFichier] = useState<string | null>(null);

  const erreur = creer.error as PrismeAPIError | null;

  function changerFormat(format: FormatFichierBrut) {
    setFormatFichier(format);
    setFichiers([null, null, null]);
    setErreurFichier(null);
    inputFichierRefs.forEach((ref) => {
      if (ref.current) ref.current.value = "";
    });
  }

  async function lireFichier(fichier: File): Promise<string> {
    if (formatFichier === "excel") return feuillesExcelEnTexte(await readXlsxFile(fichier));
    return fichier.text();
  }

  async function definirFichier(index: number, fichier: File | null) {
    const nouveauxFichiers = fichiers.map((f, i) => (i === index ? fichier : f));
    setFichiers(nouveauxFichiers);
    setErreurFichier(null);
    setChargementFichier(true);
    try {
      const presents = nouveauxFichiers.filter((f): f is File => f !== null);
      const contenus = await Promise.all(presents.map((f) => lireFichier(f)));
      setDonneesBrutes(
        presents.length > 1
          ? contenus.map((c, i) => `--- ${presents[i].name} ---\n${c}`).join("\n\n")
          : (contenus[0] ?? ""),
      );
    } catch {
      setErreurFichier("Fichier illisible — vérifiez qu'il correspond bien au format sélectionné ci-dessus.");
    } finally {
      setChargementFichier(false);
    }
  }

  function enregistrer() {
    creer.mutate(
      { donneesBrutes, nom: nom.trim() || undefined, clientId: estAdmin ? clientId : undefined },
      { onSuccess: (data) => onCree(data.source_id) },
    );
  }

  return (
    <div className="glass space-y-5 rounded-2xl p-6">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="client_id_donnees">Client</Label>
          <Input
            id="client_id_donnees"
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            disabled={!estAdmin}
          />
          {!estAdmin && (
            <p className="text-xs text-muted-foreground">Associé automatiquement à votre compte.</p>
          )}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="nom_source">Nom de la source (optionnel)</Label>
          <Input
            id="nom_source"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            placeholder="ex : Export ERP atelier mécanique"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="fichier_brut">Fichier de données brutes (optionnel)</Label>
        <Tabs value={formatFichier} onValueChange={(v) => changerFormat(v as FormatFichierBrut)}>
          <TabsList className="h-8">
            <TabsTrigger value="csv" className="text-xs">CSV</TabsTrigger>
            <TabsTrigger value="json" className="text-xs">JSON</TabsTrigger>
            <TabsTrigger value="excel" className="text-xs">Excel</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
          <span className="text-muted-foreground">Gabarit d'exemple :</span>
          {GABARITS_PAR_FORMAT[formatFichier].map((gabarit) => (
            <a
              key={gabarit.href}
              href={gabarit.href}
              download
              className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
            >
              <Download className="h-3 w-3" /> {gabarit.nom}
            </a>
          ))}
        </div>
        <div className="space-y-2">
          {Array.from({ length: NB_FICHIERS_PAR_FORMAT[formatFichier] }, (_, index) => (
            <Input
              key={index}
              id={index === 0 ? "fichier_brut" : undefined}
              ref={inputFichierRefs[index]}
              type="file"
              accept={ACCEPT_PAR_FORMAT[formatFichier]}
              onChange={(e) => definirFichier(index, e.target.files?.[0] ?? null)}
            />
          ))}
        </div>
        {chargementFichier && <p className="text-xs text-muted-foreground">Lecture du/des fichier(s)...</p>}
        {erreurFichier && (
          <p className="flex items-center gap-1.5 text-xs text-destructive">
            <AlertCircle className="h-3.5 w-3.5" /> {erreurFichier}
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          {NB_FICHIERS_PAR_FORMAT[formatFichier] > 1
            ? "Jusqu'à 3 fichiers — un par table si votre export en a plusieurs (tâches, ressources, contraintes...), leur contenu est concaténé ci-dessous."
            : "Charge le contenu du fichier dans le champ ci-dessous."}{" "}
          Vous pouvez aussi coller le texte directement (export CSV, JSON, tableau collé...).
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="donnees_brutes">Données brutes</Label>
        <Textarea
          id="donnees_brutes"
          value={donneesBrutes}
          onChange={(e) => setDonneesBrutes(e.target.value)}
          placeholder="Collez ici l'export brut de votre ERP (n'importe quel format texte)..."
          className="min-h-64 font-mono text-xs"
        />
      </div>

      {erreur && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <div className="flex items-center gap-2 font-medium">
            <AlertCircle className="h-4 w-4" /> Échec de l'enregistrement
          </div>
          <p className="mt-1">{erreur.message}</p>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          onClick={enregistrer}
          disabled={creer.isPending || (estAdmin && !clientId.trim()) || !donneesBrutes.trim()}
          className="bg-gradient-to-r from-primary to-accent"
        >
          <Plus className="mr-2 h-4 w-4" />
          {creer.isPending ? "Enregistrement..." : "Enregistrer la source"}
        </Button>
      </div>
    </div>
  );
}

function SourceActivePanel({ sourceId, onNouveau }: { sourceId: string; onNouveau: () => void }) {
  const queryClient = useQueryClient();
  const { data: source, isLoading } = useSource(sourceId);
  const generer = useGenererInstanceDepuisSource();
  const [dernier, setDernier] = useState<{
    instance_id: string;
    avertissements: string[];
    justifications: Justification[];
  } | null>(null);

  // État local pour maintenir l'indicateur visible même si le composant re-render
  const [generationEnCours, setGenerationEnCours] = useState(false);

  const erreur = generer.error as PrismeAPIError | null;

  function genererInstance() {
    setDernier(null);
    setGenerationEnCours(true);
    generer.mutate(sourceId, {
      onSuccess: (data) => {
        setDernier({
          instance_id: data.instance_id,
          avertissements: data.avertissements,
          justifications: data.justifications,
        });
        setGenerationEnCours(false);
        queryClient.invalidateQueries({ queryKey: prismeKeys.source(sourceId) });
        queryClient.invalidateQueries({ queryKey: prismeKeys.sources() });
        queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
      },
      onError: () => {
        setGenerationEnCours(false);
      },
    });
  }

  if (isLoading || !source) {
    return <div className="glass rounded-2xl p-6 text-sm text-muted-foreground">Chargement de la source...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="glass space-y-4 rounded-2xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Source</div>
            <h3 className="text-lg font-semibold">{source.nom || "Sans nom"}</h3>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span>{source.client_id}</span>
              <span>·</span>
              <span>{new Date(source.date_creation).toLocaleString()}</span>
              <span>·</span>
              <Badge variant="outline" className="font-mono">{source.source_id}</Badge>
            </div>
          </div>
          <Button variant="outline" onClick={onNouveau}>
            <Plus className="mr-2 h-4 w-4" /> Nouvelle source
          </Button>
        </div>

        <details className="rounded-lg border border-border/50 p-3 text-xs">
          <summary className="cursor-pointer font-medium text-muted-foreground">Voir les données brutes</summary>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-mono">{source.donnees_brutes}</pre>
        </details>

        {erreur && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <div className="flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4" /> Échec de la conversion
            </div>
            <p className="mt-1">{erreur.message}</p>
          </div>
        )}

        {dernier && dernier.avertissements.length > 0 && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            <div className="flex items-center gap-2 font-medium text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4" /> Avertissements de la dernière conversion
            </div>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-muted-foreground">
              {dernier.avertissements.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          </div>
        )}

        {dernier && dernier.justifications.length > 0 && (
          <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
            <div className="flex items-center gap-2 font-medium text-primary">
              <Lightbulb className="h-4 w-4" /> Comment les contraintes ont été choisies
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Précédences, échéances et compétences requises seulement — la compatibilité
              ressource-tâche n'est pas détaillée ici, trop nombreuse pour être justifiée une à une.
            </p>
            <ul className="mt-2 space-y-2">
              {dernier.justifications.map((j, i) => (
                <li key={i} className="rounded-md border border-border/50 p-2">
                  <div className="font-mono text-xs text-foreground">{j.contrainte}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">{j.raison}</div>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            Rejouable à volonté sur ces mêmes données brutes — chaque conversion ajoute une instance à
            l'historique ci-dessous, aucune n'est remplacée. Chaque instance générée s'exécute directement
            depuis la page Solveurs générés, sans étape supplémentaire ici.
          </p>
          <Button onClick={genererInstance} disabled={generationEnCours || generer.isPending} className="shrink-0">
            <ArrowRightLeft className="mr-2 h-4 w-4" />
            {(generationEnCours || generer.isPending) ? "Conversion en cours..." : "Générer une instance"}
          </Button>
        </div>
        {(generationEnCours || generer.isPending) && <IndicateurGeneration />}
      </div>

      <div className="glass rounded-2xl p-6">
        <h4 className="mb-3 text-sm font-semibold">Instances générées ({source.instances.length})</h4>
        {source.instances.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune instance générée pour l'instant.</p>
        ) : (
          <div className="space-y-2">
            {source.instances.map((i) => (
              <div
                key={i.instance_id}
                className="flex flex-wrap items-center gap-2 rounded-lg border border-border/50 p-2 text-sm"
              >
                <CheckCircle2 className="h-4 w-4 text-primary" />
                <Badge variant="secondary" className="font-mono text-xs">{i.instance_id}</Badge>
                <Badge variant="outline" className="font-mono text-xs">{i.structure_contraintes}</Badge>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const MESSAGES_GENERATION = [
  "Envoi des données à l'agent de compréhension...",
  "L'agent analyse la structure de vos données...",
  "Traduction en tâches, ressources et contraintes...",
  "Vérification par le garde-fou de validation...",
];

// Ni les étapes ni leur durée ne sont réelles — l'appel LLM côté serveur est
// atomique (un seul aller-retour, voir `adapters/agent_comprehension/agent.py`),
// il n'y a rien à observer entre le départ et l'arrivée. Ce chronomètre et ces
// messages qui tournent servent uniquement à ce que l'attente ne semble pas
// figée ; ils ne prétendent pas refléter un vrai avancement côté serveur.
function IndicateurGeneration() {
  const [secondes, setSecondes] = useState(0);
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const debut = Date.now();
    const timerSecondes = setInterval(() => setSecondes(Math.floor((Date.now() - debut) / 1000)), 1000);
    const timerMessage = setInterval(
      () => setMessageIndex((i) => (i + 1) % MESSAGES_GENERATION.length),
      4000,
    );
    return () => {
      clearInterval(timerSecondes);
      clearInterval(timerMessage);
    };
  }, []);

  const minutes = Math.floor(secondes / 60);
  const reste = (secondes % 60).toString().padStart(2, "0");

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border/50 bg-muted/30 p-3">
      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
      <div className="min-w-0">
        <div className="text-sm font-medium">
          Conversion en cours — {minutes}:{reste}
        </div>
        <div className="truncate text-xs text-muted-foreground">{MESSAGES_GENERATION[messageIndex]}</div>
      </div>
    </div>
  );
}

function ListeSources({ onOuvrir }: { onOuvrir: (sourceId: string) => void }) {
  const { data: sources, isLoading } = useSources();
  const queryClient = useQueryClient();
  const supprimer = useSupprimerSource();
  const [aSupprimer, setASupprimer] = useState<string | null>(null);

  const erreurSuppression = supprimer.error as PrismeAPIError | null;

  function ouvrirConfirmation(sourceId: string) {
    supprimer.reset();
    setASupprimer(sourceId);
  }

  function confirmerSuppression() {
    if (!aSupprimer) return;
    supprimer.mutate(aSupprimer, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: prismeKeys.sources() });
        setASupprimer(null);
      },
    });
  }

  if (!isLoading && sources && sources.length === 0) {
    return (
      <EmptyState
        icon={FolderOpen}
        title="Aucune source enregistrée"
        desc="Enregistrez vos premières données brutes dans l'onglet « Source en cours » pour les retrouver ici."
      />
    );
  }

  return (
    <>
      <div className="glass overflow-hidden rounded-2xl">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Source</TableHead>
              <TableHead>Client</TableHead>
              <TableHead>Créée le</TableHead>
              <TableHead>Instances générées</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sources?.map((s) => (
              <TableRow key={s.source_id}>
                <TableCell>
                  <div className="font-medium">{s.nom || "Sans nom"}</div>
                  <div className="font-mono text-xs text-muted-foreground">{s.source_id}</div>
                </TableCell>
                <TableCell>{s.client_id}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(s.date_creation).toLocaleString()}
                </TableCell>
                <TableCell>
                  <Badge variant={s.nb_instances > 0 ? "secondary" : "outline"}>{s.nb_instances}</Badge>
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="outline" onClick={() => onOuvrir(s.source_id)}>
                      <FolderOpen className="mr-2 h-3.5 w-3.5" /> Ouvrir
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Supprimer la source"
                      onClick={() => ouvrirConfirmation(s.source_id)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <AlertDialog open={!!aSupprimer} onOpenChange={(open) => !open && setASupprimer(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette source ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action supprime définitivement les données brutes de cette source. Les instances déjà
              générées à partir d'elle restent intactes et exécutables — seul le lien de provenance
              disparaît. Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>

          {erreurSuppression && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              <div className="flex items-center gap-2 font-medium">
                <AlertCircle className="h-4 w-4" /> Échec de la suppression
              </div>
              <p className="mt-1">{erreurSuppression.message}</p>
            </div>
          )}

          <AlertDialogFooter>
            <AlertDialogCancel disabled={supprimer.isPending}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmerSuppression}
              disabled={supprimer.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {supprimer.isPending ? "Suppression..." : "Supprimer"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

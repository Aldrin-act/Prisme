import { useEffect, useRef, useState, type RefObject } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import {
  ArrowRightLeft,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Copy,
  Download,
  Eye,
  Factory,
  FolderOpen,
  Lightbulb,
  Loader2,
  Plug,
  Plus,
  Square,
  Trash2,
  Upload,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  useApercuPromptComprehension,
  useApercuPromptComprehensionSansSource,
  useCreerSource,
  useGenererInstanceDepuisSource,
  useGenererInstanceDeterministeDepuisSource,
  useImporterFichiersCsv,
  useSource,
  useSources,
  useSupprimerSource,
  useDeclencherExecution,
  PrismeAPIError,
  STATUT_REQUETE_ANNULEE,
  type AuthentificationAPI,
  type Justification,
} from "@/integrations/prisme";
import { PRISME_CONFIG } from "@/integrations/prisme";
import {
  LABELS_OBJECTIF,
  SectionObjectifs,
  construireObjectifs,
  nouvelObjectif,
  type ObjectifLigne,
} from "@/components/ingestion/ingestion-dialog";
import { useAuth } from "@/integrations/prisme/auth";
import type { UniteTemps } from "@/lib/dates-relatives";
import { hrefGabaritCsv, libelleUnite, nomGabaritCsv } from "@/lib/unite-ingestion";

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
  const [tab, setTab] = useState<"actif" | "historique" | "import_csv">("actif");
  // Pré-rempli depuis l'URL (?source=<id>) — permet un lien direct depuis la
  // page Instances vers le détail de la source qui a généré une instance donnée.
  const [sourceActiveId, setSourceActiveId] = useState<string | null>(source ?? null);

  function creerEtOuvrirSource(sourceId: string) {
    setSourceActiveId(sourceId);
  }

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
          <TabsTrigger value="import_csv">Import CSV</TabsTrigger>
        </TabsList>

        <TabsContent value="actif" className="max-w-3xl">
          {sourceActiveId ? (
            <SourceActivePanel sourceId={sourceActiveId} />
          ) : (
            <FormulaireNouvelleSource onCree={creerEtOuvrirSource} />
          )}
        </TabsContent>

        <TabsContent value="historique">
          <ListeSources onOuvrir={ouvrirSource} />
        </TabsContent>

        <TabsContent value="import_csv" className="max-w-3xl">
          <ImporteurCsvDirect />
        </TabsContent>
      </Tabs>
    </>
  );
}

// CSV a son propre flux dédié (onglet "Import CSV", voir ImporteurCsvDirect
// plus bas — un import direct multi-fichiers, sans passer par une Source) —
// ce formulaire-ci ne gère plus qu'un fichier de données brutes JSON, ou une
// connexion API. Une instance déjà structurée en JSON n'a pas besoin d'être
// scindée en plusieurs fichiers, contrairement à un export CSV.
type FormatDonnees = "json" | "api";

const ACCEPT_FICHIER_JSON = ".json,application/json";

// Gabarit d'exemple téléchargeable (Front/prismatron-solver-forge/public/gabarits/,
// voir scripts/generer_gabarit_ingestion.py pour la source de vérité régénérée
// côté backend — copie manuelle après changement).
const GABARIT_JSON = { nom: "instance_exemple.json", href: "/gabarits/instance_exemple.json" };

// Champ partagé entre FormulaireNouvelleSource (crée une Source réenre-
// gistrable) et ImporteurCsvDirect (crée une instance immédiatement, sans
// Source) — seul "Nom de l'atelier" reste propre au premier (aucune Source
// n'existe côté import CSV direct).
function ChampClientSource({
  idPrefix,
  estAdmin,
  clientId,
  onClientIdChange,
}: {
  idPrefix: string;
  estAdmin: boolean;
  clientId: string;
  onClientIdChange: (v: string) => void;
}) {
  return (
    <div className="space-y-1.5 sm:max-w-[calc(50%-0.5rem)]">
      <Label htmlFor={`${idPrefix}_client`}>Client</Label>
      <Input
        id={`${idPrefix}_client`}
        value={clientId}
        onChange={(e) => onClientIdChange(e.target.value)}
        disabled={!estAdmin}
      />
      {!estAdmin && (
        <p className="text-xs text-muted-foreground">Associé automatiquement à votre compte.</p>
      )}
    </div>
  );
}

// "export_atelier_mecanique.json" -> "export_atelier_mecanique" — utilisé pour préremplir
// "Nom de l'atelier" (voir FormulaireNouvelleSource) à partir du fichier choisi, jamais pour
// deviner quoi que ce soit dans les données elles-mêmes.
function nomDepuisNomFichier(nomFichier: string): string {
  return nomFichier.replace(/\.[^./\\]+$/, "").trim();
}

// Bouton "Choisir un fichier..." stylé / badge de fichier choisi avec retrait
// — un seul fichier par emplacement (contrairement à l'ancien onglet CSV,
// retiré, qui acceptait jusqu'à 3 fichiers dans le même emplacement).
function ChampFichierUnique({
  id,
  label,
  accept,
  fichier,
  onChange,
  inputRef,
}: {
  id: string;
  label: string;
  accept: string;
  fichier: File | null;
  onChange: (fichier: File | null) => void;
  inputRef: RefObject<HTMLInputElement | null>;
}) {
  return (
    <div className="space-y-1">
      <Label htmlFor={id} className="text-xs text-muted-foreground">
        {label}
      </Label>
      <input
        id={id}
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
      {fichier ? (
        <div className="flex h-9 w-full items-center justify-between rounded-md border border-input bg-transparent px-3 text-sm">
          <span className="flex items-center gap-1.5 truncate text-primary">
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{fichier.name}</span>
          </span>
          <button
            type="button"
            onClick={() => {
              onChange(null);
              if (inputRef.current) inputRef.current.value = "";
            }}
            className="shrink-0 text-muted-foreground hover:text-destructive"
            aria-label={`Retirer ${fichier.name}`}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="flex h-9 w-full items-center rounded-md border border-input bg-transparent px-3 text-sm text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground"
        >
          Choisir un fichier...
        </button>
      )}
    </div>
  );
}

function FormulaireNouvelleSource({ onCree }: { onCree: (sourceId: string) => void }) {
  const creer = useCreerSource();
  const apercuPrompt = useApercuPromptComprehensionSansSource();
  const inputFichierRef = useRef<HTMLInputElement>(null);
  const { utilisateur } = useAuth();
  const estAdmin = utilisateur?.role === "admin";

  const [clientId, setClientId] = useState(utilisateur?.client_id ?? "");
  const [nom, setNom] = useState("");
  const [donneesBrutes, setDonneesBrutes] = useState("");
  const [instructionsComplementaires, setInstructionsComplementaires] = useState("");
  // Objectifs déclarés avec les données — désactivés par défaut : l'agent (ou le fichier) décide
  // alors, comme avant. Activés, ils s'imposent à chaque instance générée depuis cette source.
  const [imposerObjectifs, setImposerObjectifs] = useState(false);
  const [objectifs, setObjectifs] = useState<ObjectifLigne[]>([nouvelObjectif()]);
  const [formatFichier, setFormatFichier] = useState<FormatDonnees>("json");
  const [fichier, setFichier] = useState<File | null>(null);
  const [chargementFichier, setChargementFichier] = useState(false);
  const [erreurFichier, setErreurFichier] = useState<string | null>(null);

  const erreur = creer.error as PrismeAPIError | null;

  function changerFormat(format: FormatDonnees) {
    setFormatFichier(format);
    setFichier(null);
    setErreurFichier(null);
    if (inputFichierRef.current) inputFichierRef.current.value = "";
  }

  async function definirFichier(nouveauFichier: File | null) {
    setFichier(nouveauFichier);
    setErreurFichier(null);
    if (!nouveauFichier) return;
    // Suggestion automatique du nom depuis le fichier choisi — seulement si le champ est
    // encore vide, jamais pour écraser un nom déjà saisi à la main.
    setNom((actuel) => (actuel.trim() ? actuel : nomDepuisNomFichier(nouveauFichier.name)));
    setChargementFichier(true);
    try {
      setDonneesBrutes(await nouveauFichier.text());
    } catch {
      setErreurFichier(
        "Fichier illisible — vérifiez qu'il correspond bien au format sélectionné ci-dessus.",
      );
    } finally {
      setChargementFichier(false);
    }
  }

  function enregistrer() {
    creer.mutate(
      {
        donneesBrutes,
        nom: nom.trim() || undefined,
        clientId: estAdmin ? clientId : undefined,
        objectifs: imposerObjectifs ? construireObjectifs(objectifs) : undefined,
      },
      { onSuccess: (data) => onCree(data.source_id) },
    );
  }

  return (
    <div className="glass space-y-5 rounded-2xl p-6">
      <div className="space-y-1.5">
        <Label htmlFor="nom_atelier">Nom de l'atelier (optionnel)</Label>
        <Input
          id="nom_atelier"
          value={nom}
          onChange={(e) => setNom(e.target.value)}
          placeholder="ex : Atelier mécanique"
          className="max-w-sm"
        />
      </div>

      <ChampClientSource
        idPrefix="donnees"
        estAdmin={estAdmin}
        clientId={clientId}
        onClientIdChange={setClientId}
      />

      <div className="space-y-1.5">
        <Label htmlFor="fichier_brut">Fichier de données brutes (optionnel)</Label>
        <Tabs value={formatFichier} onValueChange={(v) => changerFormat(v as FormatDonnees)}>
          <TabsList className="h-8">
            <TabsTrigger value="json" className="text-xs">
              JSON
            </TabsTrigger>
            <TabsTrigger value="api" className="text-xs">
              API (réception)
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {formatFichier === "api" ? (
          <InstructionsReceptionAPI clientId={clientId} />
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
              <span className="text-muted-foreground">Gabarit d'exemple :</span>
              <a
                href={GABARIT_JSON.href}
                download
                className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
              >
                <Download className="h-3 w-3" /> {GABARIT_JSON.nom}
              </a>
            </div>
            <ChampFichierUnique
              id="fichier_brut"
              label="Instance"
              accept={ACCEPT_FICHIER_JSON}
              fichier={fichier}
              onChange={definirFichier}
              inputRef={inputFichierRef}
            />
            {chargementFichier && (
              <p className="text-xs text-muted-foreground">Lecture du fichier...</p>
            )}
            {erreurFichier && (
              <p className="flex items-center gap-1.5 text-xs text-destructive">
                <AlertCircle className="h-3.5 w-3.5" /> {erreurFichier}
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              Charge le contenu du fichier dans le champ ci-dessous. Vous pouvez aussi coller le
              texte directement (export JSON, tableau collé...). Pour un export CSV
              Tâches/Ressources/Contraintes, voir l'onglet « Import CSV ».
            </p>
          </>
        )}
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

      <div className="space-y-2 rounded-lg border border-border/50 p-3">
        <label className="flex items-center gap-2 text-sm font-medium">
          <Checkbox
            checked={imposerObjectifs}
            onCheckedChange={(v) => setImposerObjectifs(v === true)}
          />
          Définir les objectifs de planification
        </label>
        <p className="text-xs text-muted-foreground">
          {imposerObjectifs
            ? "Ces objectifs s'appliquent à chaque instance générée depuis ces données, à la place de ceux que l'IA ou le fichier proposeraient."
            : "Non coché : l'IA (ou le fichier) choisit les objectifs à partir des données."}
        </p>
        {imposerObjectifs && <SectionObjectifs objectifs={objectifs} setObjectifs={setObjectifs} />}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="instructions_completives">
          Instructions complémentaires pour l'IA (optionnel)
        </Label>
        <Textarea
          id="instructions_completives"
          value={instructionsComplementaires}
          onChange={(e) => setInstructionsComplementaires(e.target.value)}
          placeholder="Contexte métier supplémentaire pour aider la traduction — ne peut jamais l'emporter sur les règles de traduction elles-mêmes (ex. compétence vs. simple historique d'affectation)."
          className="min-h-16 text-xs"
        />
        <p className="text-xs text-muted-foreground">
          Pas persisté sur la source — à ressaisir à chaque tentative de génération si besoin,
          depuis le panneau de la source une fois créée.
        </p>
      </div>

      {donneesBrutes.trim() && (
        <details
          className="rounded-lg border border-border/50 p-3 text-xs"
          onToggle={(e) => {
            if (e.currentTarget.open) {
              apercuPrompt.mutate({ donneesBrutes, instructionsComplementaires });
            }
          }}
        >
          <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-muted-foreground">
            <Eye className="h-3.5 w-3.5" /> Voir le prompt envoyé à l'IA sur ce texte
          </summary>
          <p className="mt-2 text-muted-foreground">
            Le prompt exact que "Générer une instance" enverrait à l'agent de compréhension sur les
            données brutes (et instructions complémentaires) ci-dessus — construit sans appeler le
            LLM, gratuit.
          </p>
          {apercuPrompt.data && (
            <button
              type="button"
              className="mt-1 text-primary hover:underline"
              onClick={() => apercuPrompt.mutate({ donneesBrutes, instructionsComplementaires })}
            >
              Actualiser l'aperçu
            </button>
          )}
          {apercuPrompt.isPending && (
            <p className="mt-2 text-muted-foreground">Construction du prompt...</p>
          )}
          {apercuPrompt.error && (
            <p className="mt-2 text-destructive">
              {(apercuPrompt.error as PrismeAPIError).message}
            </p>
          )}
          {apercuPrompt.data && (
            <div className="mt-2 space-y-2">
              <button
                type="button"
                className="flex items-center gap-1 text-primary hover:underline"
                onClick={() =>
                  telechargerTexte(
                    "gabarit_prompt_comprehension.txt",
                    `--- PROMPT SYSTÈME ---\n\n${apercuPrompt.data!.prompt_systeme}\n\n` +
                      `--- PROMPT UTILISATEUR ---\n\n${apercuPrompt.data!.prompt_utilisateur}`,
                  )
                }
              >
                <Download className="h-3 w-3" /> Télécharger le gabarit de prompt
              </button>
              <div>
                <div className="mb-1 font-medium text-foreground">Prompt système</div>
                <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded-md bg-muted/30 p-2 font-mono">
                  {apercuPrompt.data.prompt_systeme}
                </pre>
              </div>
              <div>
                <div className="mb-1 font-medium text-foreground">Prompt utilisateur</div>
                <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-muted/30 p-2 font-mono">
                  {apercuPrompt.data.prompt_utilisateur}
                </pre>
              </div>
            </div>
          )}
        </details>
      )}

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

// Réception : c'est l'ERP du client qui envoie ses données à PRISME, jamais PRISME qui va les
// chercher. Rien à saisir ici donc — l'écran donne l'adresse à appeler, l'en-tête d'authentification
// et un exemple prêt à copier ; le jeton est une clé PRISME, créée dans « Clés API » (jamais
// réaffichée après sa création, d'où le lien plutôt qu'une valeur ici).
function InstructionsReceptionAPI({ clientId }: { clientId: string }) {
  const [copie, setCopie] = useState<string | null>(null);
  const url = `${PRISME_CONFIG.baseURL}${PRISME_CONFIG.routes.sources}`;
  const client = clientId.trim() || "VOTRE_CLIENT";
  const exemple = [
    `curl -X POST ${url} \\`,
    `  -H "Authorization: Bearer pk_live_VOTRE_CLE" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '{"nom": "Export ERP", "client_id": "${client}", "donnees_brutes": "..." }'`,
  ].join("\n");

  async function copier(texte: string, quoi: string) {
    try {
      await navigator.clipboard.writeText(texte);
      setCopie(quoi);
      setTimeout(() => setCopie(null), 2000);
    } catch {
      setCopie(null); // presse-papiers refusé (navigateur/permission) : l'utilisateur copie à la main
    }
  }

  return (
    <div className="space-y-3 rounded-lg border border-border/50 p-3">
      <p className="text-xs text-muted-foreground">
        Votre ERP envoie ses données à PRISME — rien à saisir ici. Il s'identifie avec un jeton
        PRISME, et le corps de l'envoi remplit le champ « Données brutes » d'une nouvelle source,
        exactement comme un export collé à la main.
      </p>

      <div className="space-y-1">
        <Label className="text-xs text-muted-foreground">Adresse de réception</Label>
        <div className="flex items-center gap-2">
          <code className="flex-1 truncate rounded-md border border-border/50 bg-muted/30 px-2 py-1.5 font-mono text-xs">
            POST {url}
          </code>
          <Button variant="outline" size="sm" onClick={() => copier(url, "url")}>
            {copie === "url" ? "Copié" : "Copier"}
          </Button>
        </div>
      </div>

      <div className="space-y-1">
        <Label className="text-xs text-muted-foreground">Authentification</Label>
        <code className="block rounded-md border border-border/50 bg-muted/30 px-2 py-1.5 font-mono text-xs">
          Authorization: Bearer pk_live_...
        </code>
        <p className="text-xs text-muted-foreground">
          Créez ce jeton dans{" "}
          <Link to="/api-keys" className="text-primary underline-offset-2 hover:underline">
            Clés API
          </Link>{" "}
          — il n'est affiché qu'à sa création, notez-le à ce moment-là.
        </p>
      </div>

      <div className="space-y-1">
        <div className="flex items-center justify-between">
          <Label className="text-xs text-muted-foreground">Exemple d'envoi</Label>
          <Button variant="ghost" size="sm" onClick={() => copier(exemple, "exemple")}>
            <Copy className="mr-1.5 h-3 w-3" />
            {copie === "exemple" ? "Copié" : "Copier"}
          </Button>
        </div>
        <pre className="overflow-x-auto rounded-md border border-border/50 bg-muted/30 p-2 font-mono text-[11px] leading-relaxed">
          {exemple}
        </pre>
        <p className="text-xs text-muted-foreground">
          Un export volumineux s'envoie en plusieurs appels : chacun crée sa propre source,
          reconvertible indépendamment. Cinq mégaoctets par envoi au maximum.
        </p>
      </div>
    </div>
  );
}

function ResultatExecutionAuto({
  executer,
}: {
  executer: ReturnType<typeof useDeclencherExecution>;
}) {
  if (executer.isPending) {
    return <p className="text-sm text-muted-foreground">Exécution automatique en cours...</p>;
  }
  if (executer.isSuccess) {
    return (
      <div
        className={`rounded-lg border p-3 text-sm ${
          executer.data.reussi
            ? "border-primary/40 bg-primary/10 text-primary"
            : "border-destructive/40 bg-destructive/10 text-destructive"
        }`}
      >
        <div className="flex items-center gap-2 font-medium">
          {executer.data.reussi ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <AlertCircle className="h-4 w-4" />
          )}
          {executer.data.reussi ? "Planning généré automatiquement" : "Exécution en échec"}
        </div>
        {!executer.data.reussi && executer.data.erreur && (
          <p className="mt-1 text-muted-foreground">{executer.data.erreur}</p>
        )}
      </div>
    );
  }
  if (executer.isError) {
    return (
      <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
        <div className="flex items-center gap-2 font-medium text-amber-600 dark:text-amber-400">
          <AlertCircle className="h-4 w-4" /> Instance générée, mais pas encore exécutée
        </div>
        <p className="mt-1 text-muted-foreground">{(executer.error as PrismeAPIError).message}</p>
      </div>
    );
  }
  return null;
}

type EntiteCsv = "taches" | "ressources" | "contraintes" | "commandes";

const ENTITES_CSV: EntiteCsv[] = ["taches", "ressources", "contraintes", "commandes"];
const ENTITES_CSV_REQUISES: EntiteCsv[] = ["taches", "ressources", "contraintes"];

const LABELS_ENTITE_CSV: Record<EntiteCsv, string> = {
  taches: "Tâches",
  ressources: "Ressources",
  contraintes: "Contraintes",
  commandes: "Commandes",
};

// Documentation des colonnes attendues par fichier — reflète exactement
// adapters/csv_import/traducteur.py (COLONNES_*_REQUISES/OPTIONNELLES,
// TYPES_CONTRAINTE_SUPPORTES) : une deuxième source de vérité délibérée côté
// frontend, comme les gabarits de src/lib/unite-ingestion.ts — à relire si le
// schéma backend change. Fonction de l'unité de temps : le nom de la colonne de
// durée et le sens de date_limite en dépendent.
interface ChampDocCsv {
  champ: string;
  requis: boolean;
  type: string;
  valeursAttendues: string;
}

function docChampsCsv(unite: UniteTemps): Record<EntiteCsv, ChampDocCsv[]> {
  return {
    taches: [
      {
        champ: "id",
        requis: true,
        type: "Texte",
        valeursAttendues: "Identifiant unique de la tâche",
      },
      { champ: "nom", requis: false, type: "Texte", valeursAttendues: "Libellé affiché" },
    ],
    ressources: [
      {
        champ: "id",
        requis: true,
        type: "Texte",
        valeursAttendues: "Identifiant unique de la ressource",
      },
      { champ: "nom", requis: false, type: "Texte", valeursAttendues: "Libellé affiché" },
      {
        champ: "competences",
        requis: false,
        type: "Liste",
        valeursAttendues: "Séparées par ; (ex. decoupe;assemblage)",
      },
      {
        champ: "heures_par_jour",
        requis: false,
        type: "Entier",
        valeursAttendues:
          "Durée de travail quotidienne, 1 à 24 h — vide : disponible en continu. La ressource " +
          "devient indisponible le reste de chaque journée.",
      },
    ],
    contraintes: [
      {
        champ: "type",
        requis: true,
        type: "Texte",
        valeursAttendues: "precedence | compatibilite_ressource_tache | competence_requise",
      },
      {
        champ: "tache_avant, tache_apres",
        requis: false,
        type: "Texte",
        valeursAttendues: "Requis si type = precedence",
      },
      {
        champ: "tache, ressource",
        requis: false,
        type: "Texte",
        valeursAttendues:
          "Requis si type = compatibilite_ressource_tache — aucune durée ici : elle se fixe à la " +
          "commande, tâche par tâche",
      },
      {
        champ: "tache, competence",
        requis: false,
        type: "Texte",
        valeursAttendues: "Requis si type = competence_requise",
      },
    ],
    commandes: [
      {
        champ: "id",
        requis: true,
        type: "Texte",
        valeursAttendues: "Identifiant unique de la commande",
      },
      {
        champ: "taches",
        requis: true,
        type: "Liste",
        valeursAttendues: "Séparées par ; (ex. T1;T2)",
      },
      { champ: "client", requis: false, type: "Texte", valeursAttendues: "Nom du client" },
      {
        champ: "date_limite",
        requis: false,
        type: "Entier",
        valeursAttendues: `${unite === "heures" ? "Heures" : "Jours"} relatifs — dérive une échéance par tâche liée, jamais une date calendaire`,
      },
    ],
  };
}

// Unité fixe de cet import : les fichiers déposés ici sont toujours lus en heures (aucun choix
// demandé à l'écran). Le formulaire d'ingestion, lui, laisse le choix — voir
// `components/ingestion/ingestion-dialog.tsx::SelecteurUniteTemps`.
const UNITE_TEMPS_IMPORT: UniteTemps = "heures";

const OPTIONS_DELIMITEUR_CSV: { valeur: string; label: string }[] = [
  { valeur: ",", label: "Virgule (,)" },
  { valeur: ";", label: "Point-virgule (;)" },
  { valeur: "\t", label: "Tabulation" },
  { valeur: "|", label: "Pipe (|)" },
];

// Import CSV direct — POST /adapters/csv/{client_id} (multipart), déjà câblé
// côté client (prismeClient.importerFichiersCsv / useImporterFichiersCsv)
// mais jamais branché à une UI avant cette page. Contrairement à
// FormulaireNouvelleSource, ne crée aucune Source : l'instance est créée
// immédiatement (comme GreenSIG ou l'import tableur), source_id=NULL. Les
// 3 fichiers requis (Tâches/Ressources/Contraintes) sont combinés en une
// seule instance en un seul appel — un bouton "Importer" partagé, pas un
// par section (contrairement à la référence visuelle qui a inspiré cette
// page, où chaque entité est une table indépendante).
function ImporteurCsvDirect() {
  const { utilisateur } = useAuth();
  const estAdmin = utilisateur?.role === "admin";
  const importer = useImporterFichiersCsv();
  const executer = useDeclencherExecution();

  const [clientId, setClientId] = useState(utilisateur?.client_id ?? "");
  const [delimiteur, setDelimiteur] = useState(",");
  // Unité des entiers écrits dans les fichiers (durées, date_limite) — transmise telle quelle au
  // backend (unite_temps), qui ne convertit rien : elle fixe aussi la colonne de durée attendue et
  // le gabarit proposé au téléchargement.
  const docChamps = docChampsCsv(UNITE_TEMPS_IMPORT);
  const [fichiers, setFichiers] = useState<Partial<Record<EntiteCsv, File>>>({});
  const inputRefs: Record<EntiteCsv, RefObject<HTMLInputElement | null>> = {
    taches: useRef<HTMLInputElement>(null),
    ressources: useRef<HTMLInputElement>(null),
    contraintes: useRef<HTMLInputElement>(null),
    commandes: useRef<HTMLInputElement>(null),
  };
  const [resultat, setResultat] = useState<{
    instance_id: string;
    structure_contraintes: string;
    avertissements: string[];
  } | null>(null);

  const erreur = importer.error as PrismeAPIError | null;
  const pretPourImport =
    ENTITES_CSV_REQUISES.every((e) => fichiers[e]) && clientId.trim().length > 0;

  function definirFichierEntite(entite: EntiteCsv, fichier: File | null) {
    setFichiers((precedent) => {
      const suivant = { ...precedent };
      if (fichier) suivant[entite] = fichier;
      else delete suivant[entite];
      return suivant;
    });
  }

  function importerFichiers() {
    if (!fichiers.taches || !fichiers.ressources || !fichiers.contraintes) return;
    executer.reset();
    setResultat(null);
    importer.mutate(
      {
        clientId,
        fichiers: {
          taches: fichiers.taches,
          ressources: fichiers.ressources,
          contraintes: fichiers.contraintes,
          commandes: fichiers.commandes,
        },
        delimiteur,
        uniteTemps: UNITE_TEMPS_IMPORT,
      },
      {
        onSuccess: (data) => {
          setResultat(data);
          executer.mutate({ instanceId: data.instance_id });
        },
      },
    );
  }

  return (
    <div className="glass space-y-5 rounded-2xl p-6">
      <p className="text-sm text-muted-foreground">
        Import direct depuis des fichiers CSV séparés (un par table) — crée une instance
        immédiatement, sans passer par une Source réenregistrable. Pour un export ERP non structuré
        (une seule pièce jointe, un format libre), utilisez plutôt l'onglet « Source en cours ».
      </p>

      <ChampClientSource
        idPrefix="import_csv"
        estAdmin={estAdmin}
        clientId={clientId}
        onClientIdChange={setClientId}
      />

      <div className="space-y-1.5">
        <Label htmlFor="import_csv_delimiteur">Délimiteur CSV</Label>
        <Select value={delimiteur} onValueChange={setDelimiteur}>
          <SelectTrigger id="import_csv_delimiteur" className="max-w-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {OPTIONS_DELIMITEUR_CSV.map((o) => (
              <SelectItem key={o.valeur} value={o.valeur}>
                {o.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          S'applique identiquement aux quatre fichiers — jamais deviné automatiquement. Les dates
          limites sont lues en heures, sans conversion. Aucun fichier ne porte de durée : elle se
          fixe à la commande, tâche par tâche.
        </p>
      </div>

      <div className="space-y-3">
        {ENTITES_CSV.map((entite) => {
          const requis = ENTITES_CSV_REQUISES.includes(entite);
          return (
            <details key={entite} className="rounded-lg border border-border/50 p-3" open={requis}>
              <summary className="flex cursor-pointer items-center gap-2 text-sm font-medium">
                {LABELS_ENTITE_CSV[entite]}
                <Badge variant={requis ? "default" : "outline"} className="text-[10px]">
                  {requis ? "Requis" : "Optionnel"}
                </Badge>
                {fichiers[entite] && <CheckCircle2 className="h-3.5 w-3.5 text-primary" />}
              </summary>

              <div className="mt-3 space-y-3">
                <div className="overflow-x-auto rounded-md border border-border/50">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead className="text-xs">Champ</TableHead>
                        <TableHead className="text-xs">Requis</TableHead>
                        <TableHead className="text-xs">Type</TableHead>
                        <TableHead className="text-xs">Valeurs attendues</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {docChamps[entite].map((c) => (
                        <TableRow key={c.champ}>
                          <TableCell className="font-mono text-xs">{c.champ}</TableCell>
                          <TableCell className="text-xs">{c.requis ? "X" : ""}</TableCell>
                          <TableCell className="text-xs">{c.type}</TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {c.valeursAttendues}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>

                <a
                  href={hrefGabaritCsv(entite, UNITE_TEMPS_IMPORT)}
                  download
                  className="inline-flex items-center gap-1 text-xs text-primary underline-offset-2 hover:underline"
                >
                  <Download className="h-3 w-3" /> Télécharger le gabarit{" "}
                  {nomGabaritCsv(entite, UNITE_TEMPS_IMPORT)}
                </a>

                <ChampFichierUnique
                  id={`import_csv_fichier_${entite}`}
                  label={`Fichier ${entite}.csv`}
                  accept=".csv,text/csv"
                  fichier={fichiers[entite] ?? null}
                  onChange={(f) => definirFichierEntite(entite, f)}
                  inputRef={inputRefs[entite]}
                />
              </div>
            </details>
          );
        })}
      </div>

      {erreur && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <div className="flex items-center gap-2 font-medium">
            <AlertCircle className="h-4 w-4" /> Échec de l'import
          </div>
          <p className="mt-1">{erreur.message}</p>
        </div>
      )}

      {resultat && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2 font-medium text-primary">
            <CheckCircle2 className="h-4 w-4" /> Instance créée
            <Badge variant="secondary" className="font-mono text-xs">
              {resultat.instance_id}
            </Badge>
            <Badge variant="outline" className="font-mono text-xs">
              {resultat.structure_contraintes}
            </Badge>
          </div>
          {resultat.avertissements.length > 0 && (
            <div className="mt-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-xs">
              <div className="flex items-center gap-1.5 font-medium text-amber-600 dark:text-amber-400">
                <AlertTriangle className="h-3.5 w-3.5" /> Avertissements
              </div>
              <ul className="mt-1 list-disc space-y-0.5 pl-4 text-muted-foreground">
                {resultat.avertissements.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="mt-2">
            <ResultatExecutionAuto executer={executer} />
          </div>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted-foreground">
          Les fichiers Tâches/Ressources/Contraintes sont combinés en une seule instance — importés
          ensemble, pas fichier par fichier.
        </p>
        <Button
          onClick={importerFichiers}
          disabled={!pretPourImport || importer.isPending}
          className="shrink-0"
        >
          <Upload className="mr-2 h-4 w-4" />
          {importer.isPending ? "Import en cours..." : "Importer"}
        </Button>
      </div>
    </div>
  );
}

// Téléchargement client (Blob + lien programmatique) — contrairement aux gabarits CSV/JSON
// (fichiers statiques sous public/gabarits/, voir src/lib/unite-ingestion.ts), le prompt dépend
// des données brutes de CETTE source : rien de statique à servir, le contenu vient de ce qui est
// déjà affiché à l'écran (apercuPrompt.data), jamais reconstruit ici.
function telechargerTexte(nomFichier: string, contenu: string) {
  const lien = document.createElement("a");
  lien.href = URL.createObjectURL(new Blob([contenu], { type: "text/plain;charset=utf-8" }));
  lien.download = nomFichier;
  lien.click();
  URL.revokeObjectURL(lien.href);
}

function SourceActivePanel({ sourceId }: { sourceId: string }) {
  const queryClient = useQueryClient();
  const { data: source, isLoading } = useSource(sourceId);
  const generer = useGenererInstanceDepuisSource();
  const genererDeterministe = useGenererInstanceDeterministeDepuisSource();
  const executer = useDeclencherExecution();
  // Non persisté sur la source (voir FormulaireNouvelleSource) — remis à zéro à chaque ouverture
  // de panneau, ressaisi à volonté pour chaque tentative de génération.
  const [instructionsComplementaires, setInstructionsComplementaires] = useState("");
  // Aperçu du prompt IA — chargé seulement à l'ouverture du <details> ci-dessous (refetch
  // manuel), jamais automatiquement : gratuit mais inutile tant que personne ne le consulte.
  const apercuPrompt = useApercuPromptComprehension(sourceId, instructionsComplementaires);
  const [dernier, setDernier] = useState<{
    instance_id: string;
    // Résumé en langage naturel de ce que fait l'atelier — absent (null) pour une conversion
    // déterministe (genererInstanceDeterministe), aucun agent LLM n'intervient sur ce chemin.
    descriptionMetier: string | null;
    avertissements: string[];
    justifications: Justification[];
  } | null>(null);

  // État local pour maintenir l'indicateur visible même si le composant re-render
  const [generationEnCours, setGenerationEnCours] = useState(false);

  // Bouton "Arrêter" : coupe la requête en cours, le serveur abandonne alors la conversion sans
  // enregistrer d'instance.
  const annulationRef = useRef<AbortController | null>(null);

  const erreurBrute = generer.error as PrismeAPIError | null;
  const generationAnnulee = erreurBrute?.status === STATUT_REQUETE_ANNULEE;
  // Une annulation voulue n'est pas un échec : message neutre à part, pas le bandeau rouge.
  const erreur = generationAnnulee ? null : erreurBrute;
  const erreurDeterministe = genererDeterministe.error as PrismeAPIError | null;

  function arreterGeneration() {
    annulationRef.current?.abort();
  }

  function invaliderApresConversion() {
    queryClient.invalidateQueries({ queryKey: prismeKeys.source(sourceId) });
    queryClient.invalidateQueries({ queryKey: prismeKeys.sources() });
    queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
  }

  // Réexécute automatiquement dès qu'une conversion produit une instance —
  // le principe fondateur "generate once" reste respecté : /execution
  // échoue proprement (409) si aucun solveur validé n'existe encore pour
  // cette structure, sans jamais en générer un à la volée.
  function executerAutomatiquement(instanceId: string) {
    executer.mutate(
      { instanceId },
      { onSuccess: () => queryClient.invalidateQueries({ queryKey: prismeKeys.executions() }) },
    );
  }

  function genererInstance() {
    genererDeterministe.reset();
    executer.reset();
    setDernier(null);
    setGenerationEnCours(true);
    const annulation = new AbortController();
    annulationRef.current = annulation;
    generer.mutate(
      {
        sourceId,
        instructionsComplementaires: instructionsComplementaires || undefined,
        signal: annulation.signal,
      },
      {
        onSuccess: (data) => {
          setDernier({
            instance_id: data.instance_id,
            descriptionMetier: data.description_metier,
            avertissements: data.avertissements,
            justifications: data.justifications,
          });
          setGenerationEnCours(false);
          invaliderApresConversion();
          executerAutomatiquement(data.instance_id);
        },
        onError: () => {
          setGenerationEnCours(false);
        },
      },
    );
  }

  function genererInstanceDeterministe() {
    generer.reset();
    executer.reset();
    setDernier(null);
    genererDeterministe.mutate(
      { sourceId },
      {
        onSuccess: (data) => {
          setDernier({
            instance_id: data.instance_id,
            descriptionMetier: null,
            avertissements: [],
            justifications: [],
          });
          invaliderApresConversion();
          executerAutomatiquement(data.instance_id);
        },
      },
    );
  }

  if (isLoading || !source) {
    return (
      <div className="glass rounded-2xl p-6 text-sm text-muted-foreground">
        Chargement de la source...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="glass space-y-4 rounded-2xl p-6">
        <div>
          <div className="text-xs uppercase tracking-widest text-muted-foreground">Source</div>
          <h3 className="text-lg font-semibold">{source.nom || "Sans nom"}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>{source.client_id}</span>
            <span>·</span>
            <span>{new Date(source.date_creation).toLocaleString()}</span>
            <span>·</span>
            <Badge variant="outline" className="font-mono">
              {source.source_id}
            </Badge>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground">Objectifs :</span>
          {source.objectifs.length > 0 ? (
            source.objectifs.map((o, i) => (
              <Badge key={i} variant="secondary">
                {LABELS_OBJECTIF[o.type]}
              </Badge>
            ))
          ) : (
            <span className="text-muted-foreground">choisis par l'IA à chaque conversion</span>
          )}
        </div>

        <details className="rounded-lg border border-border/50 p-3 text-xs">
          <summary className="cursor-pointer font-medium text-muted-foreground">
            Voir les données brutes
          </summary>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-mono">
            {source.donnees_brutes}
          </pre>
        </details>

        <div className="space-y-1.5">
          <Label htmlFor="instructions_completives_source" className="text-xs">
            Instructions complémentaires pour l'IA (optionnel)
          </Label>
          <Textarea
            id="instructions_completives_source"
            value={instructionsComplementaires}
            onChange={(e) => setInstructionsComplementaires(e.target.value)}
            placeholder="Contexte métier supplémentaire — ne peut jamais l'emporter sur les règles de traduction elles-mêmes."
            className="min-h-16 text-xs"
          />
        </div>

        <details
          className="rounded-lg border border-border/50 p-3 text-xs"
          onToggle={(e) => {
            if (e.currentTarget.open && !apercuPrompt.data && !apercuPrompt.isFetching) {
              apercuPrompt.refetch();
            }
          }}
        >
          <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-muted-foreground">
            <Eye className="h-3.5 w-3.5" /> Voir le prompt envoyé à l'IA
          </summary>
          <p className="mt-2 text-muted-foreground">
            Le prompt exact que "Générer une instance" enverrait à l'agent de compréhension —
            construit sans appeler le LLM, gratuit, rien n'est déclenché en le consultant.
          </p>
          {apercuPrompt.data && (
            <button
              type="button"
              className="mt-1 text-primary hover:underline"
              onClick={() => apercuPrompt.refetch()}
            >
              Actualiser l'aperçu (après modification des instructions)
            </button>
          )}
          {apercuPrompt.isFetching && (
            <p className="mt-2 text-muted-foreground">Construction du prompt...</p>
          )}
          {apercuPrompt.error && (
            <p className="mt-2 text-destructive">
              {(apercuPrompt.error as PrismeAPIError).message}
            </p>
          )}
          {apercuPrompt.data && (
            <div className="mt-2 space-y-2">
              <button
                type="button"
                className="flex items-center gap-1 text-primary hover:underline"
                onClick={() =>
                  telechargerTexte(
                    `gabarit_prompt_comprehension_${sourceId}.txt`,
                    `--- PROMPT SYSTÈME ---\n\n${apercuPrompt.data!.prompt_systeme}\n\n` +
                      `--- PROMPT UTILISATEUR ---\n\n${apercuPrompt.data!.prompt_utilisateur}`,
                  )
                }
              >
                <Download className="h-3 w-3" /> Télécharger le gabarit de prompt
              </button>
              <div>
                <div className="mb-1 font-medium text-foreground">Prompt système</div>
                <pre className="max-h-32 overflow-auto whitespace-pre-wrap rounded-md bg-muted/30 p-2 font-mono">
                  {apercuPrompt.data.prompt_systeme}
                </pre>
              </div>
              <div>
                <div className="mb-1 font-medium text-foreground">Prompt utilisateur</div>
                <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded-md bg-muted/30 p-2 font-mono">
                  {apercuPrompt.data.prompt_utilisateur}
                </pre>
              </div>
            </div>
          )}
        </details>

        {erreur && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <div className="flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4" /> Échec de la conversion
            </div>
            <p className="mt-1">{erreur.message}</p>
          </div>
        )}

        {erreurDeterministe && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <div className="flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4" /> Échec de la conversion déterministe
            </div>
            <p className="mt-1">{erreurDeterministe.message}</p>
          </div>
        )}

        {dernier?.descriptionMetier && (
          <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">
            <div className="flex items-center gap-2 font-medium text-primary">
              <Factory className="h-4 w-4" /> Comment fonctionne cet atelier
            </div>
            <p className="mt-1 text-muted-foreground">{dernier.descriptionMetier}</p>
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

        <ResultatExecutionAuto executer={executer} />

        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            Rejouable à volonté sur ces mêmes données brutes — chaque conversion ajoute une instance
            à l'historique ci-dessous, aucune n'est remplacée. Chaque instance générée est exécutée
            automatiquement si un solveur validé existe déjà pour sa structure.
          </p>
          <div className="flex shrink-0 flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={genererInstanceDeterministe}
              disabled={generationEnCours || generer.isPending || genererDeterministe.isPending}
            >
              <Zap className="mr-2 h-4 w-4" />
              {genererDeterministe.isPending ? "Conversion..." : "Convertir sans IA"}
            </Button>
            {generationEnCours || generer.isPending ? (
              <Button variant="destructive" onClick={arreterGeneration}>
                <Square className="mr-2 h-4 w-4" />
                Arrêter
              </Button>
            ) : (
              <Button onClick={genererInstance} disabled={genererDeterministe.isPending}>
                <ArrowRightLeft className="mr-2 h-4 w-4" />
                Générer une instance
              </Button>
            )}
          </div>
        </div>
        {(generationEnCours || generer.isPending) && <IndicateurGeneration />}
        {generationAnnulee && (
          <p className="text-sm text-muted-foreground">
            Génération arrêtée — aucune instance n'a été créée.
          </p>
        )}
      </div>

      <div className="glass rounded-2xl p-6">
        <h4 className="mb-3 text-sm font-semibold">
          Instances générées ({source.instances.length})
        </h4>
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
                <Badge variant="secondary" className="font-mono text-xs">
                  {i.instance_id}
                </Badge>
                <Badge variant="outline" className="font-mono text-xs">
                  {i.structure_contraintes}
                </Badge>
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
    const timerSecondes = setInterval(
      () => setSecondes(Math.floor((Date.now() - debut) / 1000)),
      1000,
    );
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
        <div className="truncate text-xs text-muted-foreground">
          {MESSAGES_GENERATION[messageIndex]}
        </div>
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
        <div className="overflow-x-auto">
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
                    <Badge variant={s.nb_instances > 0 ? "secondary" : "outline"}>
                      {s.nb_instances}
                    </Badge>
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
      </div>

      <AlertDialog open={!!aSupprimer} onOpenChange={(open) => !open && setASupprimer(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette source ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action supprime définitivement les données brutes de cette source. Les instances
              déjà générées à partir d'elle restent intactes et exécutables — seul le lien de
              provenance disparaît. Cette action est irréversible.
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

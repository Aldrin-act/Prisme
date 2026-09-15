import { useEffect, useRef, useState, type RefObject } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import {
  ArrowRightLeft,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Download,
  Factory,
  FolderOpen,
  Lightbulb,
  Loader2,
  Plug,
  Plus,
  Trash2,
  Upload,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";
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
  useCreerSource,
  useExplorerAPI,
  useGenererInstanceDepuisSource,
  useGenererInstanceDeterministeDepuisSource,
  useImporterFichiersCsv,
  useSource,
  useSources,
  useSupprimerSource,
  useDeclencherExecution,
  PrismeAPIError,
  type AuthentificationAPI,
  type Justification,
  type TypeAuthentificationAPI,
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
  const inputFichierRef = useRef<HTMLInputElement>(null);
  const { utilisateur } = useAuth();
  const estAdmin = utilisateur?.role === "admin";

  const [clientId, setClientId] = useState(utilisateur?.client_id ?? "");
  const [nom, setNom] = useState("");
  const [donneesBrutes, setDonneesBrutes] = useState("");
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
              API
            </TabsTrigger>
          </TabsList>
        </Tabs>

        {formatFichier === "api" ? (
          <FormulaireConnexionAPI onExtrait={setDonneesBrutes} />
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

// Connexion à une API HTTP quelconque (POST /sources/explorer-api) — un seul
// appel, jamais les identifiants saisis ici, qui ne servent qu'à cet appel.
// Ne crée jamais de source elle-même : remplit seulement le champ "Données
// brutes" du formulaire parent, pour relecture avant "Enregistrer la source".
function FormulaireConnexionAPI({ onExtrait }: { onExtrait: (donneesBrutes: string) => void }) {
  const explorer = useExplorerAPI();
  const [url, setUrl] = useState("");
  const [methode, setMethode] = useState<"GET" | "POST">("GET");
  const [typeAuth, setTypeAuth] = useState<TypeAuthentificationAPI>("aucune");
  const [enTeteCle, setEnTeteCle] = useState("X-API-Key");
  const [valeurCle, setValeurCle] = useState("");
  const [jeton, setJeton] = useState("");
  const [utilisateurApi, setUtilisateurApi] = useState("");
  const [motDePasseApi, setMotDePasseApi] = useState("");
  const [corps, setCorps] = useState("");
  // Validée côté client avant tout appel réseau — sinon une URL incomplète
  // (protocole manquant, oubli fréquent) ne remonte qu'un message d'erreur
  // brut de la librairie HTTP serveur, en anglais, une fois l'appel déjà
  // parti pour rien.
  const [erreurUrl, setErreurUrl] = useState<string | null>(null);

  const erreur = explorer.error as PrismeAPIError | null;

  function urlValide(valeur: string): boolean {
    try {
      const analysee = new URL(valeur);
      return analysee.protocol === "http:" || analysee.protocol === "https:";
    } catch {
      return false;
    }
  }

  function extraire() {
    const urlSaisie = url.trim();
    if (!urlValide(urlSaisie)) {
      setErreurUrl(
        "L'URL doit être complète et commencer par http:// ou https:// (ex. https://erp.exemple.com/api/taches).",
      );
      return;
    }
    setErreurUrl(null);

    const authentification: AuthentificationAPI =
      typeAuth === "cle_api"
        ? {
            type: "cle_api",
            en_tete: enTeteCle.trim() || undefined,
            valeur: valeurCle || undefined,
          }
        : typeAuth === "porteur"
          ? { type: "porteur", jeton: jeton || undefined }
          : typeAuth === "basique"
            ? {
                type: "basique",
                utilisateur: utilisateurApi.trim() || undefined,
                mot_de_passe: motDePasseApi || undefined,
              }
            : { type: "aucune" };

    explorer.mutate(
      {
        url: urlSaisie,
        methode,
        authentification,
        corps: methode === "POST" && corps.trim() ? corps : undefined,
      },
      { onSuccess: (data) => onExtrait(data.donnees_brutes) },
    );
  }

  return (
    <div className="space-y-3 rounded-lg border border-border/50 p-3">
      <p className="text-xs text-muted-foreground">
        Un seul appel HTTP — l'URL et les identifiants ne sont jamais enregistrés, seule la réponse
        remplit le champ « Données brutes » ci-dessous, pour relecture avant d'enregistrer la
        source. Une réponse paginée ne renvoie que sa première page.
      </p>

      <div className="grid gap-3 sm:grid-cols-4">
        <div className="space-y-1 sm:col-span-3">
          <Label htmlFor="api_url" className="text-xs text-muted-foreground">
            URL
          </Label>
          <Input
            id="api_url"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setErreurUrl(null);
            }}
            placeholder="https://erp.exemple.com/api/taches"
            className="h-9 text-sm"
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="api_methode" className="text-xs text-muted-foreground">
            Méthode
          </Label>
          <Select value={methode} onValueChange={(v) => setMethode(v as "GET" | "POST")}>
            <SelectTrigger id="api_methode" className="h-9 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="GET">GET</SelectItem>
              <SelectItem value="POST">POST</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1 sm:col-span-4">
          <Label htmlFor="api_auth" className="text-xs text-muted-foreground">
            Authentification
          </Label>
          <Select value={typeAuth} onValueChange={(v) => setTypeAuth(v as TypeAuthentificationAPI)}>
            <SelectTrigger id="api_auth" className="h-9 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="aucune">Aucune</SelectItem>
              <SelectItem value="cle_api">Clé API (en-tête)</SelectItem>
              <SelectItem value="porteur">Jeton porteur (Bearer)</SelectItem>
              <SelectItem value="basique">Utilisateur / mot de passe</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {typeAuth === "cle_api" && (
          <>
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="api_en_tete" className="text-xs text-muted-foreground">
                Nom de l'en-tête
              </Label>
              <Input
                id="api_en_tete"
                value={enTeteCle}
                onChange={(e) => setEnTeteCle(e.target.value)}
                className="h-9 text-sm"
              />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="api_valeur_cle" className="text-xs text-muted-foreground">
                Valeur
              </Label>
              <Input
                id="api_valeur_cle"
                type="password"
                value={valeurCle}
                onChange={(e) => setValeurCle(e.target.value)}
                className="h-9 text-sm"
                autoComplete="off"
              />
            </div>
          </>
        )}

        {typeAuth === "porteur" && (
          <div className="space-y-1 sm:col-span-4">
            <Label htmlFor="api_jeton" className="text-xs text-muted-foreground">
              Jeton
            </Label>
            <Input
              id="api_jeton"
              type="password"
              value={jeton}
              onChange={(e) => setJeton(e.target.value)}
              className="h-9 text-sm"
              autoComplete="off"
            />
          </div>
        )}

        {typeAuth === "basique" && (
          <>
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="api_utilisateur" className="text-xs text-muted-foreground">
                Utilisateur
              </Label>
              <Input
                id="api_utilisateur"
                value={utilisateurApi}
                onChange={(e) => setUtilisateurApi(e.target.value)}
                className="h-9 text-sm"
                autoComplete="off"
              />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="api_mot_de_passe" className="text-xs text-muted-foreground">
                Mot de passe
              </Label>
              <Input
                id="api_mot_de_passe"
                type="password"
                value={motDePasseApi}
                onChange={(e) => setMotDePasseApi(e.target.value)}
                className="h-9 text-sm"
                autoComplete="off"
              />
            </div>
          </>
        )}

        {methode === "POST" && (
          <div className="space-y-1 sm:col-span-4">
            <Label htmlFor="api_corps" className="text-xs text-muted-foreground">
              Corps de la requête (optionnel)
            </Label>
            <Textarea
              id="api_corps"
              value={corps}
              onChange={(e) => setCorps(e.target.value)}
              placeholder='{"depuis": "2026-01-01"}'
              className="min-h-20 font-mono text-xs"
            />
          </div>
        )}
      </div>

      {(erreurUrl || erreur) && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <div className="flex items-center gap-2 font-medium">
            <AlertCircle className="h-4 w-4" /> {erreurUrl ? "URL invalide" : "Échec de l'appel"}
          </div>
          <p className="mt-1">{erreurUrl ?? erreur?.message}</p>
        </div>
      )}

      {explorer.isSuccess && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-3 text-xs">
          <div className="flex items-center gap-2 font-medium text-primary">
            <CheckCircle2 className="h-3.5 w-3.5" /> Données récupérées ci-dessous — relisez-les
            avant d'enregistrer la source.
          </div>
        </div>
      )}

      <div className="flex justify-end">
        <Button
          type="button"
          size="sm"
          onClick={extraire}
          disabled={!url.trim() || explorer.isPending}
        >
          <Plug className="mr-2 h-3.5 w-3.5" />
          {explorer.isPending ? "Appel en cours..." : "Appeler l'API"}
        </Button>
      </div>
    </div>
  );
}

// Bloc de statut de l'exécution automatique déclenchée après conversion —
// partagé entre SourceActivePanel (après "Générer une instance"/"Convertir
// sans IA") et ImporteurCsvDirect (après "Importer") : même geste "generate
// once" dans les deux flux, un seul endroit qui sait comment l'afficher.
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

const GABARITS_ENTITE_CSV: Record<EntiteCsv, string> = {
  taches: "/gabarits/taches.csv",
  ressources: "/gabarits/ressources.csv",
  contraintes: "/gabarits/contraintes.csv",
  commandes: "/gabarits/commandes.csv",
};

// Documentation des colonnes attendues par fichier — reflète exactement
// adapters/csv_import/traducteur.py (COLONNES_*_REQUISES/OPTIONNELLES,
// TYPES_CONTRAINTE_SUPPORTES) : une deuxième source de vérité délibérée côté
// frontend, comme GABARITS_ENTITE_CSV ci-dessus — à relire si le schéma
// backend change.
interface ChampDocCsv {
  champ: string;
  requis: boolean;
  type: string;
  valeursAttendues: string;
}

const DOC_CHAMPS_CSV: Record<EntiteCsv, ChampDocCsv[]> = {
  taches: [
    {
      champ: "id",
      requis: true,
      type: "Texte",
      valeursAttendues: "Identifiant unique de la tâche",
    },
    { champ: "nom", requis: false, type: "Texte", valeursAttendues: "Libellé affiché" },
    {
      champ: "duree_estimee_jours",
      requis: false,
      type: "Entier",
      valeursAttendues:
        "Requis seulement si compatibilité dérivée par compétence (voir Contraintes)",
    },
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
      champ: "tache, ressource, duree_jours",
      requis: false,
      type: "Texte / Texte / Entier",
      valeursAttendues: "Requis si type = compatibilite_ressource_tache",
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
      valeursAttendues:
        "Jours relatifs — dérive une échéance par tâche liée, jamais une date calendaire",
    },
  ],
};

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
          S'applique identiquement aux quatre fichiers — jamais deviné automatiquement.
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
                      {DOC_CHAMPS_CSV[entite].map((c) => (
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
                  href={GABARITS_ENTITE_CSV[entite]}
                  download
                  className="inline-flex items-center gap-1 text-xs text-primary underline-offset-2 hover:underline"
                >
                  <Download className="h-3 w-3" /> Télécharger le gabarit {entite}.csv
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

function SourceActivePanel({ sourceId }: { sourceId: string }) {
  const queryClient = useQueryClient();
  const { data: source, isLoading } = useSource(sourceId);
  const generer = useGenererInstanceDepuisSource();
  const genererDeterministe = useGenererInstanceDeterministeDepuisSource();
  const executer = useDeclencherExecution();
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

  const erreur = generer.error as PrismeAPIError | null;
  const erreurDeterministe = genererDeterministe.error as PrismeAPIError | null;

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
    generer.mutate(
      { sourceId },
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

        <details className="rounded-lg border border-border/50 p-3 text-xs">
          <summary className="cursor-pointer font-medium text-muted-foreground">
            Voir les données brutes
          </summary>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-mono">
            {source.donnees_brutes}
          </pre>
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
            <Button
              onClick={genererInstance}
              disabled={generationEnCours || generer.isPending || genererDeterministe.isPending}
            >
              <ArrowRightLeft className="mr-2 h-4 w-4" />
              {generationEnCours || generer.isPending
                ? "Conversion en cours..."
                : "Générer une instance"}
            </Button>
          </div>
        </div>
        {(generationEnCours || generer.isPending) && <IndicateurGeneration />}
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

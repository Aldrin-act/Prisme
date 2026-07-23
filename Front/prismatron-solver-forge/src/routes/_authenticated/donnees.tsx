import { useRef, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { ArrowRightLeft, CheckCircle2, AlertCircle, AlertTriangle, FolderOpen, Plus, Trash2 } from "lucide-react";

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
  useCreerProjet,
  useGenererInstanceDepuisProjet,
  useProjet,
  useProjets,
  useSupprimerProjet,
  PrismeAPIError,
} from "@/integrations/prisme";
import { useAuth } from "@/integrations/prisme/auth";

const searchSchema = z.object({
  projet: z.string().optional(),
});

export const Route = createFileRoute("/_authenticated/donnees")({
  head: () => ({ meta: [{ title: "Données — PRISME" }] }),
  validateSearch: searchSchema,
  component: DonneesPage,
});

function DonneesPage() {
  const { projet } = Route.useSearch();
  const [tab, setTab] = useState<"actif" | "historique">("actif");
  // Pré-rempli depuis l'URL (?projet=<id>) — permet un lien direct depuis la
  // page Instances vers le détail du projet qui a généré une instance donnée.
  const [projetActifId, setProjetActifId] = useState<string | null>(projet ?? null);

  function ouvrirProjet(projetId: string) {
    setProjetActifId(projetId);
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
          <TabsTrigger value="actif">Projet en cours</TabsTrigger>
          <TabsTrigger value="historique">Historique</TabsTrigger>
        </TabsList>

        <TabsContent value="actif" className="max-w-3xl">
          {projetActifId ? (
            <ProjetActifPanel projetId={projetActifId} onNouveau={() => setProjetActifId(null)} />
          ) : (
            <FormulaireNouveauProjet onCree={setProjetActifId} />
          )}
        </TabsContent>

        <TabsContent value="historique">
          <ListeProjets onOuvrir={ouvrirProjet} />
        </TabsContent>
      </Tabs>
    </>
  );
}

function FormulaireNouveauProjet({ onCree }: { onCree: (projetId: string) => void }) {
  const creer = useCreerProjet();
  const inputFichierRef = useRef<HTMLInputElement>(null);
  const { utilisateur } = useAuth();
  const estAdmin = utilisateur?.role === "admin";

  const [clientId, setClientId] = useState(utilisateur?.client_id ?? "");
  const [nom, setNom] = useState("");
  const [donneesBrutes, setDonneesBrutes] = useState("");

  const erreur = creer.error as PrismeAPIError | null;

  async function chargerFichier(fichier: File | null) {
    if (!fichier) return;
    setDonneesBrutes(await fichier.text());
  }

  function enregistrer() {
    creer.mutate(
      { donneesBrutes, nom: nom.trim() || undefined, clientId: estAdmin ? clientId : undefined },
      { onSuccess: (data) => onCree(data.projet_id) },
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
          <Label htmlFor="nom_projet">Nom du projet (optionnel)</Label>
          <Input
            id="nom_projet"
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            placeholder="ex : Export ERP atelier mécanique"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="fichier_brut">Fichier de données brutes (optionnel)</Label>
        <Input
          id="fichier_brut"
          ref={inputFichierRef}
          type="file"
          onChange={(e) => chargerFichier(e.target.files?.[0] ?? null)}
        />
        <p className="text-xs text-muted-foreground">
          Charge le contenu du fichier dans le champ ci-dessous — vous pouvez aussi coller le texte
          directement, quel que soit son format (export CSV, JSON, tableau collé...).
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
          {creer.isPending ? "Enregistrement..." : "Enregistrer le projet"}
        </Button>
      </div>
    </div>
  );
}

function ProjetActifPanel({ projetId, onNouveau }: { projetId: string; onNouveau: () => void }) {
  const queryClient = useQueryClient();
  const { data: projet, isLoading } = useProjet(projetId);
  const generer = useGenererInstanceDepuisProjet();
  const [dernier, setDernier] = useState<{ instance_id: string; avertissements: string[] } | null>(null);

  const erreur = generer.error as PrismeAPIError | null;

  function genererInstance() {
    setDernier(null);
    generer.mutate(projetId, {
      onSuccess: (data) => {
        setDernier({ instance_id: data.instance_id, avertissements: data.avertissements });
        queryClient.invalidateQueries({ queryKey: prismeKeys.projet(projetId) });
        queryClient.invalidateQueries({ queryKey: prismeKeys.projets() });
        queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
      },
    });
  }

  if (isLoading || !projet) {
    return <div className="glass rounded-2xl p-6 text-sm text-muted-foreground">Chargement du projet...</div>;
  }

  return (
    <div className="space-y-4">
      <div className="glass space-y-4 rounded-2xl p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Projet</div>
            <h3 className="text-lg font-semibold">{projet.nom || "Sans nom"}</h3>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span>{projet.client_id}</span>
              <span>·</span>
              <span>{new Date(projet.date_creation).toLocaleString()}</span>
              <span>·</span>
              <Badge variant="outline" className="font-mono">{projet.projet_id}</Badge>
            </div>
          </div>
          <Button variant="outline" onClick={onNouveau}>
            <Plus className="mr-2 h-4 w-4" /> Nouveau projet
          </Button>
        </div>

        <details className="rounded-lg border border-border/50 p-3 text-xs">
          <summary className="cursor-pointer font-medium text-muted-foreground">Voir les données brutes</summary>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap font-mono">{projet.donnees_brutes}</pre>
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

        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            Rejouable à volonté sur ces mêmes données brutes — chaque conversion ajoute une instance à
            l'historique ci-dessous, aucune n'est remplacée.
          </p>
          <Button onClick={genererInstance} disabled={generer.isPending} className="shrink-0">
            <ArrowRightLeft className="mr-2 h-4 w-4" />
            {generer.isPending ? "Conversion en cours..." : "Générer une instance"}
          </Button>
        </div>
        {generer.isPending && (
          <p className="text-right text-xs text-muted-foreground">
            L'agent de compréhension lit vos données — jusqu'à quelques minutes sur un gros volume, merci de
            patienter sans recharger la page.
          </p>
        )}
      </div>

      <div className="glass rounded-2xl p-6">
        <h4 className="mb-3 text-sm font-semibold">Instances générées ({projet.instances.length})</h4>
        {projet.instances.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune instance générée pour l'instant.</p>
        ) : (
          <div className="space-y-2">
            {projet.instances.map((i) => (
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

function ListeProjets({ onOuvrir }: { onOuvrir: (projetId: string) => void }) {
  const { data: projets, isLoading } = useProjets();
  const queryClient = useQueryClient();
  const supprimer = useSupprimerProjet();
  const [aSupprimer, setASupprimer] = useState<string | null>(null);

  const erreurSuppression = supprimer.error as PrismeAPIError | null;

  function ouvrirConfirmation(projetId: string) {
    supprimer.reset();
    setASupprimer(projetId);
  }

  function confirmerSuppression() {
    if (!aSupprimer) return;
    supprimer.mutate(aSupprimer, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: prismeKeys.projets() });
        setASupprimer(null);
      },
    });
  }

  if (!isLoading && projets && projets.length === 0) {
    return (
      <EmptyState
        icon={FolderOpen}
        title="Aucun projet enregistré"
        desc="Enregistrez vos premières données brutes dans l'onglet « Projet en cours » pour les retrouver ici."
      />
    );
  }

  return (
    <>
      <div className="glass overflow-hidden rounded-2xl">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Projet</TableHead>
              <TableHead>Client</TableHead>
              <TableHead>Créé le</TableHead>
              <TableHead>Instances générées</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {projets?.map((p) => (
              <TableRow key={p.projet_id}>
                <TableCell>
                  <div className="font-medium">{p.nom || "Sans nom"}</div>
                  <div className="font-mono text-xs text-muted-foreground">{p.projet_id}</div>
                </TableCell>
                <TableCell>{p.client_id}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {new Date(p.date_creation).toLocaleString()}
                </TableCell>
                <TableCell>
                  <Badge variant={p.nb_instances > 0 ? "secondary" : "outline"}>{p.nb_instances}</Badge>
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="outline" onClick={() => onOuvrir(p.projet_id)}>
                      <FolderOpen className="mr-2 h-3.5 w-3.5" /> Ouvrir
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Supprimer le projet"
                      onClick={() => ouvrirConfirmation(p.projet_id)}
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
            <AlertDialogTitle>Supprimer ce projet ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action supprime définitivement les données brutes du projet. Les instances déjà générées
              à partir de lui restent intactes — seul le lien vers ce projet disparaît. Cette action est
              irréversible.
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

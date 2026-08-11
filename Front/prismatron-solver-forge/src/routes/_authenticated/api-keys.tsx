import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { AlertCircle, AlertTriangle, Check, Copy, KeyRound, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  useClesApi,
  useCreerCleApi,
  useRevoquerCleApi,
  PrismeAPIError,
} from "@/integrations/prisme";
import type * as Types from "@/integrations/prisme/types";

export const Route = createFileRoute("/_authenticated/api-keys")({
  head: () => ({ meta: [{ title: "Clés API — PRISME" }] }),
  component: ApiKeysPage,
});

function ApiKeysPage() {
  const [dialogOuvert, setDialogOuvert] = useState(false);
  const [secretRevele, setSecretRevele] = useState<Types.ReponseCreationCleApi | null>(null);
  const { data: cles, isLoading } = useClesApi();

  const boutonNouvelleCle = (
    <Button
      className="bg-gradient-to-r from-primary to-accent"
      onClick={() => setDialogOuvert(true)}
    >
      <Plus className="mr-2 h-4 w-4" /> Nouvelle clé
    </Button>
  );

  return (
    <>
      <PageHeader
        title="Clés API"
        desc="Clés révocables et limitées en portée pour un accès programmatique à vos instances, solveurs et plannings."
        action={boutonNouvelleCle}
      />

      {!isLoading && cles && cles.length === 0 && (
        <EmptyState
          icon={KeyRound}
          title="Aucune clé API"
          desc="Créez une clé pour authentifier un script ou une CI sans rejouer un login à chaque appel."
          action={boutonNouvelleCle}
        />
      )}

      {cles && cles.length > 0 && <TableClesApi cles={cles} />}

      <DialogNouvelleCleApi
        open={dialogOuvert}
        onOpenChange={setDialogOuvert}
        onCreee={setSecretRevele}
      />
      <DialogSecretRevele reponse={secretRevele} onFermer={() => setSecretRevele(null)} />
    </>
  );
}

function TableClesApi({ cles }: { cles: Types.CleApi[] }) {
  const queryClient = useQueryClient();
  const revoquer = useRevoquerCleApi();
  const [aRevoquer, setARevoquer] = useState<string | null>(null);

  const erreurRevocation = revoquer.error as PrismeAPIError | null;

  function ouvrirConfirmation(cleId: string) {
    revoquer.reset();
    setARevoquer(cleId);
  }

  function confirmerRevocation() {
    if (!aRevoquer) return;
    revoquer.mutate(aRevoquer, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: prismeKeys.clesApi() });
        setARevoquer(null);
      },
    });
  }

  return (
    <>
      <div className="glass overflow-hidden rounded-2xl">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nom</TableHead>
              <TableHead>Clé</TableHead>
              <TableHead>Créée</TableHead>
              <TableHead>Dernière utilisation</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {cles.map((c) => (
              <TableRow key={c.cle_id}>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <KeyRound className="h-4 w-4 text-primary" /> {c.nom}
                  </div>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  {c.prefixe}…
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {new Date(c.date_creation).toLocaleString()}
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {c.derniere_utilisation
                    ? new Date(c.derniere_utilisation).toLocaleString()
                    : "Jamais"}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label="Révoquer la clé"
                    onClick={() => ouvrirConfirmation(c.cle_id)}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <AlertDialog open={!!aRevoquer} onOpenChange={(open) => !open && setARevoquer(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Révoquer cette clé ?</AlertDialogTitle>
            <AlertDialogDescription>
              Toute application ou script utilisant cette clé perdra immédiatement l'accès à l'API.
              Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>

          {erreurRevocation && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              <div className="flex items-center gap-2 font-medium">
                <AlertCircle className="h-4 w-4" /> Échec de la révocation
              </div>
              <p className="mt-1">{erreurRevocation.message}</p>
            </div>
          )}

          <AlertDialogFooter>
            <AlertDialogCancel disabled={revoquer.isPending}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmerRevocation}
              disabled={revoquer.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {revoquer.isPending ? "Révocation..." : "Révoquer"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function DialogNouvelleCleApi({
  open,
  onOpenChange,
  onCreee,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreee: (reponse: Types.ReponseCreationCleApi) => void;
}) {
  const creer = useCreerCleApi();
  const [nom, setNom] = useState("");

  const erreur = creer.error as PrismeAPIError | null;

  function reinitialiser() {
    setNom("");
    creer.reset();
  }

  function fermer(open: boolean) {
    if (!open) reinitialiser();
    onOpenChange(open);
  }

  function soumettre() {
    creer.mutate(nom.trim(), {
      onSuccess: (reponse) => {
        fermer(false);
        onCreee(reponse);
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={fermer}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouvelle clé API</DialogTitle>
          <DialogDescription>
            Cette clé aura exactement les mêmes droits que votre compte. Le nom sert uniquement à la
            reconnaître dans la liste (ex. « ci-readonly ») — sans effet sur ses permissions.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="nouvelle_cle_nom">Nom</Label>
            <Input
              id="nouvelle_cle_nom"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              placeholder="ex : ci-readonly"
            />
          </div>

          {erreur && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              <div className="flex items-center gap-2 font-medium">
                <AlertCircle className="h-4 w-4" /> Échec de la création
              </div>
              <p className="mt-1">{erreur.message}</p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => fermer(false)}>
            Annuler
          </Button>
          <Button onClick={soumettre} disabled={creer.isPending || !nom.trim()}>
            {creer.isPending ? "Création..." : "Créer la clé"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DialogSecretRevele({
  reponse,
  onFermer,
}: {
  reponse: Types.ReponseCreationCleApi | null;
  onFermer: () => void;
}) {
  const queryClient = useQueryClient();
  const [copie, setCopie] = useState(false);

  async function copier() {
    if (!reponse) return;
    await navigator.clipboard.writeText(reponse.secret);
    setCopie(true);
    toast.success("Copié dans le presse-papiers");
  }

  function confirmer() {
    queryClient.invalidateQueries({ queryKey: prismeKeys.clesApi() });
    setCopie(false);
    onFermer();
  }

  return (
    <Dialog open={!!reponse} onOpenChange={(open) => !open && confirmer()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Clé créée{reponse ? ` : ${reponse.nom}` : ""}</DialogTitle>
          <DialogDescription>
            Cette clé ne sera plus jamais affichée en clair — copiez-la maintenant et conservez-la
            dans un endroit sûr (gestionnaire de secrets, variable d'environnement CI...).
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="flex items-center gap-2 rounded-lg border border-border/50 bg-muted/30 p-3">
            <code className="flex-1 overflow-x-auto whitespace-nowrap font-mono text-xs">
              {reponse?.secret}
            </code>
            <Button size="sm" variant="ghost" onClick={copier}>
              {copie ? (
                <Check className="mr-2 h-4 w-4 text-emerald-500" />
              ) : (
                <Copy className="mr-2 h-4 w-4" />
              )}
              {copie ? "Copiée" : "Copier"}
            </Button>
          </div>
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            <div className="flex items-center gap-2 font-medium text-amber-600 dark:text-amber-400">
              <AlertTriangle className="h-4 w-4" /> Vous ne pourrez plus revoir cette clé
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button onClick={confirmer}>J'ai copié ma clé</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

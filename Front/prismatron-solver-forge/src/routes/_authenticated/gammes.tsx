import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { Pencil, Plus, Trash2, Workflow } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { GammeEditor } from "@/components/planning/gamme-editor";
import { prismeKeys, useGammes, useSupprimerGamme, type GammeProduit } from "@/integrations/prisme";

export const Route = createFileRoute("/_authenticated/gammes")({
  head: () => ({ meta: [{ title: "Gammes — PRISME" }] }),
  component: GammesPage,
});

function GammesPage() {
  const { data: gammes, isLoading } = useGammes();
  const [gammeAEditer, setGammeAEditer] = useState<GammeProduit | "nouvelle" | null>(null);
  const [aSupprimer, setASupprimer] = useState<string | null>(null);

  const boutonNouvelleGamme = (
    <Button
      className="bg-gradient-to-r from-primary to-accent"
      onClick={() => setGammeAEditer("nouvelle")}
    >
      <Plus className="mr-2 h-4 w-4" /> Nouvelle gamme
    </Button>
  );

  return (
    <>
      <PageHeader
        title="Gammes"
        desc="Décrivez une fois, par produit, la séquence d'étapes (compétences requises, ordre) — une commande peut référencer une ou plusieurs gammes, explosées automatiquement en tâches concrètes plutôt que ressaisies à la main."
        action={boutonNouvelleGamme}
      />

      {!isLoading && gammes && gammes.length === 0 && (
        <EmptyState
          icon={Workflow}
          title="Aucune gamme enregistrée"
          desc="Créez une première gamme pour pouvoir exploser des commandes automatiquement depuis l'onglet Flux d'une instance."
          action={boutonNouvelleGamme}
        />
      )}

      {gammes && gammes.length > 0 && (
        <div className="glass overflow-hidden rounded-2xl">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Produit</TableHead>
                <TableHead>Nom</TableHead>
                <TableHead>Étapes</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {gammes.map((g) => (
                <TableRow key={g.gamme_id}>
                  <TableCell className="font-medium">{g.produit}</TableCell>
                  <TableCell>{g.nom || <span className="text-muted-foreground">—</span>}</TableCell>
                  <TableCell>
                    <Badge variant="outline">{g.etapes.length}</Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button size="sm" variant="ghost" onClick={() => setGammeAEditer(g)}>
                      <Pencil className="h-3.5 w-3.5" />
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setASupprimer(g.gamme_id)}>
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <DialogGamme
        gammeAEditer={gammeAEditer}
        onOpenChange={(open) => !open && setGammeAEditer(null)}
      />
      <DialogSuppressionGamme
        gammeId={aSupprimer}
        onOpenChange={(open) => !open && setASupprimer(null)}
      />
    </>
  );
}

function DialogGamme({
  gammeAEditer,
  onOpenChange,
}: {
  gammeAEditer: GammeProduit | "nouvelle" | null;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();

  function fermerApresEnregistrement() {
    queryClient.invalidateQueries({ queryKey: prismeKeys.gammes() });
    onOpenChange(false);
  }

  return (
    <Dialog open={!!gammeAEditer} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-4xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {gammeAEditer === "nouvelle" ? "Nouvelle gamme" : "Modifier la gamme"}
          </DialogTitle>
          <DialogDescription>
            Chaque étape déclare les compétences qu'elle exige — la ressource compatible se résout
            automatiquement à l'explosion d'une commande, pas ici.
          </DialogDescription>
        </DialogHeader>

        {gammeAEditer && (
          <GammeEditor
            gamme={gammeAEditer === "nouvelle" ? undefined : gammeAEditer}
            onEnregistre={fermerApresEnregistrement}
            onAnnuler={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function DialogSuppressionGamme({
  gammeId,
  onOpenChange,
}: {
  gammeId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const supprimer = useSupprimerGamme();

  function confirmer() {
    if (!gammeId) return;
    supprimer.mutate(gammeId, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: prismeKeys.gammes() });
        onOpenChange(false);
      },
    });
  }

  return (
    <AlertDialog open={!!gammeId} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Supprimer cette gamme ?</AlertDialogTitle>
          <AlertDialogDescription>
            Les tâches déjà explosées à partir d'elle dans des instances existantes ne sont pas
            affectées — seule la gamme elle-même (le gabarit réutilisable) disparaît.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={supprimer.isPending}>Annuler</AlertDialogCancel>
          <AlertDialogAction onClick={confirmer} disabled={supprimer.isPending}>
            {supprimer.isPending ? "Suppression..." : "Supprimer"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

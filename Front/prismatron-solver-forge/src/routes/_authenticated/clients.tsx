import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";
import { AlertCircle, Building2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageHeader, EmptyState } from "@/components/app-page";
import { prismeKeys, useClients, useCreerClient, PrismeAPIError } from "@/integrations/prisme";
import { useAuth } from "@/integrations/prisme/auth";

export const Route = createFileRoute("/_authenticated/clients")({
  head: () => ({ meta: [{ title: "Clients — PRISME" }] }),
  component: ClientsPage,
});

function ClientsPage() {
  const { utilisateur } = useAuth();
  const [dialogOuvert, setDialogOuvert] = useState(false);
  const { data: clients, isLoading } = useClients();

  if (utilisateur?.role !== "admin") {
    return (
      <EmptyState
        icon={Building2}
        title="Accès réservé aux administrateurs"
        desc="La gestion des clients (tenants) n'est visible que pour le rôle admin."
      />
    );
  }

  const boutonNouveauClient = (
    <Button className="bg-gradient-to-r from-primary to-accent" onClick={() => setDialogOuvert(true)}>
      <Plus className="mr-2 h-4 w-4" /> Nouveau client
    </Button>
  );

  return (
    <>
      <PageHeader
        title="Clients"
        desc="Chaque client (tenant) cloisonne les données : sources, instances, solveurs générés. Un utilisateur appartient à un client et ne voit que les données de celui-ci, sauf rôle admin."
        action={boutonNouveauClient}
      />

      {!isLoading && clients && clients.length === 0 && (
        <EmptyState
          icon={Building2}
          title="Aucun client enregistré"
          desc="Créez votre premier client pour pouvoir y rattacher des comptes utilisateurs."
          action={boutonNouveauClient}
        />
      )}

      {clients && clients.length > 0 && (
        <div className="glass overflow-hidden rounded-2xl">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>client_id</TableHead>
                <TableHead>Nom</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {clients.map((c) => (
                <TableRow key={c.client_id}>
                  <TableCell className="font-mono text-xs">{c.client_id}</TableCell>
                  <TableCell>{c.nom || <span className="text-muted-foreground">—</span>}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <DialogNouveauClient open={dialogOuvert} onOpenChange={setDialogOuvert} />
    </>
  );
}

function DialogNouveauClient({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient();
  const creer = useCreerClient();
  const [clientId, setClientId] = useState("");
  const [nom, setNom] = useState("");

  const erreur = creer.error as PrismeAPIError | null;

  function reinitialiser() {
    setClientId("");
    setNom("");
    creer.reset();
  }

  function fermer(open: boolean) {
    if (!open) reinitialiser();
    onOpenChange(open);
  }

  function soumettre() {
    creer.mutate(
      { clientId, nom: nom.trim() || undefined },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: prismeKeys.clients() });
          fermer(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={fermer}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nouveau client</DialogTitle>
          <DialogDescription>
            Le client_id identifie ce tenant partout dans le système (matching des solveurs, cloisonnement des
            données) — choisissez-le avec soin, il n'est pas modifiable après création.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="nouveau_client_id">client_id</Label>
            <Input
              id="nouveau_client_id"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="ex : atelier-mecanique"
              className="font-mono text-sm"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nouveau_client_nom">Nom (optionnel)</Label>
            <Input
              id="nouveau_client_nom"
              value={nom}
              onChange={(e) => setNom(e.target.value)}
              placeholder="ex : Atelier Mécanique SARL"
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
          <Button onClick={soumettre} disabled={creer.isPending || !clientId.trim()}>
            {creer.isPending ? "Création..." : "Créer le client"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

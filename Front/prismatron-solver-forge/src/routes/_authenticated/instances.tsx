import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, FolderKanban, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { IngestionDialog } from "@/components/ingestion/ingestion-dialog";
import { prismeKeys, useInstances, useSupprimerInstance, PrismeAPIError } from "@/integrations/prisme";

export const Route = createFileRoute("/_authenticated/instances")({
  head: () => ({ meta: [{ title: "Instances — PRISME" }] }),
  component: InstancesPage,
});

function InstancesPage() {
  const [dialogOuvert, setDialogOuvert] = useState(false);
  const [aSupprimer, setASupprimer] = useState<string | null>(null);
  const { data: instances, isLoading } = useInstances();
  const queryClient = useQueryClient();
  const supprimer = useSupprimerInstance();

  const boutonNouvelleInstance = (
    <Button className="bg-gradient-to-r from-primary to-accent" onClick={() => setDialogOuvert(true)}>
      <Plus className="mr-2 h-4 w-4" /> Nouvelle instance
    </Button>
  );

  function ouvrirConfirmation(instanceId: string) {
    supprimer.reset();
    setASupprimer(instanceId);
  }

  function confirmerSuppression() {
    if (!aSupprimer) return;
    supprimer.mutate(aSupprimer, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
        queryClient.invalidateQueries({ queryKey: prismeKeys.executions() });
        queryClient.invalidateQueries({ queryKey: prismeKeys.projets() });
        setASupprimer(null);
      },
    });
  }

  const erreurSuppression = supprimer.error as PrismeAPIError | null;

  return (
    <>
      <PageHeader
        title="Instances"
        desc="Regroupez vos problèmes de planification, définitions DSL et solveurs générés en instances."
        action={boutonNouvelleInstance}
      />

      {!isLoading && instances && instances.length === 0 && (
        <EmptyState
          icon={FolderKanban}
          title="Aucune instance pour l'instant"
          desc="Une instance regroupe votre DSL, vos solveurs générés, vos exécutions et votre historique d'audit. Créez votre première instance pour commencer."
          action={boutonNouvelleInstance}
        />
      )}

      {instances && instances.length > 0 && (
        <div className="glass overflow-hidden rounded-2xl">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Instance</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Structure des contraintes</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {instances.map((instance) => (
                <TableRow key={instance.instance_id}>
                  <TableCell className="font-mono text-xs">{instance.instance_id}</TableCell>
                  <TableCell>{instance.client_id}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">
                      {instance.structure_contraintes}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant={instance.executee ? "secondary" : "outline"}>
                      {instance.executee ? "Exécutée" : "En attente"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label="Supprimer l'instance"
                      onClick={() => ouvrirConfirmation(instance.instance_id)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <IngestionDialog open={dialogOuvert} onOpenChange={setDialogOuvert} />

      <AlertDialog open={!!aSupprimer} onOpenChange={(open) => !open && setASupprimer(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette instance ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action supprime définitivement l'instance <span className="font-mono text-xs">{aSupprimer}</span>{" "}
              ainsi que tout son historique d'exécution (plannings, décisions humaines). Les solveurs enregistrés
              ne sont pas affectés. Cette action est irréversible.
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

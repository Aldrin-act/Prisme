import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { FolderKanban, Plus } from "lucide-react";
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
import { PageHeader, EmptyState } from "@/components/app-page";
import { IngestionDialog } from "@/components/ingestion/ingestion-dialog";
import { useInstances } from "@/integrations/prisme";

export const Route = createFileRoute("/_authenticated/instances")({
  head: () => ({ meta: [{ title: "Instances — PRISME" }] }),
  component: InstancesPage,
});

function InstancesPage() {
  const [dialogOuvert, setDialogOuvert] = useState(false);
  const { data: instances, isLoading } = useInstances();

  const boutonNouvelleInstance = (
    <Button className="bg-gradient-to-r from-primary to-accent" onClick={() => setDialogOuvert(true)}>
      <Plus className="mr-2 h-4 w-4" /> Nouvelle instance
    </Button>
  );

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
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <IngestionDialog open={dialogOuvert} onOpenChange={setDialogOuvert} />
    </>
  );
}

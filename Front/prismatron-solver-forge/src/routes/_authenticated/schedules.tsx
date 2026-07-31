import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Calendar, CheckCircle2, Eye, HelpCircle, XCircle } from "lucide-react";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageHeader, EmptyState } from "@/components/app-page";
import { GanttChart } from "@/components/planning/gantt-chart";
import {
  useExecutions,
  useLabelsInstances,
  usePlanning,
  PrismeAPIError,
  type ExecutionInfo,
} from "@/integrations/prisme";

export const Route = createFileRoute("/_authenticated/schedules")({
  head: () => ({ meta: [{ title: "Plannings — PRISME" }] }),
  component: SchedulesPage,
});

function BadgeDecision({ decision }: { decision: ExecutionInfo["decision"] }) {
  if (decision === "acceptee") {
    return (
      <Badge variant="secondary" className="gap-1">
        <CheckCircle2 className="h-3 w-3" /> Approuvé
      </Badge>
    );
  }
  if (decision === "refusee") {
    return (
      <Badge variant="destructive" className="gap-1">
        <XCircle className="h-3 w-3" /> Rejeté
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <HelpCircle className="h-3 w-3" /> En attente
    </Badge>
  );
}

function SchedulesPage() {
  const { data: executions, isLoading } = useExecutions();
  const labels = useLabelsInstances();
  const [aVoir, setAVoir] = useState<ExecutionInfo | null>(null);

  const executionsTriees = [...(executions ?? [])].sort((a, b) =>
    (b.date_execution ?? "").localeCompare(a.date_execution ?? ""),
  );

  return (
    <>
      <PageHeader
        title="Plannings"
        desc="Les plannings proposés par chaque exécution de solveur — un par exécution, jamais recalculés à la volée : ce que le bac à sable a produit, tel quel."
      />

      {!isLoading && executionsTriees.length === 0 && (
        <EmptyState
          icon={Calendar}
          title="Aucun planning pour l'instant"
          desc="Exécute un solveur depuis la page Solveurs générés pour voir son planning apparaître ici."
        />
      )}

      {executionsTriees.length > 0 && (
        <div className="glass overflow-hidden rounded-2xl">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Instance</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Date d'exécution</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead>Décision</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {executionsTriees.map((e) => (
                <TableRow key={e.execution_id}>
                  <TableCell>{labels.get(e.instance_id)?.label ?? e.instance_id}</TableCell>
                  <TableCell>{e.client_id}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {e.date_execution ? new Date(e.date_execution).toLocaleString() : "—"}
                  </TableCell>
                  <TableCell>
                    {e.reussi ? (
                      <Badge variant="secondary" className="gap-1">
                        <CheckCircle2 className="h-3 w-3" /> Réussi
                      </Badge>
                    ) : (
                      <Badge variant="destructive" className="gap-1">
                        <XCircle className="h-3 w-3" /> Échec
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{e.reussi ? <BadgeDecision decision={e.decision} /> : "—"}</TableCell>
                  <TableCell className="text-right">
                    {e.reussi ? (
                      <Button size="sm" variant="outline" onClick={() => setAVoir(e)}>
                        <Eye className="mr-1.5 h-3.5 w-3.5" /> Voir le planning
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground" title={e.erreur ?? undefined}>
                        {e.erreur ? "Erreur à l'exécution" : ""}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <DialogPlanning execution={aVoir} onOpenChange={(open) => !open && setAVoir(null)} />
    </>
  );
}

function DialogPlanning({
  execution,
  onOpenChange,
}: {
  execution: ExecutionInfo | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: planning, isLoading, error } = usePlanning(execution?.execution_id ?? null);

  return (
    <Dialog open={!!execution} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Planning</DialogTitle>
          <DialogDescription className="font-mono text-xs">
            {execution?.execution_id}
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <p className="text-sm text-muted-foreground">Chargement du planning...</p>
        ) : error ? (
          <p className="text-sm text-destructive">{(error as PrismeAPIError).message}</p>
        ) : planning ? (
          <GanttChart planning={planning} />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

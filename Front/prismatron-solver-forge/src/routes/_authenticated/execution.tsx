import { createFileRoute, Link } from "@tanstack/react-router";
import { CheckCircle2, Play, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { PageHeader, EmptyState } from "@/components/app-page";
import { useExecutions, useSante, useLabelsInstances } from "@/integrations/prisme";

export const Route = createFileRoute("/_authenticated/execution")({
  head: () => ({ meta: [{ title: "Centre d'exécution — PRISME" }] }),
  component: CentreExecutionPage,
});

function CentreExecutionPage() {
  const { data: executions, isLoading } = useExecutions();
  const { data: sante } = useSante();
  const labels = useLabelsInstances();

  const aujourdHui = new Date().toDateString();
  const executionsAujourdhui =
    executions?.filter((e) => e.date_execution && new Date(e.date_execution).toDateString() === aujourdHui)
      .length ?? 0;
  const nbReussies = executions?.filter((e) => e.reussi).length ?? 0;
  const tauxReussite =
    executions && executions.length > 0 ? `${Math.round((nbReussies / executions.length) * 100)}%` : "—";

  return (
    <>
      <PageHeader
        title="Centre d'exécution"
        desc="Chaque solveur s'exécute dans un bac à sable isolé avec des limites de ressources strictes. Rien ne fuite. Une exécution se déclenche depuis « Solveurs générés »."
        action={
          <Link
            to="/solvers"
            className="inline-flex items-center gap-2 rounded-lg bg-gradient-to-r from-primary to-accent px-4 py-2 text-sm font-medium text-primary-foreground"
          >
            <Play className="h-4 w-4" /> Nouvelle exécution
          </Link>
        }
      />

      <div className="grid gap-4 md:grid-cols-3">
        <div className="glass rounded-2xl p-5">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">Exécutions aujourd'hui</div>
          <div className="mt-2 text-3xl font-bold">{executionsAujourdhui}</div>
        </div>
        <div className="glass rounded-2xl p-5">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">Taux de réussite</div>
          <div className="mt-2 text-3xl font-bold">{tauxReussite}</div>
        </div>
        <div className="glass rounded-2xl p-5">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">Disponibilité du bac à sable</div>
          <div className="mt-2 text-3xl font-bold">
            {sante ? (sante.sandbox_docker ? "100%" : "0%") : "—"}
          </div>
        </div>
      </div>

      {!isLoading && executions && executions.length === 0 && (
        <div className="mt-6">
          <EmptyState
            icon={Play}
            title="Aucune exécution pour l'instant"
            desc="Déclenchez une exécution depuis la page « Solveurs générés » pour la voir apparaître ici."
          />
        </div>
      )}

      {executions && executions.length > 0 && (
        <div className="glass mt-6 overflow-hidden rounded-2xl">
          <div className="border-b border-border/50 px-5 py-3 text-sm font-semibold">Exécutions récentes</div>
          <ul>
            {executions.map((e) => (
              <li
                key={e.execution_id}
                className="flex items-center justify-between border-b border-border/30 px-5 py-4 text-sm last:border-0"
              >
                <div className="flex items-center gap-3">
                  {e.reussi ? (
                    <CheckCircle2 className="h-4 w-4 text-primary" />
                  ) : (
                    <XCircle className="h-4 w-4 text-destructive" />
                  )}
                  <span className="font-mono text-xs">{e.execution_id}</span>
                  <span className="text-muted-foreground">
                    {labels.get(e.instance_id)?.label ?? e.instance_id}
                  </span>
                  <Badge variant="outline" className="text-xs">
                    {e.client_id}
                  </Badge>
                </div>
                <div className="text-xs text-muted-foreground">
                  {e.date_execution ? new Date(e.date_execution).toLocaleString() : "—"}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}

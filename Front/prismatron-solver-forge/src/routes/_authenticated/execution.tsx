import { createFileRoute } from "@tanstack/react-router";
import { Play, CheckCircle2, XCircle, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/app-page";

const RUNS = [
  { id: "run_912", solver: "assembly-line-v3", status: "success", duration: "4,2s", icon: CheckCircle2 },
  { id: "run_911", solver: "smt-line-v1", status: "running", duration: "12s", icon: Clock },
  { id: "run_910", solver: "assembly-line-v2", status: "failed", duration: "1,1s", icon: XCircle },
];

export const Route = createFileRoute("/_authenticated/execution")({
  head: () => ({ meta: [{ title: "Centre d'exécution — PRISME" }] }),
  component: () => (
    <>
      <PageHeader
        title="Centre d'exécution"
        desc="Chaque solveur s'exécute dans un bac à sable isolé avec des limites de ressources strictes. Rien ne fuite."
        action={
          <Button className="bg-gradient-to-r from-primary to-accent">
            <Play className="mr-2 h-4 w-4" /> Nouvelle exécution
          </Button>
        }
      />
      <div className="grid gap-4 md:grid-cols-3">
        {[
          { l: "Exécutions aujourd'hui", v: "0" },
          { l: "Temps moyen", v: "—" },
          { l: "Disponibilité du bac à sable", v: "100%" },
        ].map((k) => (
          <div key={k.l} className="glass rounded-2xl p-5">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">{k.l}</div>
            <div className="mt-2 text-3xl font-bold">{k.v}</div>
          </div>
        ))}
      </div>
      <div className="glass mt-6 overflow-hidden rounded-2xl">
        <div className="border-b border-border/50 px-5 py-3 text-sm font-semibold">Exécutions récentes</div>
        <ul>
          {RUNS.map((r) => (
            <li
              key={r.id}
              className="flex items-center justify-between border-b border-border/30 px-5 py-4 text-sm last:border-0"
            >
              <div className="flex items-center gap-3">
                <r.icon
                  className={`h-4 w-4 ${
                    r.status === "success"
                      ? "text-primary"
                      : r.status === "failed"
                        ? "text-destructive"
                        : "text-accent"
                  }`}
                />
                <span className="font-mono text-xs">{r.id}</span>
                <span className="text-muted-foreground">{r.solver}</span>
              </div>
              <div className="text-xs text-muted-foreground">{r.duration}</div>
            </li>
          ))}
        </ul>
      </div>
    </>
  ),
});

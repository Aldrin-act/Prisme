import { createFileRoute } from "@tanstack/react-router";
import { Cpu, Sparkles, CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/app-page";

const STEPS = [
  { icon: Sparkles, label: "Analyser le DSL", status: "done" },
  { icon: Cpu, label: "Rédiger le solveur", status: "done" },
  { icon: Loader2, label: "Valider et expliquer", status: "running" },
  { icon: CheckCircle2, label: "Enregistrer l'artefact", status: "pending" },
];

export const Route = createFileRoute("/_authenticated/solver-generator")({
  head: () => ({ meta: [{ title: "Générateur de solveurs — PRISME" }] }),
  component: () => (
    <>
      <PageHeader
        title="Générateur de solveurs"
        desc="Observez le pipeline multi-agents transformer votre DSL en solveur OR-Tools signé et validé."
        action={
          <Button className="bg-gradient-to-r from-primary to-accent">Lancer la génération</Button>
        }
      />
      <div className="glass rounded-2xl p-6">
        <div className="grid gap-4 md:grid-cols-4">
          {STEPS.map((s, i) => {
            const running = s.status === "running";
            const done = s.status === "done";
            return (
              <div key={s.label} className="relative">
                <div className="glass flex items-center gap-3 rounded-xl p-4">
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                      done
                        ? "bg-gradient-to-br from-primary to-accent text-white"
                        : running
                          ? "bg-primary/20 text-primary"
                          : "bg-muted text-muted-foreground"
                    }`}
                  >
                    <s.icon className={`h-5 w-5 ${running ? "animate-spin" : ""}`} />
                  </div>
                  <div>
                    <div className="text-xs uppercase tracking-widest text-muted-foreground">
                      Agent {i + 1}
                    </div>
                    <div className="text-sm font-semibold">{s.label}</div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-6 rounded-xl border border-border/50 p-4 font-mono text-xs text-muted-foreground">
          <div>[parser] 4 ressources, 2 tâches, 3 contraintes, 1 objectif — OK</div>
          <div>[generator] génération de model.py — 132 lignes</div>
          <div>[validator] exécution des tests de propriétés… 12/18 réussis</div>
        </div>
      </div>
    </>
  ),
});

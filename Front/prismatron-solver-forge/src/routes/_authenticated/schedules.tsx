import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-page";

const JOBS = ["Peinture-Carrosserie", "Portes", "Montage-Moteur", "QA", "Emballage"];
const CELLS = Array.from({ length: 12 }, (_, i) => i);

export const Route = createFileRoute("/_authenticated/schedules")({
  head: () => ({ meta: [{ title: "Plannings — PRISME" }] }),
  component: () => (
    <>
      <PageHeader
        title="Plannings"
        desc="Plans de production optimisés, prêts pour l'atelier. Sortie Gantt avec voies par ressource."
      />
      <div className="glass overflow-hidden rounded-2xl p-6">
        <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
          <div>Ligne 1 · Semaine 42</div>
          <div>Durée totale : 8h 14min · Utilisation 92%</div>
        </div>
        <div className="space-y-2">
          {JOBS.map((j, ri) => (
            <div key={j} className="flex items-center gap-3">
              <div className="w-24 shrink-0 text-xs text-muted-foreground">{j}</div>
              <div className="grid flex-1 grid-cols-12 gap-1">
                {CELLS.map((c) => {
                  const start = (ri * 2 + 1) % 12;
                  const span = 2 + (ri % 3);
                  const active = c >= start && c < start + span;
                  return (
                    <div
                      key={c}
                      className={`h-8 rounded-md ${
                        active
                          ? "bg-gradient-to-r from-primary to-accent"
                          : "bg-muted/40"
                      }`}
                    />
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </>
  ),
});

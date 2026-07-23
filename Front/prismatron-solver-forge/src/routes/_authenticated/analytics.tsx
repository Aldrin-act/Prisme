import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/app-page";

const BARS = [12, 18, 22, 16, 28, 34, 30, 40, 44, 38, 52, 48];

export const Route = createFileRoute("/_authenticated/analytics")({
  head: () => ({ meta: [{ title: "Analytique — PRISME" }] }),
  component: () => (
    <>
      <PageHeader
        title="Analytique"
        desc="Performance des solveurs, KPI de planification et tendances de génération sur toutes vos instances."
      />
      <div className="grid gap-4 md:grid-cols-4">
        {[
          { l: "Durée totale moyenne", v: "6h 42min", d: "-12%" },
          { l: "TRS", v: "82,3%", d: "+3,1%" },
          { l: "Succès des solveurs", v: "97%", d: "+1%" },
          { l: "P95 bac à sable", v: "5,9s", d: "-0,4s" },
        ].map((k) => (
          <div key={k.l} className="glass rounded-2xl p-5">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">{k.l}</div>
            <div className="mt-2 text-3xl font-bold">{k.v}</div>
            <div className="mt-1 text-xs text-primary">{k.d}</div>
          </div>
        ))}
      </div>
      <div className="glass mt-6 rounded-2xl p-6">
        <div className="mb-3 text-sm font-semibold">Exécutions de solveurs (12 dernières semaines)</div>
        <div className="flex h-40 items-end gap-2">
          {BARS.map((b, i) => (
            <div
              key={i}
              className="flex-1 rounded-t-md bg-gradient-to-t from-primary/70 to-accent"
              style={{ height: `${(b / 60) * 100}%` }}
            />
          ))}
        </div>
      </div>
    </>
  ),
});

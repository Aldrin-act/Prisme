import { createFileRoute } from "@tanstack/react-router";
import { FileCode2, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/app-page";

const SOLVERS = [
  { name: "assembly-line-v3", instance: "Automobile · FR-01", status: "Actif", when: "il y a 2h" },
  { name: "smt-line-v1", instance: "Électronique · Cellule A", status: "Brouillon", when: "hier" },
  { name: "maintenance-q3", instance: "Ops usine", status: "Archivé", when: "il y a 3 jours" },
];

export const Route = createFileRoute("/_authenticated/solvers")({
  head: () => ({ meta: [{ title: "Solveurs générés — PRISME" }] }),
  component: () => (
    <>
      <PageHeader
        title="Solveurs générés"
        desc="Chaque solveur rédigé, versionné et signé par PRISME. Exportez en Python ou promouvez en production."
      />
      <div className="glass overflow-hidden rounded-2xl">
        <table className="w-full text-sm">
          <thead className="border-b border-border/50 text-left text-xs uppercase tracking-widest text-muted-foreground">
            <tr>
              <th className="px-5 py-3">Solveur</th>
              <th className="px-5 py-3">Instance</th>
              <th className="px-5 py-3">Statut</th>
              <th className="px-5 py-3">Généré</th>
              <th className="px-5 py-3" />
            </tr>
          </thead>
          <tbody>
            {SOLVERS.map((s) => (
              <tr key={s.name} className="border-b border-border/30 last:border-0">
                <td className="px-5 py-4">
                  <div className="flex items-center gap-2">
                    <FileCode2 className="h-4 w-4 text-primary" /> {s.name}
                  </div>
                </td>
                <td className="px-5 py-4 text-muted-foreground">{s.instance}</td>
                <td className="px-5 py-4">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      s.status === "Actif"
                        ? "bg-primary/20 text-primary"
                        : s.status === "Brouillon"
                          ? "bg-accent/20 text-accent"
                          : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {s.status}
                  </span>
                </td>
                <td className="px-5 py-4 text-muted-foreground">{s.when}</td>
                <td className="px-5 py-4 text-right">
                  <Button variant="ghost" size="sm">
                    <Download className="mr-2 h-4 w-4" /> Exporter
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  ),
});

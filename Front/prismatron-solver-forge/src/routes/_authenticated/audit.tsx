import { createFileRoute } from "@tanstack/react-router";
import { ClipboardList } from "lucide-react";
import { PageHeader } from "@/components/app-page";

const EVENTS = [
  { t: "il y a 2min", who: "vous", what: "Solveur assembly-line-v3 approuvé → Production" },
  { t: "il y a 18min", who: "ai-generator", what: "Brouillon de solveur v3 émis (132 lignes de code)" },
  { t: "il y a 22min", who: "validator", what: "18/18 tests de propriétés réussis sur v2" },
  { t: "il y a 1h", who: "sandbox", what: "Exécution de run_907 (4,2s, code de sortie 0)" },
  { t: "hier", who: "vous", what: "DSL mis à jour : fenêtre de maintenance ajoutée sur Line1" },
];

export const Route = createFileRoute("/_authenticated/audit")({
  head: () => ({ meta: [{ title: "Audit — PRISME" }] }),
  component: () => (
    <>
      <PageHeader
        title="Audit"
        desc="Chaque prompt, modification DSL, génération, validation, exécution et approbation humaine — enregistrés, inviolables, exportables."
      />
      <div className="glass overflow-hidden rounded-2xl">
        <div className="flex items-center gap-2 border-b border-border/50 px-5 py-3 text-sm font-semibold">
          <ClipboardList className="h-4 w-4 text-primary" /> Événements d'audit récents
        </div>
        <ul>
          {EVENTS.map((e, i) => (
            <li
              key={i}
              className="flex items-start justify-between border-b border-border/30 px-5 py-4 text-sm last:border-0"
            >
              <div>
                <div className="text-xs uppercase tracking-widest text-muted-foreground">
                  {e.who}
                </div>
                <div className="mt-1">{e.what}</div>
              </div>
              <div className="whitespace-nowrap pl-4 text-xs text-muted-foreground">{e.t}</div>
            </li>
          ))}
        </ul>
      </div>
    </>
  ),
});

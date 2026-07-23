import { createFileRoute } from "@tanstack/react-router";
import { ShieldCheck, Check, AlertTriangle, X } from "lucide-react";
import { PageHeader } from "@/components/app-page";

const CHECKS = [
  { name: "Vérifications de type statiques", status: "pass", icon: Check },
  { name: "Atteignabilité des contraintes", status: "pass", icon: Check },
  { name: "Tests de propriétés (500 graines)", status: "warn", icon: AlertTriangle, note: "3 graines instables" },
  { name: "Limites d'utilisation des ressources", status: "pass", icon: Check },
  { name: "Sortie déterministe", status: "fail", icon: X, note: "Départage non déterministe sur Line1" },
  { name: "Signature et provenance", status: "pass", icon: Check },
];

export const Route = createFileRoute("/_authenticated/validation")({
  head: () => ({ meta: [{ title: "Validation — PRISME" }] }),
  component: () => (
    <>
      <PageHeader
        title="Validation"
        desc="Chaque solveur généré passe par des vérifications statiques, sémantiques et basées sur des propriétés avant de pouvoir être promu."
      />
      <div className="glass rounded-2xl p-6">
        <div className="flex items-center gap-3">
          <ShieldCheck className="h-5 w-5 text-primary" />
          <div className="text-sm font-semibold">assembly-line-v3</div>
          <span className="rounded-full bg-accent/20 px-2 py-0.5 text-xs text-accent">1 problème</span>
        </div>
        <div className="mt-5 space-y-2">
          {CHECKS.map((c) => (
            <div
              key={c.name}
              className="flex items-center justify-between rounded-xl border border-border/50 p-4 text-sm"
            >
              <div className="flex items-center gap-3">
                <c.icon
                  className={`h-4 w-4 ${
                    c.status === "pass"
                      ? "text-primary"
                      : c.status === "warn"
                        ? "text-accent"
                        : "text-destructive"
                  }`}
                />
                {c.name}
              </div>
              {c.note && <div className="text-xs text-muted-foreground">{c.note}</div>}
            </div>
          ))}
        </div>
      </div>
    </>
  ),
});

import { createFileRoute } from "@tanstack/react-router";
import { Bell, AlertTriangle, Info } from "lucide-react";
import { PageHeader } from "@/components/app-page";

const ALERTS = [
  { icon: AlertTriangle, level: "warn", title: "Dérive de planning sur Line1", when: "il y a 12min" },
  { icon: Info, level: "info", title: "Nouveau brouillon de solveur prêt pour révision", when: "il y a 1h" },
  { icon: Bell, level: "info", title: "Maintenance du bac à sable terminée", when: "hier" },
];

export const Route = createFileRoute("/_authenticated/alerts")({
  head: () => ({ meta: [{ title: "Alertes — PRISME" }] }),
  component: () => (
    <>
      <PageHeader
        title="Alertes"
        desc="Seuils de SLA, détection de dérive, anomalies du bac à sable. Routage vers Slack, e-mail ou webhook."
      />
      <div className="glass overflow-hidden rounded-2xl">
        {ALERTS.map((a, i) => (
          <div
            key={i}
            className="flex items-center justify-between border-b border-border/30 px-5 py-4 text-sm last:border-0"
          >
            <div className="flex items-center gap-3">
              <a.icon
                className={`h-4 w-4 ${
                  a.level === "warn" ? "text-accent" : "text-primary"
                }`}
              />
              {a.title}
            </div>
            <div className="text-xs text-muted-foreground">{a.when}</div>
          </div>
        ))}
      </div>
    </>
  ),
});

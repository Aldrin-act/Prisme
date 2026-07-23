import { createFileRoute } from "@tanstack/react-router";
import { KeyRound, Plus, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/app-page";

const KEYS = [
  { name: "prod-write", prefix: "pk_live_a1b2…", created: "il y a 2 semaines", used: "il y a 12min" },
  { name: "ci-readonly", prefix: "pk_live_9f0e…", created: "il y a 1 mois", used: "il y a 1h" },
];

export const Route = createFileRoute("/_authenticated/api-keys")({
  head: () => ({ meta: [{ title: "Clés API — PRISME" }] }),
  component: () => (
    <>
      <PageHeader
        title="Clés API"
        desc="Clés révocables et limitées en portée pour un accès programmatique à vos instances, solveurs et plannings."
        action={
          <Button className="bg-gradient-to-r from-primary to-accent">
            <Plus className="mr-2 h-4 w-4" /> Nouvelle clé
          </Button>
        }
      />
      <div className="glass overflow-hidden rounded-2xl">
        <table className="w-full text-sm">
          <thead className="border-b border-border/50 text-left text-xs uppercase tracking-widest text-muted-foreground">
            <tr>
              <th className="px-5 py-3">Nom</th>
              <th className="px-5 py-3">Clé</th>
              <th className="px-5 py-3">Créée</th>
              <th className="px-5 py-3">Dernière utilisation</th>
              <th className="px-5 py-3" />
            </tr>
          </thead>
          <tbody>
            {KEYS.map((k) => (
              <tr key={k.name} className="border-b border-border/30 last:border-0">
                <td className="px-5 py-4">
                  <div className="flex items-center gap-2">
                    <KeyRound className="h-4 w-4 text-primary" /> {k.name}
                  </div>
                </td>
                <td className="px-5 py-4 font-mono text-xs text-muted-foreground">{k.prefix}</td>
                <td className="px-5 py-4 text-muted-foreground">{k.created}</td>
                <td className="px-5 py-4 text-muted-foreground">{k.used}</td>
                <td className="px-5 py-4 text-right">
                  <Button variant="ghost" size="sm">
                    <Copy className="mr-2 h-4 w-4" /> Copier
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

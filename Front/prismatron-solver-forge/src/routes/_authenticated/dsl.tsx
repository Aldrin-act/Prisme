import { createFileRoute } from "@tanstack/react-router";
import { Code2, Play } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/app-page";

const SAMPLE = `resource Line1 { capacity: 1 }
resource Line2 { capacity: 1 }

job PaintCarBody(duration: 45min) uses Line1 or Line2
job AssembleDoor(duration: 20min) uses Line1

constraint no_overlap(Line1)
constraint no_overlap(Line2)
constraint precedence(PaintCarBody, AssembleDoor)

objective minimize makespan
`;

export const Route = createFileRoute("/_authenticated/dsl")({
  head: () => ({ meta: [{ title: "Concepteur DSL — PRISME" }] }),
  component: () => (
    <>
      <PageHeader
        title="Concepteur DSL"
        desc="Écrivez vos contraintes de planification dans le DSL PRISME. Le générateur IA les traduira en solveur CP-SAT."
        action={
          <Button className="bg-gradient-to-r from-primary to-accent">
            <Play className="mr-2 h-4 w-4" /> Générer le solveur
          </Button>
        }
      />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="glass overflow-hidden rounded-2xl lg:col-span-2">
          <div className="flex items-center justify-between border-b border-border/50 px-4 py-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Code2 className="h-4 w-4 text-primary" /> scheduling.prisme
            </div>
            <div className="text-xs text-muted-foreground">aperçu en lecture seule</div>
          </div>
          <pre className="max-h-[520px] overflow-auto p-5 text-xs leading-relaxed text-foreground/90">
            <code>{SAMPLE}</code>
          </pre>
        </div>
        <div className="glass rounded-2xl p-6">
          <h3 className="font-semibold">Assistant</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Demandez à l'assistant d'ajouter des contraintes, de refactoriser le DSL, ou d'expliquer une instruction.
          </p>
          <div className="mt-4 space-y-2 text-sm">
            <div className="rounded-lg border border-border/50 p-3 text-muted-foreground">
              « Ajoute une fenêtre de maintenance sur Line1 chaque dimanche de 8h à 16h. »
            </div>
            <div className="rounded-lg border border-border/50 p-3 text-muted-foreground">
              « Change l'objectif pour minimiser le retard. »
            </div>
          </div>
        </div>
      </div>
    </>
  ),
});

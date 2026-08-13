import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowUpRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export const Route = createFileRoute("/_authenticated/app")({
  head: () => ({
    meta: [
      { title: "Tableau de bord — PRISME" },
      { name: "description", content: "Votre espace de travail PRISME." },
    ],
  }),
  component: AppDashboard,
});

function AppDashboard() {
  const { utilisateur } = Route.useRouteContext();
  return (
    <div className="space-y-6">
      <div className="glass rounded-2xl p-6" style={{ backgroundImage: "var(--gradient-hero)" }}>
        <div className="text-xs uppercase tracking-widest text-muted-foreground">
          Bon retour, {utilisateur.prenom}
        </div>
        <h2 className="mt-2 text-2xl font-bold">
          Prêt à construire avec <span className="gradient-text">PRISME</span>
        </h2>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Ingérez vos données brutes, laissez l'agent de compréhension proposer une instance en
          T-R-C-O, et laissez l'IA rédiger votre premier solveur prêt pour la production.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button asChild className="bg-gradient-to-r from-primary to-accent">
            <Link to="/donnees">
              Ingérer des données <ArrowUpRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/solver-generator">Générer un solveur</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[
          { label: "Instances actives", value: "0" },
          { label: "Solveurs générés", value: "0" },
          { label: "Exécutions en bac à sable", value: "0" },
          { label: "Événements d'audit", value: "0" },
        ].map((s) => (
          <div key={s.label} className="glass rounded-2xl p-5">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">
              {s.label}
            </div>
            <div className="mt-2 text-3xl font-bold">{s.value}</div>
          </div>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="glass rounded-2xl p-6 lg:col-span-2">
          <h3 className="font-semibold">Activité récente</h3>
          <p className="mt-2 text-sm text-muted-foreground">
            Aucune activité pour l'instant. Une fois votre premier solveur généré, son cycle de vie
            apparaîtra ici avec une piste d'audit complète.
          </p>
        </div>
        <div className="glass rounded-2xl p-6">
          <h3 className="font-semibold">Pour commencer</h3>
          <ol className="mt-3 space-y-2 text-sm text-muted-foreground">
            <li>1. Créer une instance</li>
            <li>2. Définir les contraintes en DSL</li>
            <li>3. Générer un solveur</li>
            <li>4. Valider et tester en bac à sable</li>
            <li>5. Planifier et surveiller</li>
          </ol>
        </div>
      </div>
    </div>
  );
}

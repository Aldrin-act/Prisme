import { createFileRoute } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { MarketingLayout, PageHero } from "@/components/marketing-shell";

export const Route = createFileRoute("/architecture")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Architecture — PRISME" },
      {
        name: "description",
        content:
          "L'architecture de PRISME : ERP → DSL → Générateur IA → Validation → Dépôt de code → Bac à sable → Planification → Tableau de bord. Isolée, observable, auditable.",
      },
      { property: "og:title", content: "Architecture — PRISME" },
      {
        property: "og:description",
        content: "L'architecture en huit étapes derrière le pipeline IA industriel de PRISME.",
      },
    ],
  }),
  component: ArchitecturePage,
});

const NODES = [
  { name: "ERP", desc: "Ingestion des commandes, nomenclatures, ressources." },
  { name: "DSL", desc: "Contraintes spécifiques au domaine." },
  { name: "Générateur IA", desc: "Rédaction de solveurs multi-agents." },
  { name: "Validation", desc: "Vérifications de type, sémantiques et de sécurité." },
  { name: "Dépôt de code", desc: "Artefacts versionnés et signés." },
  { name: "Bac à sable", desc: "Exécution isolée." },
  { name: "Planification", desc: "Plans optimisés et Gantt." },
  { name: "Tableau de bord", desc: "Opérations, KPI, piste d'audit." },
];

function ArchitecturePage() {
  return (
    <MarketingLayout>
      <PageHero
        eyebrow="Architecture"
        title={
          <>
            Huit étapes, <span className="gradient-text">un seul contrat</span>
          </>
        }
        desc="Chaque étape de PRISME a un contrat d'entrée/sortie strict, ce qui rend le pipeline testable de bout en bout et permet d'échanger, d'auditer ou de reproduire n'importe quelle étape."
      />

      <section className="mx-auto max-w-7xl px-4 py-16">
        <div className="glass rounded-3xl p-6 md:p-10">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
            {NODES.map((n, i) => (
              <div key={n.name} className="relative">
                <div className="glass h-full rounded-2xl p-5">
                  <div className="text-xs text-muted-foreground">Nœud {String(i + 1).padStart(2, "0")}</div>
                  <div className="mt-1 text-lg font-semibold">{n.name}</div>
                  <p className="mt-2 text-sm text-muted-foreground">{n.desc}</p>
                </div>
                {i < NODES.length - 1 && (
                  <ArrowRight className="absolute -bottom-6 left-1/2 h-5 w-5 -translate-x-1/2 text-primary lg:-right-4 lg:bottom-1/2 lg:left-auto lg:translate-x-0 lg:translate-y-1/2" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-16">
        <div className="grid gap-4 md:grid-cols-3">
          {[
            {
              t: "Isolation",
              d: "Chaque étape s'exécute dans sa propre frontière de service — une panne ne se propage jamais.",
            },
            {
              t: "Observabilité",
              d: "Traces OpenTelemetry, journaux structurés et métriques pour chaque transition.",
            },
            {
              t: "Reproductibilité",
              d: "Tout planning passé peut être rejoué à l'identique à partir de la piste d'audit.",
            },
          ].map((p) => (
            <div key={p.t} className="glass rounded-2xl p-6">
              <div className="text-primary text-xs uppercase tracking-widest">Principe</div>
              <div className="mt-1 text-lg font-semibold">{p.t}</div>
              <p className="mt-2 text-sm text-muted-foreground">{p.d}</p>
            </div>
          ))}
        </div>
      </section>
    </MarketingLayout>
  );
}

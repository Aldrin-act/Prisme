import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Boxes,
  Cpu,
  ShieldCheck,
  Workflow,
  LineChart,
  Sparkles,
  Database,
  GitBranch,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarketingLayout, PageHero } from "@/components/marketing-shell";

export const Route = createFileRoute("/platform")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Plateforme — PRISME" },
      {
        name: "description",
        content:
          "La plateforme PRISME découple la génération de solveurs par IA, la validation, l'exécution, la planification et l'audit en étapes isolées et observables.",
      },
      { property: "og:title", content: "La plateforme PRISME" },
      {
        property: "og:description",
        content:
          "Séparation des responsabilités pour des pipelines d'optimisation de qualité industrielle.",
      },
    ],
  }),
  component: PlatformPage,
});

const STAGES = [
  {
    icon: Database,
    title: "Ingestion",
    desc: "Récupérez commandes, nomenclatures, ressources et calendriers depuis vos ERP, MES, tableurs ou API.",
  },
  {
    icon: GitBranch,
    title: "DSL",
    desc: "Exprimez les contraintes de planification dans un langage spécifique au domaine que votre équipe peut lire.",
  },
  {
    icon: Cpu,
    title: "Génération IA",
    desc: "Un pipeline multi-agents transforme le DSL en solveurs heuristiques avec des explications complètes.",
  },
  {
    icon: ShieldCheck,
    title: "Validation",
    desc: "Vérifications de type automatiques, tests sémantiques et revues de sécurité avant l'enregistrement du code.",
  },
  {
    icon: Boxes,
    title: "Dépôt de code",
    desc: "Solveurs versionnés et signés, avec rollback et portes d'approbation humaine.",
  },
  {
    icon: Workflow,
    title: "Bac à sable",
    desc: "Conteneurs isolés avec limites de ressources strictes et aucun accès réseau sortant.",
  },
  {
    icon: LineChart,
    title: "Planification",
    desc: "Plannings optimisés livrés à l'atelier avec vues Gantt et tableaux de bord KPI.",
  },
  {
    icon: Sparkles,
    title: "Audit",
    desc: "Chaque décision traçable — prompts, DSL, solveur, exécution, résultat, dérogation humaine.",
  },
];

function PlatformPage() {
  return (
    <MarketingLayout>
      <PageHero
        eyebrow="Plateforme"
        title={
          <>
            Une plateforme, <span className="gradient-text">huit étapes</span>, zéro boîte noire
          </>
        }
        desc="PRISME découpe le pipeline de l'IA jusqu'au planning en étapes isolées et observables, pour que chaque étape soit testable, explicable et sûre."
      />

      <section className="mx-auto max-w-7xl px-4 py-20">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {STAGES.map((s, i) => (
            <div key={s.title} className="glass rounded-2xl p-6">
              <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-primary/30 to-accent/30">
                <s.icon className="h-5 w-5 text-primary" />
              </div>
              <div className="text-xs text-muted-foreground">Étape {i + 1}</div>
              <h3 className="mt-1 text-lg font-semibold">{s.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{s.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-20">
        <div className="glass rounded-3xl p-10 text-center">
          <h2 className="text-3xl font-bold md:text-4xl">
            Supervision humaine par <span className="gradient-text">conception</span>
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-muted-foreground">
            Aucun solveur n'atteint la production sans une approbation humaine explicite. PRISME
            expose le raisonnement de l'IA, le diff, et les résultats des tests en bac à sable —
            vous décidez.
          </p>
          <Button asChild size="lg" className="mt-8 bg-gradient-to-r from-primary to-accent glow">
            <Link to="/architecture">
              Voir l'architecture <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
        </div>
      </section>
    </MarketingLayout>
  );
}

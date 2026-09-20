import { createFileRoute } from "@tanstack/react-router";
import {
  Cpu,
  ShieldCheck,
  Workflow,
  LineChart,
  Sparkles,
  Boxes,
  GitBranch,
  KeyRound,
  Bell,
  FileCode2,
  Users,
  Gauge,
} from "lucide-react";
import { MarketingLayout, PageHero } from "@/components/marketing-shell";

export const Route = createFileRoute("/features")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Fonctionnalités — PRISME" },
      {
        name: "description",
        content:
          "Génération de solveurs par IA, planification industrielle, moteur de validation, bac à sable sécurisé, auditabilité et pipeline multi-agents — toutes les fonctionnalités de PRISME.",
      },
      { property: "og:title", content: "Fonctionnalités — PRISME" },
      {
        property: "og:description",
        content: "Toutes les capacités offertes par PRISME pour l'optimisation industrielle.",
      },
    ],
  }),
  component: FeaturesPage,
});

const FEATURES = [
  {
    icon: Cpu,
    title: "Génération de solveurs par IA",
    desc: "Transformez des contraintes métier en solveurs heuristiques, revus et expliqués par des agents IA.",
  },
  {
    icon: LineChart,
    title: "Planification industrielle",
    desc: "Plans de production optimisés, fenêtres de maintenance et allocation des ressources — avec sortie Gantt.",
  },
  {
    icon: ShieldCheck,
    title: "Moteur de validation",
    desc: "Analyse statique, tests symboliques et vérifications de propriétés détectent les mauvais solveurs avant leur exécution.",
  },
  {
    icon: Workflow,
    title: "Bac à sable sécurisé",
    desc: "Conteneurs éphémères, aucun accès réseau sortant, limites CPU/RAM par cgroup, artefacts signés.",
  },
  {
    icon: Sparkles,
    title: "Auditabilité complète",
    desc: "Chaque prompt, DSL, solveur, exécution et décision humaine enregistrés — prêts à l'export pour les régulateurs.",
  },
  {
    icon: Boxes,
    title: "Pipeline multi-agents",
    desc: "Des agents spécialisés pour l'analyse, la génération, la validation et l'explication — visualisez chaque étape.",
  },
  {
    icon: GitBranch,
    title: "DSL et versioning",
    desc: "Langage spécifique au domaine avec versioning façon Git, diff et rollback de chaque solveur.",
  },
  {
    icon: Gauge,
    title: "Benchmarks de performance",
    desc: "Comparez les solveurs entre eux sur différents scénarios ; choisissez le meilleur en conditions réelles.",
  },
  {
    icon: KeyRound,
    title: "SSO et clés API",
    desc: "OIDC / SAML, clés API granulaires, accès basé sur les rôles, jetons limités par environnement.",
  },
  {
    icon: Bell,
    title: "Alertes et surveillance",
    desc: "Seuils de SLA, détection de dérive et notifications Slack/e-mail lorsque les plannings se dégradent.",
  },
  {
    icon: FileCode2,
    title: "Export et sur site",
    desc: "Gardez la maîtrise de votre code. Exportez les solveurs en Python propre. Déployez PRISME sur votre infrastructure.",
  },
  {
    icon: Users,
    title: "Supervision humaine",
    desc: "Portes d'approbation, historiques de dérogations et comparaisons côte à côte pour chaque décision.",
  },
];

function FeaturesPage() {
  return (
    <MarketingLayout>
      <PageHero
        eyebrow="Fonctionnalités"
        title={
          <>
            Tout ce qu'il faut pour <span className="gradient-text">industrialiser l'IA</span>
          </>
        }
        desc="Douze capacités conçues pour les ateliers de production réels — du DSL au Gantt, du prompt à l'audit."
      />

      <section className="mx-auto max-w-7xl px-4 py-20">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="glass rounded-2xl p-6 transition hover:-translate-y-0.5">
              <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary/30 to-accent/30">
                <f.icon className="h-5 w-5 text-primary" />
              </div>
              <h3 className="text-lg font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>
    </MarketingLayout>
  );
}

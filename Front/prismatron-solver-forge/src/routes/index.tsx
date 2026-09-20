import { createFileRoute, Link } from "@tanstack/react-router";
import {
  Sparkles,
  ShieldCheck,
  Cpu,
  Boxes,
  Workflow,
  LineChart,
  ArrowRight,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarketingNav, MarketingFooter } from "@/components/marketing-shell";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "PRISME — Générez des solveurs de planification industrielle avec l'IA" },
      {
        name: "description",
        content:
          "PRISME est une plateforme propulsée par l'IA qui transforme vos contraintes métier de planification en solveurs d'ordonnancement heuristiques prêts pour la production — validés, isolés en bac à sable, auditables et supervisés par un humain.",
      },
      {
        property: "og:title",
        content: "PRISME — Générez des solveurs de planification industrielle avec l'IA",
      },
      {
        property: "og:description",
        content:
          "PRISME est une plateforme propulsée par l'IA qui transforme vos contraintes métier de planification en solveurs d'ordonnancement heuristiques prêts pour la production — validés, isolés en bac à sable, auditables et supervisés par un humain.",
      },
    ],
  }),
  component: Landing,
});

function Landing() {
  return (
    <div className="min-h-screen">
      <MarketingNav />
      <Hero />
      <TrustedBy />
      <Platform />
      <Features />
      <Architecture />
      <Pricing />
      <FAQ />
      <CTA />
      <MarketingFooter />
    </div>
  );
}

function Hero() {
  return (
    <section
      className="relative overflow-hidden pt-40 pb-24"
      style={{ backgroundImage: "var(--gradient-hero)" }}
    >
      <GridBackdrop />
      <div className="relative mx-auto max-w-7xl px-4 text-center">
        <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
          <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
          IA multi-agents pour l'optimisation des processus métiers
        </div>
        <h1 className="mt-6 text-5xl font-bold tracking-tight sm:text-6xl md:text-7xl">
          Générez des solveurs de planification
          <br />
          <span className="gradient-text">industrielle avec l'IA</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg text-muted-foreground">
          PRISME transforme vos contraintes métier de planification en solveurs heuristiques prêts
          pour la production — validés, isolés en bac à sable, auditables et supervisés par un
          humain.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button
            asChild
            size="lg"
            className="bg-gradient-to-r from-primary to-accent glow hover:opacity-90"
          >
            <Link to="/contact">
              Demander une démo
              <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link to="/platform">Découvrir la plateforme</Link>
          </Button>
        </div>
        <FloatingCards />
      </div>
    </section>
  );
}

function GridBackdrop() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 opacity-30"
      style={{
        backgroundImage:
          "linear-gradient(oklch(1 0 0 / 0.06) 1px, transparent 1px), linear-gradient(90deg, oklch(1 0 0 / 0.06) 1px, transparent 1px)",
        backgroundSize: "56px 56px",
        maskImage: "radial-gradient(ellipse 70% 60% at 50% 20%, black, transparent 80%)",
      }}
    />
  );
}

function FloatingCards() {
  const cards = [
    { icon: Cpu, label: "Générateur IA", value: "Agents IA + heuristiques" },
    { icon: ShieldCheck, label: "Validation", value: "100% couvert" },
    { icon: Workflow, label: "Bac à sable", value: "Exécutions isolées" },
    { icon: LineChart, label: "Plannings", value: "Optimisés" },
  ];
  return (
    <div className="mt-16 grid grid-cols-2 gap-3 md:grid-cols-4">
      {cards.map((c) => (
        <div key={c.label} className="glass flex items-center gap-3 rounded-2xl p-4 text-left">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-primary/30 to-accent/30">
            <c.icon className="h-5 w-5 text-primary" />
          </div>
          <div>
            <div className="text-xs text-muted-foreground">{c.label}</div>
            <div className="text-sm font-semibold">{c.value}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function TrustedBy() {
  const items = [
    "Industrie manufacturière",
    "Automobile",
    "Électronique",
    "Logistique",
    "Laboratoires de recherche",
    "Aéronautique",
  ];
  return (
    <section className="border-y border-border/50 py-10">
      <div className="mx-auto max-w-7xl px-4">
        <p className="text-center text-xs uppercase tracking-widest text-muted-foreground">
          Ils nous font confiance dans les secteurs industriels
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-4 opacity-70">
          {items.map((i) => (
            <span key={i} className="text-sm font-semibold tracking-wide">
              {i}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function SectionHead({ eyebrow, title, desc }: { eyebrow: string; title: string; desc: string }) {
  return (
    <div className="mx-auto max-w-3xl text-center">
      <div className="text-xs uppercase tracking-widest text-primary">{eyebrow}</div>
      <h2 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl md:text-5xl">{title}</h2>
      <p className="mt-4 text-muted-foreground">{desc}</p>
    </div>
  );
}

function Platform() {
  const steps = [
    { icon: Boxes, title: "Ingestion", desc: "Données ERP et contraintes métier en DSL." },
    {
      icon: Cpu,
      title: "Génération IA",
      desc: "Génération multi-agents de solveurs heuristiques.",
    },
    {
      icon: ShieldCheck,
      title: "Validation",
      desc: "Vérifications automatiques et explicabilité.",
    },
    { icon: Workflow, title: "Bac à sable", desc: "Exécution de code isolée et sécurisée." },
    { icon: LineChart, title: "Planification", desc: "Plans de production optimisés." },
    { icon: Sparkles, title: "Audit", desc: "Chaque décision est traçable." },
  ];
  return (
    <section id="platform" className="mx-auto max-w-7xl px-4 py-28">
      <SectionHead
        eyebrow="Plateforme"
        title="Une séparation des responsabilités pensée pour l'industrie"
        desc="PRISME découple la génération IA, la validation des solveurs, l'exécution sécurisée, la planification, la surveillance et l'audit — pour que chaque étape reste testable, explicable et sûre."
      />
      <div className="mt-14 grid gap-4 md:grid-cols-3">
        {steps.map((s, i) => (
          <div key={s.title} className="glass group relative rounded-2xl p-6">
            <div className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-primary/30 to-accent/30">
              <s.icon className="h-5 w-5 text-primary" />
            </div>
            <div className="text-xs text-muted-foreground">Étape {i + 1}</div>
            <h3 className="mt-1 text-lg font-semibold">{s.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{s.desc}</p>
          </div>
        ))}
      </div>
      <div className="mt-10 text-center">
        <Button asChild variant="outline">
          <Link to="/platform">
            Voir toute la plateforme <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </div>
    </section>
  );
}

function Features() {
  const items = [
    {
      icon: Cpu,
      title: "Génération de solveurs par IA",
      desc: "Transformez des contraintes métier en langage naturel en solveurs heuristiques d'ordonnancement.",
    },
    {
      icon: LineChart,
      title: "Planification industrielle",
      desc: "Plans de production optimisés, fenêtres de maintenance, allocation des ressources.",
    },
    {
      icon: ShieldCheck,
      title: "Moteur de validation",
      desc: "Validation automatique des solveurs générés avant leur mise en production.",
    },
    {
      icon: Workflow,
      title: "Bac à sable sécurisé",
      desc: "Chaque solveur s'exécute dans des conteneurs isolés — rien ne fuite.",
    },
    {
      icon: Sparkles,
      title: "Auditabilité complète",
      desc: "Décisions traçables et explicables, du prompt jusqu'au planning.",
    },
    {
      icon: Boxes,
      title: "Pipeline multi-agents",
      desc: "Visualisez le rôle de chaque agent dans le flux de génération.",
    },
  ];
  return (
    <section id="features" className="mx-auto max-w-7xl px-4 py-28">
      <SectionHead
        eyebrow="Fonctionnalités"
        title="Conçu pour les ateliers de production réels"
        desc="Du DSL au Gantt — la boucle complète, conçue pour la fiabilité en entreprise."
      />
      <div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {items.map((f) => (
          <div key={f.title} className="glass rounded-2xl p-6 transition hover:-translate-y-0.5">
            <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary/30 to-accent/30">
              <f.icon className="h-5 w-5 text-primary" />
            </div>
            <h3 className="text-lg font-semibold">{f.title}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{f.desc}</p>
          </div>
        ))}
      </div>
      <div className="mt-10 text-center">
        <Button asChild variant="outline">
          <Link to="/features">
            Toutes les fonctionnalités <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </div>
    </section>
  );
}

function Architecture() {
  const nodes = [
    "ERP",
    "DSL",
    "Générateur IA",
    "Validation",
    "Dépôt de code",
    "Bac à sable",
    "Planification",
    "Tableau de bord",
  ];
  return (
    <section id="architecture" className="mx-auto max-w-7xl px-4 py-28">
      <SectionHead
        eyebrow="Architecture"
        title="Chaque étape, isolée et observable"
        desc="De l'ingestion ERP au tableau de bord de l'opérateur, le pipeline de PRISME est transparent — et chaque solveur est traçable."
      />
      <div className="glass mt-14 rounded-3xl p-6 md:p-10">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {nodes.map((n, i) => (
            <div key={n} className="flex flex-col items-center">
              <div className="flex h-16 w-full items-center justify-center rounded-xl border border-border bg-background/40 text-sm font-medium">
                {n}
              </div>
              {i < nodes.length - 1 && (
                <ArrowRight className="my-2 h-4 w-4 rotate-90 text-primary lg:rotate-0" />
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Pricing() {
  const plans = [
    {
      name: "Communautaire",
      price: "Gratuit",
      features: ["1 instance", "Exécutions manuelles des solveurs", "Support communautaire"],
      highlight: false,
    },
    {
      name: "Professionnel",
      price: "1 490 €/mois",
      features: [
        "Instances illimitées",
        "Quotas de génération IA",
        "Exécution en bac à sable",
        "Journaux d'audit",
      ],
      highlight: true,
    },
    {
      name: "Entreprise",
      price: "Sur mesure",
      features: ["SSO / SAML", "Déploiement sur site", "SRE dédié", "SLA personnalisés"],
      highlight: false,
    },
  ];
  return (
    <section id="pricing" className="mx-auto max-w-7xl px-4 py-28">
      <SectionHead
        eyebrow="Tarifs"
        title="Simple, de qualité industrielle"
        desc="Commencez avec l'édition communautaire. Passez au sur site quand vous en avez besoin."
      />
      <div className="mt-14 grid gap-6 md:grid-cols-3">
        {plans.map((p) => (
          <div
            key={p.name}
            className={`relative rounded-3xl p-8 ${p.highlight ? "glass border-primary/40 glow" : "glass"}`}
          >
            {p.highlight && (
              <div className="absolute -top-3 left-8 rounded-full bg-gradient-to-r from-primary to-accent px-3 py-1 text-xs font-semibold">
                Le plus populaire
              </div>
            )}
            <div className="text-sm text-muted-foreground">{p.name}</div>
            <div className="mt-2 text-3xl font-bold">{p.price}</div>
            <ul className="mt-6 space-y-2 text-sm">
              {p.features.map((f) => (
                <li key={f} className="flex items-start gap-2">
                  <Check className="mt-0.5 h-4 w-4 text-primary" /> {f}
                </li>
              ))}
            </ul>
            <Button
              asChild
              className={`mt-8 w-full ${p.highlight ? "bg-gradient-to-r from-primary to-accent" : ""}`}
              variant={p.highlight ? "default" : "outline"}
            >
              <Link to="/pricing">En savoir plus</Link>
            </Button>
          </div>
        ))}
      </div>
    </section>
  );
}

function FAQ() {
  const faqs = [
    {
      q: "Comment l'IA génère-t-elle les solveurs ?",
      a: "Un pipeline multi-agents transforme vos contraintes DSL en code de solveur heuristique (Python pur), puis le valide et l'exécute en bac à sable avant sa mise en service.",
    },
    {
      q: "Quels algorithmes d'optimisation sont utilisés ?",
      a: "Des heuristiques d'ordonnancement (tabou, recuit simulé, génétique, colonies de fourmis, règles de dispatching) — choisies et générées pour chaque instance.",
    },
    {
      q: "L'exécution est-elle sécurisée ?",
      a: "Chaque solveur généré s'exécute dans un conteneur isolé sans accès réseau sortant, avec des limites de ressources strictes et des journaux d'audit complets.",
    },
    {
      q: "Puis-je déployer sur site ?",
      a: "Oui. Les clients Entreprise peuvent déployer PRISME sur leur propre infrastructure avec SSO et leurs propres modèles.",
    },
    {
      q: "Puis-je exporter le code généré ?",
      a: "Absolument — chaque solveur est du Python entièrement lisible et exportable à tout moment.",
    },
  ];
  return (
    <section className="mx-auto max-w-3xl px-4 py-28">
      <SectionHead
        eyebrow="FAQ"
        title="Les réponses, tout de suite"
        desc="Tout ce qu'il vous faut pour évaluer PRISME."
      />
      <div className="mt-10 space-y-3">
        {faqs.map((f) => (
          <details key={f.q} className="glass group rounded-2xl p-5">
            <summary className="flex cursor-pointer items-center justify-between text-left font-semibold">
              {f.q}
              <span className="text-primary transition group-open:rotate-45">+</span>
            </summary>
            <p className="mt-3 text-sm text-muted-foreground">{f.a}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className="mx-auto max-w-7xl px-4 py-20">
      <div
        className="glass relative overflow-hidden rounded-3xl p-10 text-center md:p-16"
        style={{ backgroundImage: "var(--gradient-hero)" }}
      >
        <h2 className="text-3xl font-bold tracking-tight md:text-5xl">
          Prêt à industrialiser votre <span className="gradient-text">optimisation ?</span>
        </h2>
        <p className="mx-auto mt-4 max-w-xl text-muted-foreground">
          Demandez une démo et voyez PRISME générer un solveur à partir de vos propres contraintes.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Button asChild size="lg" className="bg-gradient-to-r from-primary to-accent glow">
            <Link to="/contact">
              Demander une démo <ArrowRight className="ml-2 h-4 w-4" />
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link to="/platform">En savoir plus</Link>
          </Button>
        </div>
      </div>
    </section>
  );
}

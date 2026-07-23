import { createFileRoute, Link } from "@tanstack/react-router";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarketingLayout, PageHero } from "@/components/marketing-shell";

export const Route = createFileRoute("/pricing")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Tarifs — PRISME" },
      {
        name: "description",
        content:
          "Offres Communautaire, Professionnel et Entreprise pour la plateforme de planification industrielle propulsée par l'IA de PRISME.",
      },
      { property: "og:title", content: "Tarifs — PRISME" },
      {
        property: "og:description",
        content: "Une tarification simple et de qualité industrielle pour des équipes de toute taille.",
      },
    ],
  }),
  component: PricingPage,
});

const PLANS = [
  {
    name: "Communautaire",
    price: "Gratuit",
    desc: "Pour la recherche et l'évaluation.",
    features: ["1 instance", "Exécutions manuelles des solveurs", "Support communautaire", "Journal d'audit basique"],
    cta: "Commencer gratuitement",
    to: "/auth" as const,
    highlight: false,
  },
  {
    name: "Professionnel",
    price: "1 490 €",
    per: "/ mois",
    desc: "Pour les équipes d'ingénierie.",
    features: [
      "Instances illimitées",
      "Quotas de génération IA",
      "Exécution en bac à sable",
      "Piste d'audit complète",
      "Support prioritaire",
      "SSO (Google, Microsoft)",
    ],
    cta: "Demander l'accès",
    to: "/contact" as const,
    highlight: true,
  },
  {
    name: "Entreprise",
    price: "Sur mesure",
    desc: "Sur site, SSO, SRE dédié.",
    features: [
      "SSO SAML / OIDC",
      "Déploiement sur site",
      "SRE dédié",
      "SLA personnalisés",
      "Vos propres modèles",
      "Packs d'export réglementaires",
    ],
    cta: "Contacter les ventes",
    to: "/contact" as const,
    highlight: false,
  },
];

function PricingPage() {
  return (
    <MarketingLayout>
      <PageHero
        eyebrow="Tarifs"
        title={
          <>
            Simple, <span className="gradient-text">qualité industrielle</span>
          </>
        }
        desc="Commencez gratuitement, passez au sur site quand vous en avez besoin. Aucun frais caché sur la génération."
      />

      <section className="mx-auto max-w-7xl px-4 py-16">
        <div className="grid gap-6 md:grid-cols-3">
          {PLANS.map((p) => (
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
              <div className="mt-2 flex items-baseline gap-1">
                <span className="text-3xl font-bold">{p.price}</span>
                {p.per && <span className="text-sm text-muted-foreground">{p.per}</span>}
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{p.desc}</p>
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
                <Link to={p.to}>{p.cta}</Link>
              </Button>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-4 py-16 text-center">
        <h2 className="text-2xl font-bold">Besoin de quelque chose de spécifique ?</h2>
        <p className="mt-2 text-muted-foreground">
          Déploiements air-gapped, SLA personnalisés, vos propres modèles — nous adaptons PRISME
          à votre cadre de conformité.
        </p>
        <Button asChild size="lg" className="mt-6 bg-gradient-to-r from-primary to-accent">
          <Link to="/contact">Parler aux ventes</Link>
        </Button>
      </section>
    </MarketingLayout>
  );
}

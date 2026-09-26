import { createFileRoute } from "@tanstack/react-router";
import { BookOpen, Code2, Cpu, ShieldCheck, Workflow, KeyRound } from "lucide-react";
import { MarketingLayout, PageHero } from "@/components/marketing-shell";

export const Route = createFileRoute("/docs")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Documentation — PRISME" },
      {
        name: "description",
        content:
          "Guides, référence DSL, fonctionnement interne de la génération de solveurs, modèle de sécurité du bac à sable et référence API pour PRISME.",
      },
      { property: "og:title", content: "Documentation PRISME" },
      {
        property: "og:description",
        content:
          "Tout ce dont développeurs et opérateurs ont besoin pour exploiter PRISME en production.",
      },
    ],
  }),
  component: DocsPage,
});

const SECTIONS = [
  {
    icon: BookOpen,
    title: "Démarrage",
    items: [
      "Démarrage rapide",
      "Créer votre première instance",
      "Connecter votre ERP",
      "Approuver votre premier solveur",
    ],
  },
  {
    icon: Code2,
    title: "Référence DSL",
    items: ["Ressources et calendriers", "Contraintes", "Objectifs", "Extensibilité et macros"],
  },
  {
    icon: Cpu,
    title: "Génération de solveurs",
    items: [
      "Le pipeline d'agents",
      "Prompts et garde-fous",
      "Diff et explication",
      "Sélection du modèle",
    ],
  },
  {
    icon: ShieldCheck,
    title: "Validation",
    items: [
      "Vérifications statiques",
      "Tests sémantiques",
      "Tests de propriétés",
      "Approbation humaine",
    ],
  },
  {
    icon: Workflow,
    title: "Bac à sable et exécution",
    items: [
      "Modèle de conteneurs",
      "Limites de ressources",
      "Garanties d'isolation",
      "Signature des artefacts",
    ],
  },
  {
    icon: KeyRound,
    title: "API et SSO",
    items: ["API REST", "Webhooks", "OIDC / SAML", "Portées des clés API"],
  },
];

function DocsPage() {
  return (
    <MarketingLayout>
      <PageHero
        eyebrow="Documentation"
        title={
          <>
            Le <span className="gradient-text">manuel de l'opérateur</span>
          </>
        }
        desc="De la syntaxe DSL aux garanties d'isolation du bac à sable — tout ce qu'il faut pour déployer PRISME dans un environnement réglementé."
      />
      <section className="mx-auto max-w-7xl px-4 py-16">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {SECTIONS.map((s) => (
            <div key={s.title} className="glass rounded-2xl p-6">
              <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary/30 to-accent/30">
                <s.icon className="h-5 w-5 text-primary" />
              </div>
              <h3 className="text-lg font-semibold">{s.title}</h3>
              <ul className="mt-3 space-y-1.5 text-sm text-muted-foreground">
                {s.items.map((i) => (
                  <li key={i} className="flex items-center gap-2 hover:text-foreground">
                    <span className="text-primary">›</span> {i}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </MarketingLayout>
  );
}

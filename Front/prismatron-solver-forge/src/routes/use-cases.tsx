import { createFileRoute } from "@tanstack/react-router";
import {
  Factory,
  Car,
  Cpu as Chip,
  Truck,
  Wrench,
  CalendarClock,
  Boxes,
  ClipboardList,
} from "lucide-react";
import { MarketingLayout, PageHero } from "@/components/marketing-shell";

export const Route = createFileRoute("/use-cases")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Cas d'usage — PRISME" },
      {
        name: "description",
        content:
          "Industrie manufacturière, automobile, électronique, logistique, planification de maintenance — PRISME dans tous les secteurs industriels.",
      },
      { property: "og:title", content: "Cas d'usage — PRISME" },
      {
        property: "og:description",
        content: "Comment les équipes industrielles déploient PRISME dans chaque secteur.",
      },
    ],
  }),
  component: UseCasesPage,
});

const CASES = [
  { icon: Factory, title: "Industrie manufacturière", desc: "Plan directeur de production, minimisation des changements de série, contrôle des en-cours." },
  { icon: Car, title: "Automobile", desc: "Assemblage final séquencé, flux de pièces en JAT, équilibrage de ligne multi-modèles." },
  { icon: Chip, title: "Électronique", desc: "Chargement de lignes SMT, allocation fours et postes de test, ordonnancement en petites séries." },
  { icon: Truck, title: "Logistique", desc: "Planification des vagues d'entrepôt, ordonnancement des quais, roulement des chauffeurs." },
  { icon: Boxes, title: "Lignes d'assemblage", desc: "Optimisation du takt-time, équilibrage des postes, réduction du temps de cycle." },
  { icon: ClipboardList, title: "Planification de production", desc: "Plans à moyen terme alignés S&OP avec contraintes de capacité et de demande." },
  { icon: Wrench, title: "Maintenance", desc: "Plannings préventifs et prédictifs avec appariement des compétences des techniciens." },
  { icon: CalendarClock, title: "Allocation des ressources", desc: "Outillage, moules, montages — la bonne ressource, au bon poste, au bon moment." },
];

function UseCasesPage() {
  return (
    <MarketingLayout>
      <PageHero
        eyebrow="Cas d'usage"
        title={
          <>
            Conçu pour <span className="gradient-text">l'atelier réel</span>
          </>
        }
        desc="De l'assemblage final automobile aux lignes SMT en électronique, PRISME génère exactement le solveur dont votre processus a besoin."
      />
      <section className="mx-auto max-w-7xl px-4 py-20">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {CASES.map((c) => (
            <div key={c.title} className="glass rounded-2xl p-6">
              <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-primary/30 to-accent/30">
                <c.icon className="h-5 w-5 text-primary" />
              </div>
              <h3 className="text-lg font-semibold">{c.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{c.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-4 py-16">
        <div className="glass rounded-3xl p-10">
          <h2 className="text-2xl font-bold md:text-3xl">Résultats rapportés par nos clients</h2>
          <div className="mt-8 grid gap-6 md:grid-cols-3">
            {[
              { v: "-38%", l: "temps de planification" },
              { v: "+12%", l: "TRS" },
              { v: "-27%", l: "changements de série" },
            ].map((k) => (
              <div key={k.l}>
                <div className="text-4xl font-bold gradient-text">{k.v}</div>
                <div className="mt-1 text-sm text-muted-foreground">{k.l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </MarketingLayout>
  );
}

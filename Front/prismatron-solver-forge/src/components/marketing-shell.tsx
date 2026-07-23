import { Link } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { Menu, X, Linkedin, Github, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PrismeLogo } from "@/components/prisme-logo";

const LINKS = [
  { to: "/platform", label: "Plateforme" },
  { to: "/features", label: "Fonctionnalités" },
  { to: "/architecture", label: "Architecture" },
  { to: "/use-cases", label: "Cas d'usage" },
  { to: "/pricing", label: "Tarifs" },
  { to: "/docs", label: "Documentation" },
  { to: "/contact", label: "Contact" },
] as const;

export function MarketingNav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="fixed top-0 z-50 w-full">
      <div className="mx-auto mt-4 max-w-7xl px-4">
        <div className="glass flex items-center justify-between rounded-2xl px-5 py-3">
          <Link to="/" className="flex items-center gap-2">
            <PrismeLogo className="h-8 w-8" />
            <span className="text-lg font-bold tracking-tight">PRISME</span>
          </Link>
          <nav className="hidden items-center gap-6 lg:flex">
            {LINKS.map((l) => (
              <Link
                key={l.to}
                to={l.to}
                className="text-sm text-muted-foreground transition hover:text-foreground"
                activeProps={{ className: "text-sm text-foreground" }}
              >
                {l.label}
              </Link>
            ))}
          </nav>
          <div className="hidden items-center gap-2 lg:flex">
            <Button asChild variant="ghost" size="sm">
              <Link to="/auth">Se connecter</Link>
            </Button>
            <Button asChild size="sm" className="bg-gradient-to-r from-primary to-accent">
              <Link to="/contact">Demander une démo</Link>
            </Button>
          </div>
          <button className="lg:hidden" onClick={() => setOpen(!open)} aria-label="Menu">
            {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
        {open && (
          <div className="glass mt-2 flex flex-col gap-1 rounded-2xl p-4 lg:hidden">
            {LINKS.map((l) => (
              <Link key={l.to} to={l.to} className="py-2 text-sm" onClick={() => setOpen(false)}>
                {l.label}
              </Link>
            ))}
            <Link to="/auth" className="py-2 text-sm font-semibold text-primary">
              Se connecter
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}

export function MarketingFooter() {
  return (
    <footer className="border-t border-border/50 py-14">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 md:grid-cols-4">
        <div>
          <div className="flex items-center gap-2">
            <PrismeLogo className="h-8 w-8" />
            <span className="font-bold">PRISME</span>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            Planification industrielle propulsée par l'IA. Supervisée par l'humain. Auditable par conception.
          </p>
        </div>
        <FooterCol
          title="Produit"
          items={[
            { label: "Plateforme", to: "/platform" },
            { label: "Fonctionnalités", to: "/features" },
            { label: "Architecture", to: "/architecture" },
            { label: "Tarifs", to: "/pricing" },
          ]}
        />
        <FooterCol
          title="Entreprise"
          items={[
            { label: "Cas d'usage", to: "/use-cases" },
            { label: "Documentation", to: "/docs" },
            { label: "Contact", to: "/contact" },
            { label: "Se connecter", to: "/auth" },
          ]}
        />
        <div>
          <div className="text-sm font-semibold">Nous contacter</div>
          <div className="mt-3 flex gap-3">
            <a href="#" className="glass rounded-lg p-2 hover:text-primary" aria-label="LinkedIn">
              <Linkedin className="h-4 w-4" />
            </a>
            <a href="#" className="glass rounded-lg p-2 hover:text-primary" aria-label="GitHub">
              <Github className="h-4 w-4" />
            </a>
            <a
              href="mailto:hello@prisme.ai"
              className="glass rounded-lg p-2 hover:text-primary"
              aria-label="Email"
            >
              <Mail className="h-4 w-4" />
            </a>
          </div>
        </div>
      </div>
      <div className="mx-auto mt-10 max-w-7xl px-4 text-xs text-muted-foreground">
        © {new Date().getFullYear()} PRISME. Tous droits réservés.
      </div>
    </footer>
  );
}

function FooterCol({
  title,
  items,
}: {
  title: string;
  items: { label: string; to: string }[];
}) {
  return (
    <div>
      <div className="text-sm font-semibold">{title}</div>
      <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
        {items.map((i) => (
          <li key={i.label}>
            <Link to={i.to} className="hover:text-foreground">
              {i.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function MarketingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen">
      <MarketingNav />
      <div className="pt-28">{children}</div>
      <MarketingFooter />
    </div>
  );
}

export function PageHero({
  eyebrow,
  title,
  desc,
}: {
  eyebrow: string;
  title: ReactNode;
  desc: string;
}) {
  return (
    <section
      className="relative overflow-hidden pb-16 pt-8"
      style={{ backgroundImage: "var(--gradient-hero)" }}
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-25"
        style={{
          backgroundImage:
            "linear-gradient(oklch(1 0 0 / 0.06) 1px, transparent 1px), linear-gradient(90deg, oklch(1 0 0 / 0.06) 1px, transparent 1px)",
          backgroundSize: "56px 56px",
          maskImage: "radial-gradient(ellipse 70% 60% at 50% 20%, black, transparent 80%)",
        }}
      />
      <div className="relative mx-auto max-w-4xl px-4 text-center">
        <div className="mx-auto inline-flex items-center gap-2 rounded-full border border-border bg-card/60 px-3 py-1 text-xs uppercase tracking-widest text-primary backdrop-blur">
          {eyebrow}
        </div>
        <h1 className="mt-5 text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">{title}</h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-muted-foreground">{desc}</p>
      </div>
    </section>
  );
}

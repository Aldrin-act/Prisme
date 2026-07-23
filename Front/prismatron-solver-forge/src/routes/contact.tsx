import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Mail, Linkedin, Github, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { MarketingLayout, PageHero } from "@/components/marketing-shell";

export const Route = createFileRoute("/contact")({
  ssr: false,
  head: () => ({
    meta: [
      { title: "Contact — PRISME" },
      {
        name: "description",
        content:
          "Demandez une démo de PRISME ou échangez avec notre équipe sur vos déploiements de planification industrielle par IA.",
      },
      { property: "og:title", content: "Contacter PRISME" },
      { property: "og:description", content: "Demandez une démo ou parlez aux ventes." },
    ],
  }),
  component: ContactPage,
});

function ContactPage() {
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", company: "", message: "" });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.name || !form.email || !form.message)
      return toast.error("Merci de renseigner tous les champs obligatoires");
    setLoading(true);
    await new Promise((r) => setTimeout(r, 700));
    setLoading(false);
    toast.success("Merci — nous vous répondrons sous un jour ouvré.");
    setForm({ name: "", email: "", company: "", message: "" });
  }

  return (
    <MarketingLayout>
      <PageHero
        eyebrow="Contact"
        title={
          <>
            Parlons de votre <span className="gradient-text">problème de planification</span>
          </>
        }
        desc="Réservez une démo, demandez un pilote, ou demandez simplement comment PRISME traiterait vos contraintes."
      />

      <section className="mx-auto max-w-6xl px-4 pb-24">
        <div className="grid gap-6 md:grid-cols-3">
          <form onSubmit={onSubmit} className="glass rounded-3xl p-8 md:col-span-2">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                  Nom complet *
                </Label>
                <Input
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                  Entreprise
                </Label>
                <Input
                  value={form.company}
                  onChange={(e) => setForm({ ...form, company: e.target.value })}
                />
              </div>
            </div>
            <div className="mt-4 space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                Email professionnel *
              </Label>
              <Input
                type="email"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>
            <div className="mt-4 space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                Parlez-nous de votre cas d'usage *
              </Label>
              <Textarea
                rows={5}
                value={form.message}
                onChange={(e) => setForm({ ...form, message: e.target.value })}
                required
              />
            </div>
            <Button
              type="submit"
              disabled={loading}
              className="mt-6 w-full bg-gradient-to-r from-primary to-accent"
            >
              {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Envoyer le message
            </Button>
          </form>

          <div className="space-y-4">
            <div className="glass rounded-2xl p-6">
              <div className="text-xs uppercase tracking-widest text-muted-foreground">Email</div>
              <a
                href="mailto:hello@prisme.ai"
                className="mt-2 flex items-center gap-2 text-sm hover:text-primary"
              >
                <Mail className="h-4 w-4" /> hello@prisme.ai
              </a>
            </div>
            <div className="glass rounded-2xl p-6">
              <div className="text-xs uppercase tracking-widest text-muted-foreground">Réseaux</div>
              <div className="mt-3 flex gap-3">
                <a
                  href="#"
                  aria-label="LinkedIn"
                  className="glass rounded-lg p-2 hover:text-primary"
                >
                  <Linkedin className="h-4 w-4" />
                </a>
                <a href="#" aria-label="GitHub" className="glass rounded-lg p-2 hover:text-primary">
                  <Github className="h-4 w-4" />
                </a>
              </div>
            </div>
            <div className="glass rounded-2xl p-6">
              <div className="text-xs uppercase tracking-widest text-muted-foreground">Bureau</div>
              <p className="mt-2 text-sm text-muted-foreground">
                PRISME SAS
                <br />
                Paris — France
              </p>
            </div>
          </div>
        </div>
      </section>
    </MarketingLayout>
  );
}

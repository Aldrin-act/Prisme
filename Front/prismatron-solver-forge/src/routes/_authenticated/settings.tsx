import { createFileRoute } from "@tanstack/react-router";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/app-page";

export const Route = createFileRoute("/_authenticated/settings")({
  head: () => ({ meta: [{ title: "Paramètres — PRISME" }] }),
  component: SettingsPage,
});

function SettingsPage() {
  const { utilisateur } = Route.useRouteContext();
  return (
    <>
      <PageHeader
        title="Paramètres"
        desc="Gérez votre profil, votre organisation et vos intégrations."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="glass rounded-2xl p-6">
          <h3 className="font-semibold">Profil</h3>
          <div className="mt-4 space-y-3">
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                Email
              </Label>
              <Input value={utilisateur.email} readOnly />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                Nom affiché
              </Label>
              <Input defaultValue={`${utilisateur.prenom} ${utilisateur.nom}`} />
            </div>
            <Button className="bg-gradient-to-r from-primary to-accent">
              Enregistrer les modifications
            </Button>
          </div>
        </div>
        <div className="glass rounded-2xl p-6">
          <h3 className="font-semibold">Organisation</h3>
          <div className="mt-4 space-y-3">
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                Entreprise
              </Label>
              <Input placeholder="Acme Manufacturing" />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                Offre
              </Label>
              <Input value="Professionnel" readOnly />
            </div>
            <Button variant="outline">Gérer la facturation</Button>
          </div>
        </div>
      </div>
    </>
  );
}

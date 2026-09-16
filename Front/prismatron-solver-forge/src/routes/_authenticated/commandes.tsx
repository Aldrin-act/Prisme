import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { AlertTriangle, CheckCircle2, ClipboardList, Clock, Plus, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader, EmptyState } from "@/components/app-page";
import { FormulaireNouvelleCommande } from "@/components/commandes/formulaire-nouvelle-commande";
import {
  useCommandes,
  useInstance,
  useInstances,
  useLabelsInstances,
  type StatutCommande,
} from "@/integrations/prisme";
import { aujourdhui, debutJour, formatDateRelative } from "@/lib/dates-relatives";

export const Route = createFileRoute("/_authenticated/commandes")({
  head: () => ({ meta: [{ title: "Commandes — PRISME" }] }),
  component: CommandesPage,
});

// Ancrage calendaire d'une commande : l'horodatage réel de la dernière exécution réussie de
// son atelier (fait historique figé côté serveur) si connu, sinon "aujourd'hui" — une
// prévisualisation "si exécuté maintenant" qui peut légitimement dériver tant que l'atelier
// n'a jamais tourné. Jamais recalculée côté DSL/backend (voir src/lib/dates-relatives.ts).
function ancrage(commande: StatutCommande): Date {
  return commande.date_execution ? debutJour(new Date(commande.date_execution)) : aujourdhui();
}

function dateDebutExecution(commande: StatutCommande): string | null {
  if (!commande.planifiee || commande.operations.length === 0) return null;
  const debut = Math.min(...commande.operations.map((o) => o.debut));
  return formatDateRelative(debut, ancrage(commande));
}

function dateEcheance(commande: StatutCommande): string | null {
  if (commande.date_limite === null) return null;
  return formatDateRelative(commande.date_limite, ancrage(commande));
}

// En retard d'abord, puis échéance la plus proche, puis planifiée sans échéance, puis non
// planifiée en dernier — surface ce qui mérite le plus l'attention en haut de la liste, pas
// d'ordre interactif pour cette page (même choix que ListeSources/le tableau principal
// d'Instances : non paginé, tri fixe). Priorités numériques explicites plutôt que comparer
// `en_retard` (`true | false | null`) directement : `null` n'est ni "pire" ni "meilleur" que
// `false`, juste incomparable (aucune échéance à évaluer) — un comparateur naïf sur ces trois
// valeurs n'est pas transitif et produit un ordre incohérent selon l'algorithme de tri.
function prioriteUrgence(c: StatutCommande): number {
  if (c.en_retard === true) return 0;
  if (c.en_retard === false) return 1;
  if (c.planifiee) return 2; // planifiée, sans échéance déclarée
  return 3; // non planifiée
}

function comparerUrgence(a: StatutCommande, b: StatutCommande): number {
  const prioriteA = prioriteUrgence(a);
  const prioriteB = prioriteUrgence(b);
  if (prioriteA !== prioriteB) return prioriteA - prioriteB;
  if (a.date_limite === null || b.date_limite === null) return 0;
  return a.date_limite - b.date_limite;
}

function BadgeStatut({ commande }: { commande: StatutCommande }) {
  if (commande.en_retard) {
    return (
      <Badge variant="destructive" className="gap-1">
        <AlertTriangle className="h-3 w-3" /> En retard
      </Badge>
    );
  }
  if (!commande.planifiee) {
    return (
      <Badge variant="outline" className="gap-1">
        <Clock className="h-3 w-3" /> Non planifiée
      </Badge>
    );
  }
  // en_retard reste `null` (jamais faux) tant qu'aucune échéance n'est déclarée — voir
  // calculer_statut_commande, api/comparaison_scenarios.py : rien à comparer, donc pas
  // vraiment "à temps" non plus, juste hors de portée du jugement de retard.
  if (commande.date_limite === null) {
    return (
      <Badge variant="outline" className="gap-1">
        Sans échéance
      </Badge>
    );
  }
  return (
    <Badge variant="secondary" className="gap-1">
      <CheckCircle2 className="h-3 w-3" /> À temps
    </Badge>
  );
}

// Choix de l'atelier (instance) concerné par la nouvelle commande, puis le même formulaire que
// l'onglet Flux d'une instance (`FormulaireNouvelleCommande`, jamais dupliqué) — cette page
// couvrant tous les ateliers à la fois, contrairement à l'onglet Flux déjà scopé à une instance,
// il lui faut ce sélecteur en plus.
function SectionNouvelleCommandeGlobale() {
  const { data: instances } = useInstances();
  const labels = useLabelsInstances();
  const [instanceId, setInstanceId] = useState<string | null>(null);
  const { data: instance, isLoading: instanceEnChargement } = useInstance(instanceId);

  return (
    <div className="glass space-y-3 rounded-2xl p-4">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Nouvelle commande</h3>
        {instanceId && (
          <Button size="sm" variant="ghost" onClick={() => setInstanceId(null)}>
            <X className="mr-1.5 h-3.5 w-3.5" /> Changer d'atelier
          </Button>
        )}
      </div>

      <div className="max-w-sm space-y-1">
        <Label>Atelier</Label>
        <Select value={instanceId ?? undefined} onValueChange={setInstanceId}>
          <SelectTrigger>
            <SelectValue placeholder="Choisir l'atelier concerné" />
          </SelectTrigger>
          <SelectContent>
            {(instances ?? []).map((inst) => {
              const info = labels.get(inst.instance_id);
              return (
                <SelectItem key={inst.instance_id} value={inst.instance_id}>
                  {info ? info.label : inst.instance_id} · {inst.client_id}
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
      </div>

      {instanceId && instanceEnChargement && (
        <p className="text-xs text-muted-foreground">Chargement de l'atelier...</p>
      )}
      {instanceId && instance && <FormulaireNouvelleCommande instance={instance} />}
    </div>
  );
}

function CommandesPage() {
  const { data: commandes, isLoading } = useCommandes();

  if (!isLoading && commandes && commandes.length === 0) {
    return (
      <>
        <PageHeader
          title="Commandes"
          desc="Suivez les commandes clients à travers tous les ateliers — échéance et date de début d'exécution prévues."
        />
        <SectionNouvelleCommandeGlobale />
        <EmptyState
          icon={ClipboardList}
          title="Aucune commande pour l'instant"
          desc="Une commande relie des tâches déjà présentes dans un atelier à une échéance client — choisissez un atelier ci-dessus pour en ajouter une."
        />
      </>
    );
  }

  const commandesTriees = [...(commandes ?? [])].sort(comparerUrgence);

  return (
    <>
      <PageHeader
        title="Commandes"
        desc="Suivez les commandes clients à travers tous les ateliers — échéance et date de début d'exécution prévues."
      />

      <SectionNouvelleCommandeGlobale />

      <div className="glass overflow-hidden rounded-2xl">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Commande</TableHead>
                <TableHead>Atelier</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Tâches</TableHead>
                <TableHead>Échéance</TableHead>
                <TableHead>Début d'exécution</TableHead>
                <TableHead>Statut</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {commandesTriees.map((commande) => (
                <TableRow key={commande.commande_id}>
                  <TableCell className="font-mono text-xs">{commande.commande_id}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">
                      {commande.instance_id}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm">{commande.client_id}</TableCell>
                  <TableCell title={commande.taches.join(", ")}>
                    {commande.taches.length} tâche{commande.taches.length > 1 ? "s" : ""}
                    {commande.taches_manquantes.length > 0 && (
                      <span className="ml-1 text-xs text-amber-600 dark:text-amber-400">
                        ({commande.taches_manquantes.length} manquante
                        {commande.taches_manquantes.length > 1 ? "s" : ""})
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-sm">{dateEcheance(commande) ?? "—"}</TableCell>
                  <TableCell className="text-sm">{dateDebutExecution(commande) ?? "—"}</TableCell>
                  <TableCell>
                    <BadgeStatut commande={commande} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </>
  );
}

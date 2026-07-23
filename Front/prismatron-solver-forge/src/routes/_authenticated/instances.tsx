import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQueryClient, useQueries } from "@tanstack/react-query";
import { AlertCircle, Eye, FolderKanban, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageHeader, EmptyState } from "@/components/app-page";
import { IngestionDialog } from "@/components/ingestion/ingestion-dialog";
import {
  prismeKeys,
  prismeClient,
  useInstances,
  useInstance,
  useProjets,
  useSupprimerInstance,
  PrismeAPIError,
  type ProjetDetail,
  type Contrainte,
  type Objectif,
} from "@/integrations/prisme";

export const Route = createFileRoute("/_authenticated/instances")({
  head: () => ({ meta: [{ title: "Instances — PRISME" }] }),
  component: InstancesPage,
});

function InstancesPage() {
  const [dialogOuvert, setDialogOuvert] = useState(false);
  const [aSupprimer, setASupprimer] = useState<string | null>(null);
  const [aVoir, setAVoir] = useState<string | null>(null);
  const { data: instances, isLoading } = useInstances();
  const { data: projets } = useProjets();
  const queryClient = useQueryClient();
  const supprimer = useSupprimerInstance();

  // /supervision/instances ne relie pas les instances à leur projet — seul
  // GET /projets/{id} donne ce lien (`instances: [{instance_id, ...}]`).
  // On charge donc le détail de chaque projet pour reconstruire, côté
  // client, l'association instance → (nom du projet, rang de génération).
  const detailsProjets = useQueries({
    queries: (projets ?? []).map((projet) => ({
      queryKey: prismeKeys.projet(projet.projet_id),
      queryFn: () => prismeClient.obtenirProjet(projet.projet_id),
    })),
  });

  const infoParInstance = new Map<string, { nomProjet: string; label: string; projetId: string }>();
  detailsProjets.forEach((requete) => {
    const detail = requete.data as ProjetDetail | undefined;
    if (!detail) return;
    const nom = detail.nom ?? "Sans nom";
    // Le backend renvoie les instances du plus récent au plus ancien —
    // on inverse pour numéroter dans l'ordre de génération (1, 2, 3...).
    [...detail.instances].reverse().forEach((instance, index) => {
      infoParInstance.set(instance.instance_id, {
        nomProjet: nom,
        label: `${nom}-${index + 1}`,
        projetId: detail.projet_id,
      });
    });
  });

  const boutonNouvelleInstance = (
    <Button className="bg-gradient-to-r from-primary to-accent" onClick={() => setDialogOuvert(true)}>
      <Plus className="mr-2 h-4 w-4" /> Nouvelle instance
    </Button>
  );

  function ouvrirConfirmation(instanceId: string) {
    supprimer.reset();
    setASupprimer(instanceId);
  }

  function confirmerSuppression() {
    if (!aSupprimer) return;
    supprimer.mutate(aSupprimer, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
        queryClient.invalidateQueries({ queryKey: prismeKeys.executions() });
        queryClient.invalidateQueries({ queryKey: prismeKeys.projets() });
        setASupprimer(null);
      },
    });
  }

  const erreurSuppression = supprimer.error as PrismeAPIError | null;

  return (
    <>
      <PageHeader
        title="Instances"
        desc="Regroupez vos problèmes de planification, définitions DSL et solveurs générés en instances."
        action={boutonNouvelleInstance}
      />

      {!isLoading && instances && instances.length === 0 && (
        <EmptyState
          icon={FolderKanban}
          title="Aucune instance pour l'instant"
          desc="Une instance regroupe votre DSL, vos solveurs générés, vos exécutions et votre historique d'audit. Créez votre première instance pour commencer."
          action={boutonNouvelleInstance}
        />
      )}

      {instances && instances.length > 0 && (
        <div className="glass overflow-hidden rounded-2xl">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Instance</TableHead>
                <TableHead>Projet</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Structure des contraintes</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {instances.map((instance) => {
                const info = infoParInstance.get(instance.instance_id);
                return (
                  <TableRow key={instance.instance_id}>
                    <TableCell className="font-mono text-xs" title={instance.instance_id}>
                      {info ? info.label : instance.instance_id}
                    </TableCell>
                    <TableCell>
                      {info ? (
                        <Link
                          to="/donnees"
                          search={{ projet: info.projetId }}
                          className="text-primary underline-offset-2 hover:underline"
                        >
                          {info.nomProjet}
                        </Link>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                    <TableCell>{instance.client_id}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-mono text-xs">
                        {instance.structure_contraintes}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={instance.executee ? "secondary" : "outline"}>
                        {instance.executee ? "Exécutée" : "En attente"}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-1">
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label="Voir l'instance"
                          onClick={() => setAVoir(instance.instance_id)}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label="Supprimer l'instance"
                          onClick={() => ouvrirConfirmation(instance.instance_id)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <IngestionDialog open={dialogOuvert} onOpenChange={setDialogOuvert} />

      <AlertDialog open={!!aSupprimer} onOpenChange={(open) => !open && setASupprimer(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette instance ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action supprime définitivement l'instance <span className="font-mono text-xs">{aSupprimer}</span>{" "}
              ainsi que tout son historique d'exécution (plannings, décisions humaines). Les solveurs enregistrés
              ne sont pas affectés. Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>

          {erreurSuppression && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              <div className="flex items-center gap-2 font-medium">
                <AlertCircle className="h-4 w-4" /> Échec de la suppression
              </div>
              <p className="mt-1">{erreurSuppression.message}</p>
            </div>
          )}

          <AlertDialogFooter>
            <AlertDialogCancel disabled={supprimer.isPending}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmerSuppression}
              disabled={supprimer.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {supprimer.isPending ? "Suppression..." : "Supprimer"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <DialogDetailInstance instanceId={aVoir} onOpenChange={(open) => !open && setAVoir(null)} />
    </>
  );
}

function decrireContrainte(c: Contrainte): string {
  switch (c.type) {
    case "precedence":
      return `${c.avant} → ${c.apres}`;
    case "compatibilite_ressource_tache":
      return `${c.tache} sur ${c.ressource} (${c.duree} min)`;
    case "echeance":
      return `${c.tache} avant ${c.echeance}`;
    case "competence_requise":
      return `${c.tache} requiert « ${c.competence} »`;
  }
}

const LABELS_TYPE_OBJECTIF: Record<Objectif["type"], string> = {
  minimiser_makespan: "Minimiser le makespan",
  equilibrer_charge: "Équilibrer la charge",
  minimiser_retards: "Minimiser les retards",
  maximiser_utilisation: "Maximiser l'utilisation",
  minimiser_changements: "Minimiser les changements",
};

function decrireObjectif(o: Objectif): string {
  const poids = o.poids !== undefined ? ` (poids ${o.poids})` : "";
  return `${LABELS_TYPE_OBJECTIF[o.type]}${poids}`;
}

function DialogDetailInstance({
  instanceId,
  onOpenChange,
}: {
  instanceId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: instance, isLoading } = useInstance(instanceId);

  return (
    <Dialog open={!!instanceId} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Détail de l'instance</DialogTitle>
          <DialogDescription className="font-mono text-xs">{instanceId}</DialogDescription>
        </DialogHeader>

        {isLoading || !instance ? (
          <p className="text-sm text-muted-foreground">Chargement...</p>
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="secondary">{instance.client_id}</Badge>
              <Badge variant="outline" className="font-mono text-xs">
                {instance.structure_contraintes}
              </Badge>
            </div>

            <div>
              <h4 className="mb-2 text-sm font-semibold">Tâches ({instance.taches.length})</h4>
              <div className="flex flex-wrap gap-1.5">
                {instance.taches.map((t) => (
                  <Badge key={t.id} variant="outline" className="font-mono text-xs">
                    {t.id}
                    {t.nom ? ` — ${t.nom}` : ""}
                    {t.priorite ? ` · p${t.priorite}` : ""}
                  </Badge>
                ))}
              </div>
            </div>

            <div>
              <h4 className="mb-2 text-sm font-semibold">Ressources ({instance.ressources.length})</h4>
              <div className="flex flex-wrap gap-1.5">
                {instance.ressources.map((r) => (
                  <Badge key={r.id} variant="outline" className="font-mono text-xs">
                    {r.id}
                    {r.nom ? ` — ${r.nom}` : ""}
                    {r.competences.length > 0 ? ` · ${r.competences.join(", ")}` : ""}
                  </Badge>
                ))}
              </div>
            </div>

            <div>
              <h4 className="mb-2 text-sm font-semibold">Contraintes ({instance.contraintes.length})</h4>
              <ul className="space-y-1 text-sm text-muted-foreground">
                {instance.contraintes.map((c, i) => (
                  <li key={i} className="font-mono text-xs">
                    {decrireContrainte(c)}
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h4 className="mb-2 text-sm font-semibold">Objectifs ({instance.objectifs.length})</h4>
              <div className="flex flex-wrap gap-1.5">
                {instance.objectifs.map((o, i) => (
                  <Badge key={i} variant="secondary" className="text-xs">
                    {decrireObjectif(o)}
                  </Badge>
                ))}
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { AlertCircle, CheckCircle2, Cpu, Play, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageHeader, EmptyState } from "@/components/app-page";
import { GanttChart } from "@/components/planning/gantt-chart";
import {
  useSolveurs,
  useCommandesInstance,
  useInstance,
  useInstances,
  useLabelsInstances,
  useCodeSourceSolveur,
  useDeclencherExecution,
  usePlanning,
  usePlanningAjuste,
  PrismeAPIError,
  type SolveurInfo,
} from "@/integrations/prisme";

export const Route = createFileRoute("/_authenticated/solvers")({
  head: () => ({ meta: [{ title: "Solveurs générés — PRISME" }] }),
  component: SolversPage,
});

function SolversPage() {
  const { data: solveurs, isLoading } = useSolveurs();
  const [aVoir, setAVoir] = useState<SolveurInfo | null>(null);
  // Nom lisible de l'atelier (voir instances.tsx) — même source que le Client, mais le client_id
  // seul ne distingue pas deux ateliers d'un même client (ex. plusieurs instances "demo").
  const labels = useLabelsInstances();

  return (
    <>
      <PageHeader
        title="Solveurs générés"
        desc="Chaque solveur validé par la cascade (faisabilité, optimalité, fidélité) puis enregistré par PRISME. Chacun ne sert que l'instance pour laquelle il a été généré — exécute-le pour obtenir un planning."
      />

      {!isLoading && solveurs && solveurs.length === 0 && (
        <EmptyState
          icon={Cpu}
          title="Aucun solveur généré pour l'instant"
          desc="Génère ton premier solveur depuis la page Générateur de solveurs."
        />
      )}

      {solveurs && solveurs.length > 0 && (
        <div className="glass overflow-hidden rounded-2xl">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Solveur</TableHead>
                <TableHead>Atelier</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Structure des contraintes</TableHead>
                <TableHead>Objectifs</TableHead>
                <TableHead>Algorithme</TableHead>
                <TableHead>Généré</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {solveurs.map((s) => (
                <TableRow key={s.id}>
                  <TableCell className="font-mono text-xs" title={s.id}>
                    {s.id.slice(0, 8)}…
                  </TableCell>
                  <TableCell className="font-mono text-xs" title={s.instance_id ?? undefined}>
                    {s.instance_id
                      ? (labels.get(s.instance_id)?.label ?? `${s.instance_id.slice(0, 8)}…`)
                      : "orphelin"}
                  </TableCell>
                  <TableCell>{s.client_id}</TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">
                      {s.structure_contraintes}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">
                      {s.signature_objectifs}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    {s.algorithme ? (
                      <Badge variant="secondary" className="font-mono text-xs">
                        {s.algorithme}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {new Date(s.date_validation).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button size="sm" variant="outline" onClick={() => setAVoir(s)}>
                      <Play className="mr-1.5 h-3.5 w-3.5" /> Exécuter
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      <DialogSolveur solveur={aVoir} onOpenChange={(open) => !open && setAVoir(null)} />
    </>
  );
}

function DialogSolveur({
  solveur,
  onOpenChange,
}: {
  solveur: SolveurInfo | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: instances } = useInstances();
  const labels = useLabelsInstances();
  const [instanceId, setInstanceId] = useState("");
  // Uniquement pour ses `contraintes` (taux d'utilisation) et `taches` (produit affiché sur les
  // barres) consommés par GanttChart — le reste de ce dialogue s'appuie déjà sur `InstanceInfo`
  // (liste ci-dessus).
  const { data: instanceChoisie } = useInstance(instanceId || null);
  const { data: commandes } = useCommandesInstance(instanceId || null);
  const [horizonGeleJours, setHorizonGeleJours] = useState("");
  const [executionId, setExecutionId] = useState<string | null>(null);
  const [voirOriginal, setVoirOriginal] = useState(false);
  const declencher = useDeclencherExecution();
  const {
    data: planning,
    isLoading: chargementPlanning,
    error: erreurPlanning,
  } = usePlanning(executionId);
  const { data: planningAjuste } = usePlanningAjuste(executionId);
  const { data: codeSource, isLoading: chargementCode } = useCodeSourceSolveur(solveur?.id ?? null);

  // Un solveur ne sert que l'instance qui l'a fait générer (plus de partage par signature entre
  // instances) — plus de choix à faire, l'instance à exécuter est directement celle du solveur.
  // `null` uniquement pour un solveur enregistré avant ce changement (orphelin, jamais exécutable).
  const instanceProprietaire = (instances ?? []).find(
    (i) => i.instance_id === solveur?.instance_id,
  );

  useEffect(() => {
    setInstanceId(solveur?.instance_id ?? "");
    setExecutionId(null);
    setVoirOriginal(false);
    declencher.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [solveur?.id]);

  function fermer(open: boolean) {
    if (!open) {
      setInstanceId("");
      setHorizonGeleJours("");
      setExecutionId(null);
      setVoirOriginal(false);
      declencher.reset();
    }
    onOpenChange(open);
  }

  function executer() {
    if (!instanceId) return;
    setExecutionId(null);
    declencher.mutate(
      {
        instanceId,
        horizonGeleJours: horizonGeleJours ? Number(horizonGeleJours) : undefined,
      },
      {
        onSuccess: (reponse) => {
          if (reponse.reussi) setExecutionId(reponse.execution_id);
        },
      },
    );
  }

  const erreurRequete = declencher.error as PrismeAPIError | null;
  const reponseExecution = declencher.data;

  return (
    <Dialog open={!!solveur} onOpenChange={fermer}>
      <DialogContent className="max-h-[85vh] max-w-5xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Solveur</DialogTitle>
          <DialogDescription className="font-mono text-xs">{solveur?.id}</DialogDescription>
        </DialogHeader>

        {solveur && (
          <Tabs defaultValue="executer">
            <TabsList>
              <TabsTrigger value="executer">Exécuter</TabsTrigger>
              <TabsTrigger value="planning">Planning</TabsTrigger>
              <TabsTrigger value="code">Code source</TabsTrigger>
            </TabsList>

            <TabsContent value="executer" className="space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="secondary">{solveur.client_id}</Badge>
                <Badge variant="outline" className="font-mono text-xs">
                  {solveur.structure_contraintes}
                </Badge>
                <Badge variant="outline" className="font-mono text-xs">
                  {solveur.signature_objectifs}
                </Badge>
                {solveur.algorithme && (
                  <Badge variant="secondary" className="font-mono text-xs">
                    {solveur.algorithme}
                  </Badge>
                )}
              </div>

              {solveur.algorithme_raison && (
                <p className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">Pourquoi cet algorithme : </span>
                  {solveur.algorithme_raison}
                </p>
              )}

              {!solveur.instance_id ? (
                <p className="text-sm text-muted-foreground">
                  Solveur orphelin — enregistré avant qu'un solveur ne soit rattaché à une instance
                  précise, aucune instance d'origine connue. Génère un nouveau solveur depuis la
                  page Générateur de solveurs pour pouvoir l'exécuter.
                </p>
              ) : !instanceProprietaire ? (
                <p className="text-sm text-muted-foreground">
                  L'instance {solveur.instance_id} pour laquelle ce solveur a été généré n'existe
                  plus (supprimée).
                </p>
              ) : (
                <div className="space-y-3">
                  <div>
                    <p className="mb-2 text-sm font-medium">Instance à exécuter</p>
                    <p className="text-sm">
                      {labels.get(instanceProprietaire.instance_id)?.label ??
                        instanceProprietaire.instance_id}
                    </p>
                  </div>

                  <Button onClick={executer} disabled={!instanceId || declencher.isPending}>
                    <Play className="mr-2 h-4 w-4" />
                    {declencher.isPending ? "Exécution en cours..." : "Exécuter le solveur"}
                  </Button>

                  {erreurRequete && (
                    <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                      <div className="flex items-center gap-2 font-medium">
                        <AlertCircle className="h-4 w-4" /> Échec de la requête
                      </div>
                      <p className="mt-1">{erreurRequete.message}</p>
                    </div>
                  )}

                  {reponseExecution && !reponseExecution.reussi && (
                    <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                      <div className="flex items-center gap-2 font-medium">
                        <XCircle className="h-4 w-4" /> Exécution en échec
                      </div>
                      {reponseExecution.erreur && <p className="mt-1">{reponseExecution.erreur}</p>}
                    </div>
                  )}

                  {reponseExecution?.reussi && (
                    <div className="rounded-lg border border-primary/40 bg-primary/5 p-3 text-sm">
                      <div className="flex items-center gap-2 font-medium text-primary">
                        <CheckCircle2 className="h-4 w-4" /> Exécution réussie — voir l'onglet
                        Planning
                      </div>
                    </div>
                  )}
                </div>
              )}
            </TabsContent>

            <TabsContent value="planning">
              {chargementPlanning ? (
                <p className="text-sm text-muted-foreground">Chargement du planning...</p>
              ) : erreurPlanning ? (
                <p className="text-sm text-destructive">
                  {(erreurPlanning as PrismeAPIError).message}
                </p>
              ) : planning ? (
                <div className="space-y-3">
                  {planningAjuste && (
                    <div className="flex items-center justify-between">
                      <Badge variant="secondary">
                        {voirOriginal ? "Planning original" : "Planning ajusté"}
                      </Badge>
                      <Button size="sm" variant="ghost" onClick={() => setVoirOriginal((v) => !v)}>
                        {voirOriginal ? "Voir l'ajustement" : "Voir l'original"}
                      </Button>
                    </div>
                  )}
                  <GanttChart
                    planning={!voirOriginal && planningAjuste ? planningAjuste : planning}
                    contraintes={instanceChoisie?.contraintes}
                    taches={instanceChoisie?.taches}
                    commandes={commandes}
                    uniteDuree={instanceChoisie?.unite_duree}
                    editable={!voirOriginal}
                    executionId={executionId ?? undefined}
                    instanceId={instanceChoisie?.instance_id}
                  />
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Aucune exécution pour l'instant — lance le solveur depuis l'onglet Exécuter pour
                  voir son planning ici.
                </p>
              )}
            </TabsContent>

            <TabsContent value="code">
              <pre className="max-h-96 overflow-auto rounded-md border border-border/50 bg-muted/30 p-3 text-xs">
                <code>{chargementCode ? "Chargement du code..." : codeSource?.code_source}</code>
              </pre>
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}

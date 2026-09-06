import { useState } from "react";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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

  return (
    <>
      <PageHeader
        title="Solveurs générés"
        desc="Chaque solveur validé par la cascade (faisabilité, optimalité, fidélité) puis enregistré par PRISME. Exécute-le sur une instance compatible pour obtenir un planning."
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
                <TableHead>Client</TableHead>
                <TableHead>Structure des contraintes</TableHead>
                <TableHead>Objectifs</TableHead>
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
  // Uniquement pour son `unite_duree` (affichage du Gantt) — le reste de ce
  // dialogue s'appuie déjà sur `InstanceInfo` (liste ci-dessus).
  const { data: instanceChoisie } = useInstance(instanceId || null);
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

  // On choisit une instance dont le client + la structure de contraintes
  // correspondent au solveur — approximatif sans les objectifs comme
  // ailleurs dans l'app ; /execution refait le matching exact côté serveur
  // et renvoie une erreur 409 claire en cas de décalage.
  const instancesCompatibles = (instances ?? []).filter(
    (i) =>
      solveur &&
      i.client_id === solveur.client_id &&
      i.structure_contraintes === solveur.structure_contraintes,
  );

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

  function changerInstance(id: string) {
    setInstanceId(id);
    setExecutionId(null);
    setVoirOriginal(false);
    declencher.reset();
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
              </div>

              {instancesCompatibles.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  Aucune instance ne correspond à ce client et cette structure de contraintes.
                  Ingère ou génère une instance compatible depuis la page Données ou Instances pour
                  pouvoir exécuter ce solveur.
                </p>
              ) : (
                <div className="space-y-3">
                  <div>
                    <p className="mb-2 text-sm font-medium">Instance à exécuter</p>
                    <Select value={instanceId} onValueChange={changerInstance}>
                      <SelectTrigger className="w-full">
                        <SelectValue placeholder="Choisir une instance compatible..." />
                      </SelectTrigger>
                      <SelectContent>
                        {instancesCompatibles.map((i) => (
                          <SelectItem key={i.instance_id} value={i.instance_id}>
                            {labels.get(i.instance_id)?.label ?? i.instance_id}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="horizon_gele_jours" className="text-xs text-muted-foreground">
                      Horizon gelé (jours, optionnel)
                    </Label>
                    <Input
                      id="horizon_gele_jours"
                      type="number"
                      min={0}
                      value={horizonGeleJours}
                      onChange={(e) => setHorizonGeleJours(e.target.value)}
                      placeholder="0"
                      className="w-32"
                    />
                    <p className="text-xs text-muted-foreground">
                      Fige les opérations déjà planifiées qui commencent avant ce nombre de jours —
                      reprend le dernier planning réussi de cette instance, sans effet s'il n'y en a
                      pas encore.
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
                      {reponseExecution.horizon_gele_jours > 0 && (
                        <p className="mt-1 text-xs text-muted-foreground">
                          {reponseExecution.planning_precedent_utilise
                            ? "Horizon gelé appliqué — les opérations déjà planifiées dans la fenêtre ont été reprises telles quelles."
                            : "Aucun planning précédent trouvé pour cette instance — solve normal, rien n'a été figé."}
                        </p>
                      )}
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
                    editable={!voirOriginal}
                    executionId={executionId ?? undefined}
                    uniteDuree={instanceChoisie?.unite_duree}
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

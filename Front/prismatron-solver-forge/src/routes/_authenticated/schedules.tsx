import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Calendar, CheckCircle2, Code2, Cpu, Eye, HelpCircle, X, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { PageHeader, EmptyState } from "@/components/app-page";
import { PlanningCalendar } from "@/components/planning/planning-calendar";
import { GanttChart } from "@/components/planning/gantt-chart";
import {
  useCommandesInstance,
  useExecutions,
  useInstance,
  useLabelsInstances,
  usePlanning,
  usePlanningAjuste,
  useSolveurs,
  useCodeSource,
  PrismeAPIError,
  type ExecutionInfo,
} from "@/integrations/prisme";

const TOUS_LES_ATELIERS = "_tous";

export const Route = createFileRoute("/_authenticated/schedules")({
  head: () => ({ meta: [{ title: "Plannings — PRISME" }] }),
  component: SchedulesPage,
});

function BadgeDecision({ decision }: { decision: ExecutionInfo["decision"] }) {
  if (decision === "acceptee") {
    return (
      <Badge variant="secondary" className="gap-1">
        <CheckCircle2 className="h-3 w-3" /> Approuvé
      </Badge>
    );
  }
  if (decision === "refusee") {
    return (
      <Badge variant="destructive" className="gap-1">
        <XCircle className="h-3 w-3" /> Rejeté
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <HelpCircle className="h-3 w-3" /> En attente
    </Badge>
  );
}

function SchedulesPage() {
  const { data: executions, isLoading } = useExecutions();
  const labels = useLabelsInstances();
  const [aVoir, setAVoir] = useState<ExecutionInfo | null>(null);
  const [filtreAtelierId, setFiltreAtelierId] = useState(TOUS_LES_ATELIERS);

  const executionsTriees = [...(executions ?? [])].sort((a, b) =>
    (b.date_execution ?? "").localeCompare(a.date_execution ?? ""),
  );

  // Ateliers (instances) ayant au moins un planning — inutile de proposer un filtre sur un
  // atelier qui n'en a aucun. Dérivé des exécutions déjà chargées, pas un appel séparé.
  const ateliers = new Map<string, string>();
  for (const e of executionsTriees) {
    if (!ateliers.has(e.instance_id)) {
      ateliers.set(e.instance_id, labels.get(e.instance_id)?.label ?? e.instance_id);
    }
  }

  function changerFiltreAtelier(id: string) {
    setFiltreAtelierId(id);
    // Changer d'atelier vide la sélection courante plutôt que de garder affiché un planning
    // qui ne correspond plus au filtre — jamais un planning orphelin du contexte affiché.
    setAVoir(null);
  }

  const executionsAffichees =
    filtreAtelierId === TOUS_LES_ATELIERS
      ? executionsTriees
      : executionsTriees.filter((e) => e.instance_id === filtreAtelierId);

  return (
    <>
      <PageHeader
        title="Plannings"
        desc="Les plannings proposés par chaque exécution de solveur — un par exécution, jamais recalculés à la volée : ce que le bac à sable a produit, tel quel."
      />

      {/* Toujours affiché, même vierge (aucune exécution sélectionnée) — jamais caché derrière
          un clic "Voir le planning" : c'est la vue principale de la page. */}
      <SectionPlanning
        key={aVoir?.execution_id ?? "vierge"}
        execution={aVoir}
        onEffacer={() => setAVoir(null)}
      />

      {!isLoading && executionsTriees.length === 0 && (
        <EmptyState
          icon={Calendar}
          title="Aucun planning pour l'instant"
          desc="Exécute un solveur depuis la page Solveurs générés pour voir son planning apparaître ici."
        />
      )}

      {executionsTriees.length > 0 && (
        <div className="mt-4 mb-4 max-w-xs space-y-1.5">
          <Label htmlFor="filtre_atelier" className="text-xs text-muted-foreground">
            Atelier
          </Label>
          <Select value={filtreAtelierId} onValueChange={changerFiltreAtelier}>
            <SelectTrigger id="filtre_atelier">
              <SelectValue placeholder="Tous les ateliers" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TOUS_LES_ATELIERS}>Tous les ateliers</SelectItem>
              {[...ateliers.entries()].map(([id, label]) => (
                <SelectItem key={id} value={id}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}

      {executionsAffichees.length > 0 && (
        <div className="glass overflow-hidden rounded-2xl">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Instance</TableHead>
                <TableHead>Client</TableHead>
                <TableHead>Date d'exécution</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead>Décision</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {executionsAffichees.map((e) => (
                <TableRow
                  key={e.execution_id}
                  className={e.execution_id === aVoir?.execution_id ? "bg-primary/5" : undefined}
                >
                  <TableCell>{labels.get(e.instance_id)?.label ?? e.instance_id}</TableCell>
                  <TableCell>{e.client_id}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {e.date_execution ? new Date(e.date_execution).toLocaleString() : "—"}
                  </TableCell>
                  <TableCell>
                    {e.reussi ? (
                      <Badge variant="secondary" className="gap-1">
                        <CheckCircle2 className="h-3 w-3" /> Réussi
                      </Badge>
                    ) : (
                      <Badge variant="destructive" className="gap-1">
                        <XCircle className="h-3 w-3" /> Échec
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>{e.reussi ? <BadgeDecision decision={e.decision} /> : "—"}</TableCell>
                  <TableCell className="text-right">
                    {e.reussi ? (
                      <Button
                        size="sm"
                        variant={e.execution_id === aVoir?.execution_id ? "secondary" : "outline"}
                        onClick={() => setAVoir(e)}
                      >
                        <Eye className="mr-1.5 h-3.5 w-3.5" /> Voir le planning
                      </Button>
                    ) : (
                      <span className="text-xs text-muted-foreground" title={e.erreur ?? undefined}>
                        {e.erreur ? "Erreur à l'exécution" : ""}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}

// Toujours montée (voir SchedulesPage) — `execution === null` affiche un calendrier vierge plutôt
// que de disparaître complètement. `key={execution.execution_id}` sur le call site force un
// remontage propre à chaque changement de sélection, pour repartir sur "Planning original" plutôt
// que de garder la bascule ajusté/original de l'exécution précédente.
function SectionPlanning({
  execution,
  onEffacer,
}: {
  execution: ExecutionInfo | null;
  onEffacer: () => void;
}) {
  const { data: planning, isLoading, error } = usePlanning(execution?.execution_id ?? null);
  const { data: planningAjuste } = usePlanningAjuste(execution?.execution_id ?? null);
  // Charges/capacités/disponibilités par ressource, pour distinguer les tâches en retard sur le
  // calendrier — même instance que l'exécution, toujours disponible sans requête supplémentaire
  // (ExecutionInfo.instance_id).
  const { data: instance } = useInstance(execution?.instance_id ?? null);
  // Commandes de cet atelier, pour les faire apparaître sur les événements/l'échéance du
  // calendrier (voir GET /ingestion/{instance_id}/commandes) — même instance que l'exécution
  // affichée.
  const { data: commandes } = useCommandesInstance(execution?.instance_id ?? null);
  // Métadonnées du solveur (algorithme, date de validation) — endpoint léger, sans code source,
  // safe à charger sans action explicite (contrairement à `useCodeSource` ci-dessous, l'audit
  // "source, explicite uniquement", voir CLAUDE.md).
  const { data: solveurs } = useSolveurs();
  const solveur = solveurs?.find((s) => s.id === execution?.id_solveur);
  const [voirCode, setVoirCode] = useState(false);
  const { data: codeSource, isLoading: chargementCode } = useCodeSource(
    voirCode && execution ? execution.execution_id : null,
  );
  const [voirOriginal, setVoirOriginal] = useState(false);

  const planningAffiche = !voirOriginal && planningAjuste ? planningAjuste : planning;

  return (
    <div className="glass space-y-3 rounded-2xl p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold">Planning</h3>
          {execution && (
            <p className="font-mono text-xs text-muted-foreground">{execution.execution_id}</p>
          )}
        </div>
        {execution && (
          <Button
            size="icon"
            variant="ghost"
            onClick={onEffacer}
            aria-label="Effacer la sélection"
            title="Effacer la sélection"
          >
            <X className="h-4 w-4" />
          </Button>
        )}
      </div>

      {execution && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/50 bg-muted/20 p-2.5 text-xs">
          <Cpu className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="font-medium">Solveur généré :</span>
          <Badge variant="outline" className="font-mono">
            {execution.id_solveur}
          </Badge>
          {solveur?.algorithme && <Badge variant="secondary">{solveur.algorithme}</Badge>}
          {solveur?.date_validation && (
            <span className="text-muted-foreground">
              validé le {new Date(solveur.date_validation).toLocaleDateString()}
            </span>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="ml-auto h-6 gap-1 px-2 text-xs"
            onClick={() => setVoirCode((v) => !v)}
          >
            <Code2 className="h-3 w-3" />
            {voirCode ? "Masquer le code source" : "Voir le code source"}
          </Button>
        </div>
      )}

      {voirCode && (
        <div className="space-y-1.5">
          {solveur?.algorithme_raison && (
            <p className="text-xs text-muted-foreground">{solveur.algorithme_raison}</p>
          )}
          {chargementCode ? (
            <p className="text-xs text-muted-foreground">Chargement du code source...</p>
          ) : codeSource ? (
            <pre className="max-h-96 overflow-auto rounded-lg border border-border/50 bg-muted/10 p-3 text-xs">
              <code>{codeSource.code_source}</code>
            </pre>
          ) : null}
        </div>
      )}

      {isLoading && <p className="text-sm text-muted-foreground">Chargement du planning...</p>}
      {error && <p className="text-sm text-destructive">{(error as PrismeAPIError).message}</p>}

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

      <Tabs defaultValue="ressources">
        <TabsList>
          <TabsTrigger value="ressources">Vue par ressource</TabsTrigger>
          <TabsTrigger value="calendrier">Calendrier</TabsTrigger>
        </TabsList>

        <TabsContent value="ressources" className="pt-3">
          {planningAffiche ? (
            <GanttChart
              planning={planningAffiche}
              contraintes={instance?.contraintes}
              taches={instance?.taches}
              commandes={commandes}
              uniteDuree={instance?.unite_duree}
              editable={!voirOriginal}
              executionId={execution?.execution_id}
              instanceId={instance?.instance_id}
            />
          ) : (
            <p className="text-sm text-muted-foreground">
              Aucun planning sélectionné pour l'instant — choisis une exécution ci-dessous.
            </p>
          )}
        </TabsContent>

        <TabsContent value="calendrier" className="pt-3">
          <PlanningCalendar
            planning={planningAffiche ?? null}
            contraintes={instance?.contraintes}
            taches={instance?.taches}
            commandes={commandes}
            uniteDuree={instance?.unite_duree}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}

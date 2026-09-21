import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, EmptyState } from "@/components/app-page";
import { AlertTriangle, BarChart3, Boxes, CheckCircle2, Loader2, XCircle } from "lucide-react";
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
import {
  useExecutions,
  useInstance,
  useInstances,
  useJobsGeneration,
  useLabelsInstances,
  usePlanning,
  useSolveurs,
  useStatistiquesGeneration,
  type InstanceDetail,
  type JobGenerationInfo,
  type PlanningAvecDurees,
} from "@/integrations/prisme";
import { chargeParJour, chargeParRessource, tachesEnRetard } from "@/lib/charge-ressources";
import { debutJour, formatDateRelative } from "@/lib/dates-relatives";
import { formatDuree } from "@/lib/unite-duree";

// Une ressource à ce taux de charge ou plus, sur tout le makespan, compte
// comme un goulot d'étranglement — seuil pragmatique, pas une valeur du DSL.
const SEUIL_GOULOT = 85;

const TOUS_LES_AGENTS = "tous";

export const Route = createFileRoute("/_authenticated/app")({
  head: () => ({ meta: [{ title: "Tableau de bord — PRISME" }] }),
  component: AppDashboard,
});

// Le nom d'agent brut inclut le numéro de tentative de la boucle de
// réparation ("reviewer (tentative 2/10)") — on l'enlève pour regrouper
// tous les passages d'un même agent, quelle que soit la tentative.
function agentNormalise(agent: string): string {
  return agent.replace(/\s*\(tentative \d+\/\d+\)$/, "");
}

interface StatAgent {
  agent: string;
  total: number;
  echecs: number;
}

function calculerStatsAgents(jobs: JobGenerationInfo[]): StatAgent[] {
  const parAgent = new Map<string, StatAgent>();
  for (const job of jobs) {
    for (const evenement of job.evenements) {
      // ne compter qu'un évènement terminal par étape — une mesure d'appel au modèle n'en est pas une
      if (evenement.statut === "en_cours" || evenement.statut === "mesure") continue;
      const nom = agentNormalise(evenement.agent);
      const stat = parAgent.get(nom) ?? { agent: nom, total: 0, echecs: 0 };
      stat.total += 1;
      if (evenement.statut === "echec") stat.echecs += 1;
      parAgent.set(nom, stat);
    }
  }
  return [...parAgent.values()].sort((a, b) => b.total - a.total);
}

// Même seuil que `SEUIL_ECHECS_BOUCLE` (api/statistiques_generation.py) — un même agent en
// échec au moins ce nombre de fois dans une génération compte comme une boucle détectée.
const SEUIL_ECHECS_BOUCLE = 3;

// Même liste que `AGENTS_CAPABLES_ECHEC` (api/statistiques_generation.py) — seuls ces nœuds
// émettent jamais `statut="echec"` dans generation/graph.py ; filtrer "Boucles détectées" sur
// un autre agent renvoie `null` côté serveur (non applicable, jamais un 0% trompeur).
const AGENTS_CAPABLES_ECHEC = new Set(["test_sandbox", "validation", "documentation", "reviewer"]);

function KpiTile({ label, valeur, detail }: { label: string; valeur: string; detail: string }) {
  return (
    <div className="rounded-xl border border-border/50 p-4">
      <div className="text-xs uppercase tracking-widest text-muted-foreground">{label}</div>
      <div className="mt-2 text-2xl font-bold">{valeur}</div>
      <div className="mt-1 text-xs text-muted-foreground">{detail}</div>
    </div>
  );
}

function AppDashboard() {
  return (
    <>
      <PageHeader
        title="Tableau de bord"
        desc="Santé du pipeline de génération de solveurs et charge des ressources de planification — deux sujets distincts, chacun sur son onglet."
      />

      <Tabs defaultValue="pipeline">
        <TabsList>
          <TabsTrigger value="pipeline">Pipeline de génération</TabsTrigger>
          <TabsTrigger value="charge">Charge des ressources</TabsTrigger>
        </TabsList>

        <TabsContent value="pipeline" className="mt-6">
          <OngletPipeline />
        </TabsContent>

        <TabsContent value="charge" className="mt-6">
          <OngletChargeRessources />
        </TabsContent>
      </Tabs>
    </>
  );
}

function OngletPipeline() {
  const [agentSelectionne, setAgentSelectionne] = useState<string>(TOUS_LES_AGENTS);
  const { data: jobs, isLoading } = useJobsGeneration();
  const { data: solveurs } = useSolveurs();
  const { data: stats } = useStatistiquesGeneration(
    agentSelectionne === TOUS_LES_AGENTS ? undefined : agentSelectionne,
  );
  const labelParInstance = useLabelsInstances();

  const tousLesJobs = jobs ?? [];
  const jobsTermines = tousLesJobs.filter((j) => j.termine);
  const jobsReussis = jobsTermines.filter((j) => j.reussi);
  const tauxReussite =
    jobsTermines.length > 0 ? (jobsReussis.length / jobsTermines.length) * 100 : null;

  const tentativesConnues = jobsTermines
    .map((j) => j.nombre_tentatives)
    .filter((n): n is number => n !== null);
  const tentativesMoyennes =
    tentativesConnues.length > 0
      ? tentativesConnues.reduce((a, b) => a + b, 0) / tentativesConnues.length
      : null;

  const statsAgents = calculerStatsAgents(tousLesJobs);
  const statsAgentsAffiches =
    agentSelectionne === TOUS_LES_AGENTS
      ? statsAgents
      : statsAgents.filter((s) => s.agent === agentSelectionne);
  const maxTotal = Math.max(1, ...statsAgentsAffiches.map((s) => s.total));

  const jobsRecents = [...tousLesJobs]
    .sort((a, b) => b.cree_le.localeCompare(a.cree_le))
    .slice(0, 10);

  return (
    <>
      <p className="mb-4 text-sm text-muted-foreground">
        Activité réelle du pipeline multi-agents de génération de solveurs — quels agents tournent,
        lesquels échouent, et à quelle fréquence, sur toutes les générations lancées depuis le
        dernier redémarrage du serveur.
      </p>

      <div className="grid gap-4 md:grid-cols-4">
        <div className="glass rounded-2xl p-5">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">
            Générations lancées
          </div>
          <div className="mt-2 text-3xl font-bold">{tousLesJobs.length}</div>
        </div>
        <div className="glass rounded-2xl p-5">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">
            Taux de réussite
          </div>
          <div className="mt-2 text-3xl font-bold">
            {tauxReussite !== null ? `${tauxReussite.toFixed(0)}%` : "—"}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {jobsReussis.length} / {jobsTermines.length} terminées
          </div>
        </div>
        <div className="glass rounded-2xl p-5">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">
            Tentatives moyennes
          </div>
          <div className="mt-2 text-3xl font-bold">
            {tentativesMoyennes !== null ? tentativesMoyennes.toFixed(1) : "—"}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">boucle de réparation, max 10</div>
        </div>
        <div className="glass rounded-2xl p-5">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">
            Solveurs enregistrés
          </div>
          <div className="mt-2 text-3xl font-bold">{solveurs?.length ?? "—"}</div>
        </div>
      </div>

      <div className="glass mt-6 rounded-2xl p-6">
        <div className="mb-1 flex flex-wrap items-center justify-between gap-3">
          <div className="text-sm font-semibold">Non-répétition (boucles)</div>
          <Select value={agentSelectionne} onValueChange={setAgentSelectionne}>
            <SelectTrigger className="h-8 w-44 text-xs">
              <SelectValue placeholder="Tous les agents" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={TOUS_LES_AGENTS}>Tous les agents</SelectItem>
              {statsAgents.map((s) => (
                <SelectItem key={s.agent} value={s.agent} className="capitalize">
                  {s.agent}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <p className="mb-4 text-xs text-muted-foreground">
          Détection de non-convergence dans la boucle de réparation bornée (tests
          sandbox/validation/debugger, max 10 tentatives) — calculé côté serveur sur toutes les
          générations persistées en base, pas seulement celles connues du process en cours (voir
          "Générations lancées" ci-dessus).
          {agentSelectionne !== TOUS_LES_AGENTS && (
            <>
              {" "}
              Restreint aux générations où <span className="capitalize">
                {agentSelectionne}
              </span>{" "}
              est intervenu ; "Boucles détectées" ne compte alors que ses propres échecs répétés.
            </>
          )}
        </p>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <KpiTile
            label="Étapes avant convergence"
            valeur={
              stats?.tentatives_moyennes_convergence != null
                ? stats.tentatives_moyennes_convergence.toFixed(1)
                : "—"
            }
            detail="tentatives en moyenne, sur les succès"
          />
          <KpiTile
            label="Taux d'épuisement"
            valeur={
              stats?.taux_epuisement_boucle != null
                ? `${stats.taux_epuisement_boucle.toFixed(0)}%`
                : "—"
            }
            detail="échecs ayant atteint la borne (10/10)"
          />
          <KpiTile
            label="Boucles détectées"
            valeur={
              agentSelectionne !== TOUS_LES_AGENTS && !AGENTS_CAPABLES_ECHEC.has(agentSelectionne)
                ? "N/A"
                : stats?.taux_boucles_detectees != null
                  ? `${stats.taux_boucles_detectees.toFixed(0)}%`
                  : "—"
            }
            detail={
              agentSelectionne === TOUS_LES_AGENTS
                ? `générations avec ≥${SEUIL_ECHECS_BOUCLE} échecs du même agent`
                : AGENTS_CAPABLES_ECHEC.has(agentSelectionne)
                  ? `générations avec ≥${SEUIL_ECHECS_BOUCLE} échecs de cet agent`
                  : "cet agent ne rapporte jamais d'échec (produit toujours une sortie)"
            }
          />
          <KpiTile
            label="Diversité des actions"
            valeur={
              stats?.diversite_actions_moyenne != null
                ? stats.diversite_actions_moyenne.toFixed(2)
                : "—"
            }
            detail="agents uniques / évènements, en moyenne"
          />
          <KpiTile
            label="Taux de stagnation"
            valeur={stats?.taux_stagnation != null ? `${stats.taux_stagnation.toFixed(0)}%` : "—"}
            detail="corrections du Debugger sans changement de code"
          />
        </div>
      </div>

      <div className="glass mt-6 rounded-2xl p-6">
        <div className="mb-1 text-sm font-semibold">Activité par agent</div>
        <p className="mb-4 text-xs text-muted-foreground">
          Nombre de passages par agent (toutes tentatives confondues) et proportion en échec, sur
          toutes les générations connues du serveur.
          {agentSelectionne !== TOUS_LES_AGENTS && " Filtré par le sélecteur ci-dessus."}
        </p>

        {!isLoading && statsAgentsAffiches.length === 0 && (
          <EmptyState
            icon={BarChart3}
            title="Aucune génération pour l'instant"
            desc="Lance une génération depuis la page Générateur de solveurs pour voir l'activité des agents ici."
          />
        )}

        <div className="space-y-2.5">
          {statsAgentsAffiches.map((s) => {
            const largeurTotale = (s.total / maxTotal) * 100;
            const largeurEchecs = s.total > 0 ? (s.echecs / s.total) * largeurTotale : 0;
            return (
              <div key={s.agent} className="flex items-center gap-3">
                <div className="w-28 shrink-0 truncate text-xs capitalize text-muted-foreground">
                  {s.agent}
                </div>
                <div className="relative h-6 flex-1 rounded bg-muted/30">
                  <div
                    className="absolute inset-y-0 left-0 rounded bg-gradient-to-r from-primary to-accent"
                    style={{ width: `${largeurTotale}%` }}
                  />
                  {s.echecs > 0 && (
                    <div
                      className="absolute inset-y-0 right-0 rounded-r bg-destructive"
                      style={{ width: `${largeurEchecs}%` }}
                    />
                  )}
                </div>
                <div className="w-20 shrink-0 text-right text-xs text-muted-foreground">
                  {s.total} · {s.echecs} échec{s.echecs !== 1 ? "s" : ""}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="glass mt-6 overflow-hidden rounded-2xl">
        <div className="border-b border-border/50 px-5 py-3 text-sm font-semibold">
          Générations récentes
        </div>
        {jobsRecents.length === 0 ? (
          <p className="p-5 text-sm text-muted-foreground">Aucune génération pour l'instant.</p>
        ) : (
          <ul>
            {jobsRecents.map((job) => (
              <li
                key={job.job_id}
                className="flex items-center justify-between border-b border-border/30 px-5 py-4 text-sm last:border-0"
              >
                <div className="flex items-center gap-3">
                  {!job.termine ? (
                    <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
                  ) : job.reussi ? (
                    <CheckCircle2 className="h-4 w-4 shrink-0 text-primary" />
                  ) : (
                    <XCircle className="h-4 w-4 shrink-0 text-destructive" />
                  )}
                  <span>{labelParInstance.get(job.instance_id)?.label ?? job.instance_id}</span>
                  <Badge variant="outline" className="text-xs">
                    {job.client_id}
                  </Badge>
                </div>
                <div className="flex items-center gap-3 text-xs text-muted-foreground">
                  {job.nombre_tentatives !== null && (
                    <span>{job.nombre_tentatives} tentative(s)</span>
                  )}
                  <span>{new Date(job.cree_le).toLocaleString()}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

const TOUTES_RESSOURCES = "_toutes";

// Charge des ressources d'une instance, sur son dernier planning réussi —
// PRISME n'a pas de calendrier d'atelier unique partagé entre instances (les
// jours d'un planning sont relatifs à l'instance, jamais des dates
// calendaires), donc une instance à la fois plutôt qu'une vue agrégée.
function OngletChargeRessources() {
  const { data: instances, isLoading: instancesLoading } = useInstances();
  const { data: executions } = useExecutions();
  const labelParInstance = useLabelsInstances();
  const [instanceId, setInstanceId] = useState("");
  const [ressourceFiltre, setRessourceFiltre] = useState(TOUTES_RESSOURCES);
  const { data: instance, isLoading: instanceLoading } = useInstance(instanceId || null);

  const derniereExecution = [...(executions ?? [])]
    .filter((e) => e.instance_id === instanceId && e.reussi)
    .sort((a, b) => (b.date_execution ?? "").localeCompare(a.date_execution ?? ""))[0];

  const { data: planning, isLoading: planningLoading } = usePlanning(
    derniereExecution?.execution_id ?? null,
  );

  const instancesTriees = [...(instances ?? [])].sort((a, b) =>
    (labelParInstance.get(a.instance_id)?.label ?? a.instance_id).localeCompare(
      labelParInstance.get(b.instance_id)?.label ?? b.instance_id,
    ),
  );

  function changerInstance(id: string) {
    setInstanceId(id);
    setRessourceFiltre(TOUTES_RESSOURCES);
  }

  return (
    <div className="space-y-4">
      <div className="glass flex flex-wrap items-end gap-4 rounded-2xl p-4">
        <div className="space-y-1.5">
          <Label htmlFor="charge_instance" className="text-xs text-muted-foreground">
            Instance
          </Label>
          <Select value={instanceId} onValueChange={changerInstance}>
            <SelectTrigger id="charge_instance" className="w-72">
              <SelectValue
                placeholder={instancesLoading ? "Chargement..." : "Choisir une instance..."}
              />
            </SelectTrigger>
            <SelectContent>
              {instancesTriees.map((i) => (
                <SelectItem key={i.instance_id} value={i.instance_id}>
                  {labelParInstance.get(i.instance_id)?.label ?? i.instance_id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {instance && instance.ressources.length > 0 && (
          <div className="space-y-1.5">
            <Label htmlFor="charge_ressource" className="text-xs text-muted-foreground">
              Ressource
            </Label>
            <Select value={ressourceFiltre} onValueChange={setRessourceFiltre}>
              <SelectTrigger id="charge_ressource" className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={TOUTES_RESSOURCES}>Toutes les ressources</SelectItem>
                {instance.ressources.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>

      {!instanceId ? (
        <EmptyState
          icon={Boxes}
          title="Choisissez une instance"
          desc="La charge des ressources se calcule sur le dernier planning exécuté d'une instance, une à la fois — PRISME n'a pas de calendrier d'atelier unique partagé entre instances."
        />
      ) : instanceLoading || planningLoading ? (
        <p className="text-sm text-muted-foreground">Chargement...</p>
      ) : !derniereExecution ? (
        <EmptyState
          icon={Boxes}
          title="Aucun planning exécuté"
          desc="Cette instance n'a pas encore d'exécution réussie — lance-en une depuis Solveurs générés ou Données pour voir sa charge ici."
        />
      ) : instance && planning ? (
        <ContenuChargeRessources
          instance={instance}
          planning={planning}
          ressourceFiltre={ressourceFiltre}
        />
      ) : null}
    </div>
  );
}

function ContenuChargeRessources({
  instance,
  planning,
  ressourceFiltre,
}: {
  instance: InstanceDetail;
  planning: PlanningAvecDurees;
  ressourceFiltre: string;
}) {
  const operations = planning.operations.map((op) => ({
    ...op,
    fin: op.debut + (planning.durees[`${op.tache}|${op.ressource}`] ?? 0),
  }));
  const makespan = operations.length > 0 ? Math.max(...operations.map((op) => op.fin)) : 0;
  // Ancrage calendaire du dernier planning réussi — voir src/lib/dates-relatives.ts. Un fait
  // historique figé côté serveur (PlanningAvecDurees.date_execution), jamais "aujourd'hui".
  const ancrage = debutJour(new Date(planning.date_execution));

  if (makespan === 0) {
    return (
      <EmptyState
        icon={Boxes}
        title="Aucune opération planifiée"
        desc="Le dernier planning de cette instance ne contient aucune opération."
      />
    );
  }

  const ressourcesInstance = instance.ressources.map((r) => r.id);
  const ressourcesIncluses =
    ressourceFiltre === TOUTES_RESSOURCES ? ressourcesInstance : [ressourceFiltre];

  const parJour = chargeParJour(ressourcesIncluses, operations, instance.contraintes, makespan);
  const capaciteTotale = parJour.reduce((s, j) => s + j.capacite, 0);
  const chargeTotale = parJour.reduce((s, j) => s + j.charge, 0);
  const tauxCharge = capaciteTotale > 0 ? (chargeTotale / capaciteTotale) * 100 : 0;
  const ressourcesActives = new Set(operations.map((op) => op.ressource)).size;
  const maxBarre = Math.max(1, ...parJour.map((j) => Math.max(j.capacite, j.charge)));

  // Toujours sur l'instance entière, indépendamment du filtre ressource — le
  // filtre sert à zoomer sur une station dans les tuiles/le graphe ci-dessus,
  // ces deux sections comparent au contraire les stations entre elles.
  const retards = tachesEnRetard(operations, instance.contraintes);
  const detailRessources = chargeParRessource(
    ressourcesInstance,
    operations,
    instance.contraintes,
    makespan,
  ).sort((a, b) => b.taux - a.taux);

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <KpiTile
          label="Capacité"
          valeur={formatDuree(capaciteTotale, instance.unite_duree)}
          detail={ressourceFiltre === TOUTES_RESSOURCES ? "toutes ressources" : ressourceFiltre}
        />
        <KpiTile
          label="Charge"
          valeur={formatDuree(chargeTotale, instance.unite_duree)}
          detail={ressourceFiltre === TOUTES_RESSOURCES ? "toutes ressources" : ressourceFiltre}
        />
        <KpiTile
          label="Taux de charge"
          valeur={`${tauxCharge.toFixed(0)}%`}
          detail={ressourceFiltre === TOUTES_RESSOURCES ? "toutes ressources" : ressourceFiltre}
        />
        <KpiTile
          label="Tâches planifiées"
          valeur={`${planning.operations.length}/${instance.taches.length}`}
          detail="sur cette instance"
        />
        <KpiTile
          label="Ressources actives"
          valeur={`${ressourcesActives}/${instance.ressources.length}`}
          detail="avec ≥1 opération"
        />
      </div>

      <div className="glass mt-6 rounded-2xl p-6">
        <div className="mb-4 text-sm font-semibold">
          Charge par jour{ressourceFiltre !== TOUTES_RESSOURCES ? ` — ${ressourceFiltre}` : ""}
        </div>
        <div className="flex items-end gap-2 overflow-x-auto pb-2">
          {parJour.map((j) => (
            <div key={j.jour} className="flex shrink-0 flex-col items-center gap-1.5">
              <div className="flex h-36 items-end gap-1">
                <div
                  className="w-4 rounded-t bg-muted"
                  style={{ height: `${(j.capacite / maxBarre) * 100}%` }}
                  title={`Capacité : ${formatDuree(j.capacite, instance.unite_duree)}`}
                />
                <div
                  className="w-4 rounded-t bg-gradient-to-t from-primary to-accent"
                  style={{ height: `${(j.charge / maxBarre) * 100}%` }}
                  title={`Charge : ${formatDuree(j.charge, instance.unite_duree)}`}
                />
              </div>
              <span className="text-[10px] text-muted-foreground">
                {formatDateRelative(j.jour, ancrage)}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-muted" /> Capacité
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-gradient-to-r from-primary to-accent" />{" "}
            Charge
          </span>
        </div>
      </div>

      <div className="glass mt-6 rounded-2xl p-6">
        <div className="mb-4 text-sm font-semibold">Tâches en retard</div>
        {retards.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Aucune tâche en retard — toutes les échéances déclarées sont respectées par ce planning.
          </p>
        ) : (
          <ul className="space-y-2">
            {retards.map((r) => (
              <li
                key={r.tache}
                className="flex items-center justify-between rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm"
              >
                <span className="flex items-center gap-2 font-medium text-destructive">
                  <AlertTriangle className="h-4 w-4 shrink-0" /> {r.tache}
                </span>
                <span className="text-xs text-muted-foreground">
                  fin le {formatDateRelative(r.fin, ancrage)} · échéance le{" "}
                  {formatDateRelative(r.echeance, ancrage)} · retard de{" "}
                  {formatDuree(r.retard, instance.unite_duree)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="glass mt-6 overflow-hidden rounded-2xl">
        <div className="border-b border-border/50 px-5 py-3 text-sm font-semibold">
          Détail par ressource — goulots d'étranglement &amp; capacité disponible
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Ressource</TableHead>
              <TableHead>Capacité</TableHead>
              <TableHead>Charge</TableHead>
              <TableHead>Disponible</TableHead>
              <TableHead>Taux de charge</TableHead>
              <TableHead />
            </TableRow>
          </TableHeader>
          <TableBody>
            {detailRessources.map((r) => (
              <TableRow key={r.ressource}>
                <TableCell className="font-mono text-xs">{r.ressource}</TableCell>
                <TableCell>{formatDuree(r.capacite, instance.unite_duree)}</TableCell>
                <TableCell>{formatDuree(r.charge, instance.unite_duree)}</TableCell>
                <TableCell>{formatDuree(r.disponible, instance.unite_duree)}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <div className="h-1.5 w-24 rounded bg-muted/30">
                      <div
                        className={`h-full rounded ${
                          r.taux >= SEUIL_GOULOT
                            ? "bg-destructive"
                            : "bg-gradient-to-r from-primary to-accent"
                        }`}
                        style={{ width: `${r.taux}%` }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">{r.taux.toFixed(0)}%</span>
                  </div>
                </TableCell>
                <TableCell>
                  {r.taux >= SEUIL_GOULOT && (
                    <Badge variant="destructive" className="gap-1">
                      <AlertTriangle className="h-3 w-3" /> Goulot
                    </Badge>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </>
  );
}

import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, EmptyState } from "@/components/app-page";
import { BarChart3, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  useJobsGeneration,
  useSolveurs,
  useLabelsInstances,
  useStatistiquesGeneration,
  type JobGenerationInfo,
} from "@/integrations/prisme";

const TOUS_LES_AGENTS = "tous";

export const Route = createFileRoute("/_authenticated/analytics")({
  head: () => ({ meta: [{ title: "Analytique — PRISME" }] }),
  component: AnalyticsPage,
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
      if (evenement.statut === "en_cours") continue; // ne compter qu'un évènement terminal par étape
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

function AnalyticsPage() {
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
      <PageHeader
        title="Analytique"
        desc="Activité réelle du pipeline multi-agents de génération de solveurs — quels agents tournent, lesquels échouent, et à quelle fréquence, sur toutes les générations lancées depuis le dernier redémarrage du serveur."
      />

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

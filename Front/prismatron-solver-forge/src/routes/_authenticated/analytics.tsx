import { createFileRoute } from "@tanstack/react-router";
import { PageHeader, EmptyState } from "@/components/app-page";
import { BarChart3, CheckCircle2, Loader2, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  useJobsGeneration,
  useSolveurs,
  useLabelsInstances,
  type JobGenerationInfo,
} from "@/integrations/prisme";

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

function AnalyticsPage() {
  const { data: jobs, isLoading } = useJobsGeneration();
  const { data: solveurs } = useSolveurs();
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
  const maxTotal = Math.max(1, ...statsAgents.map((s) => s.total));

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
        <div className="mb-1 text-sm font-semibold">Activité par agent</div>
        <p className="mb-4 text-xs text-muted-foreground">
          Nombre de passages par agent (toutes tentatives confondues) et proportion en échec, sur
          toutes les générations connues du serveur.
        </p>

        {!isLoading && statsAgents.length === 0 && (
          <EmptyState
            icon={BarChart3}
            title="Aucune génération pour l'instant"
            desc="Lance une génération depuis la page Générateur de solveurs pour voir l'activité des agents ici."
          />
        )}

        <div className="space-y-2.5">
          {statsAgents.map((s) => {
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
                  <span>{labelParInstance.get(job.instance_id) ?? job.instance_id}</span>
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

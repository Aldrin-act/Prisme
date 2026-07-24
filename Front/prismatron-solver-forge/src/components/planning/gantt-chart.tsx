import type { PlanningAvecDurees } from "@/integrations/prisme";

// Ni `fin` ni `makespan` n'existent sur le fil (`dsl/schema/planning.py` est
// volontairement permissif) — `fin` se déduit de `debut + durees["tache|ressource"]`.
function operationsAvecFin(planning: PlanningAvecDurees) {
  return planning.operations.map((op) => ({
    ...op,
    fin: op.debut + (planning.durees[`${op.tache}|${op.ressource}`] ?? 0),
  }));
}

export function GanttChart({ planning }: { planning: PlanningAvecDurees }) {
  const operations = operationsAvecFin(planning);
  const makespan = operations.length > 0 ? Math.max(...operations.map((op) => op.fin)) : 0;

  if (operations.length === 0 || makespan === 0) {
    return <p className="text-sm text-muted-foreground">Aucune opération planifiée.</p>;
  }

  const parRessource = new Map<string, typeof operations>();
  for (const op of operations) {
    const liste = parRessource.get(op.ressource) ?? [];
    liste.push(op);
    parRessource.set(op.ressource, liste);
  }
  for (const liste of parRessource.values()) {
    liste.sort((a, b) => a.debut - b.debut);
  }
  const ressources = [...parRessource.keys()].sort();

  const graduations = [0, 0.25, 0.5, 0.75, 1].map((f) => Math.round(makespan * f));

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[32rem]">
        <div className="mb-1 flex pl-32 text-[10px] text-muted-foreground">
          {graduations.map((g, i) => (
            <span key={i} className="flex-1 text-center first:text-left last:text-right">
              {g}
            </span>
          ))}
        </div>
        <div className="space-y-1.5">
          {ressources.map((ressource) => (
            <div key={ressource} className="flex items-center gap-2">
              <div
                className="w-32 shrink-0 truncate font-mono text-xs text-muted-foreground"
                title={ressource}
              >
                {ressource}
              </div>
              <div className="relative h-7 flex-1 rounded bg-muted/30">
                {(parRessource.get(ressource) ?? []).map((op, i) => {
                  const gauche = (op.debut / makespan) * 100;
                  const largeur = ((op.fin - op.debut) / makespan) * 100;
                  return (
                    <div
                      key={i}
                      title={`${op.tache} : ${op.debut} → ${op.fin}`}
                      className="absolute top-0 flex h-full items-center justify-center overflow-hidden rounded bg-gradient-to-r from-primary to-accent px-1 text-[10px] font-medium text-primary-foreground"
                      style={{ left: `${gauche}%`, width: `${largeur}%` }}
                    >
                      <span className="truncate">{op.tache}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

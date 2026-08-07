import type { Contrainte, PlanningAvecDurees } from "@/integrations/prisme";

// Ni `fin` ni `makespan` n'existent sur le fil (`dsl/schema/planning.py` est
// volontairement permissif) — `fin` se déduit de `debut + durees["tache|ressource"]`.
function operationsAvecFin(planning: PlanningAvecDurees) {
  return planning.operations.map((op) => ({
    ...op,
    fin: op.debut + (planning.durees[`${op.tache}|${op.ressource}`] ?? 0),
  }));
}

// Taux d'utilisation conscient de la capacité et de la disponibilité — pas
// une simple charge/makespan, qui sous-estimerait une ressource à capacité
// > 1 et surestimerait une ressource avec des jours indisponibles déclarés.
function tauxUtilisation(
  ressource: string,
  operations: { debut: number; fin: number }[],
  makespan: number,
  contraintes: Contrainte[],
): number {
  const capacite =
    contraintes.find(
      (c): c is Contrainte & { type: "capacite" } =>
        c.type === "capacite" && c.ressource === ressource,
    )?.capacite ?? 1;
  const joursIndisponibles = new Set(
    contraintes.find(
      (c): c is Contrainte & { type: "disponibilite_ressource" } =>
        c.type === "disponibilite_ressource" && c.ressource === ressource,
    )?.jours_indisponibles ?? [],
  );
  let joursDisponibles = 0;
  for (let jour = 0; jour < makespan; jour++) {
    if (!joursIndisponibles.has(jour)) joursDisponibles++;
  }
  const capaciteTotale = capacite * joursDisponibles;
  if (capaciteTotale === 0) return 0;
  const charge = operations.reduce((somme, op) => somme + (op.fin - op.debut), 0);
  return Math.min(100, (charge / capaciteTotale) * 100);
}

export function GanttChart({
  planning,
  contraintes,
}: {
  planning: PlanningAvecDurees;
  // Optionnelle : sans elle, la colonne taux d'utilisation ne s'affiche
  // simplement pas plutôt que d'afficher un chiffre faux.
  contraintes?: Contrainte[];
}) {
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
      <div className="min-w-160">
        <div className="mb-1 flex pl-36 text-xs text-muted-foreground">
          {graduations.map((g, i) => (
            <span key={i} className="flex-1 text-center first:text-left last:text-right">
              {g}
            </span>
          ))}
        </div>
        <div className="space-y-2.5">
          {ressources.map((ressource) => {
            const operationsRessource = parRessource.get(ressource) ?? [];
            const taux = contraintes
              ? tauxUtilisation(ressource, operationsRessource, makespan, contraintes)
              : null;
            return (
              <div key={ressource} className="flex items-center gap-3">
                <div
                  className="w-36 shrink-0 truncate font-mono text-xs text-muted-foreground"
                  title={ressource}
                >
                  {ressource}
                </div>
                <div className="relative h-10 flex-1 rounded bg-muted/30">
                  {operationsRessource.map((op, i) => {
                    const gauche = (op.debut / makespan) * 100;
                    const largeur = ((op.fin - op.debut) / makespan) * 100;
                    return (
                      <div
                        key={i}
                        title={`${op.tache} : ${op.debut} → ${op.fin}`}
                        className="absolute top-0 flex h-full items-center justify-center overflow-hidden rounded bg-gradient-to-r from-primary to-accent px-1.5 text-xs font-medium text-primary-foreground"
                        style={{ left: `${gauche}%`, width: `${largeur}%` }}
                      >
                        <span className="truncate">{op.tache}</span>
                      </div>
                    );
                  })}
                </div>
                {taux !== null && (
                  <div className="flex w-24 shrink-0 items-center gap-1.5">
                    <div className="h-1.5 flex-1 rounded bg-muted/30">
                      <div
                        className="h-full rounded bg-gradient-to-r from-primary to-accent"
                        style={{ width: `${taux}%` }}
                      />
                    </div>
                    <span className="w-8 shrink-0 text-right text-[10px] text-muted-foreground">
                      {taux.toFixed(0)}%
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, RotateCcw, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  prismeKeys,
  useAjusterPlanning,
  type Contrainte,
  type OperationPlanifiee,
  type PlanningAvecDurees,
} from "@/integrations/prisme";
import { tachesEnRetard, tauxUtilisationRessource } from "@/lib/charge-ressources";
import { formatDureeCourte } from "@/lib/unite-duree";

function cle(op: { tache: string; ressource: string }): string {
  return `${op.tache}|${op.ressource}`;
}

// Ni `fin` ni `makespan` n'existent sur le fil (`dsl/schema/planning.py` est
// volontairement permissif) — `fin` se déduit de `debut + durees["tache|ressource"]`.
function operationsAvecFin(operations: OperationPlanifiee[], durees: Record<string, number>) {
  return operations.map((op) => ({ ...op, fin: op.debut + (durees[cle(op)] ?? 0) }));
}

interface EtatDrag {
  cle: string;
  xDepart: number;
  debutDepart: number;
  largeurPistePx: number;
  makespanDepart: number;
}

export function GanttChart({
  planning,
  contraintes,
  editable = false,
  executionId,
  onAjustementReussi,
  uniteDuree,
}: {
  planning: PlanningAvecDurees;
  // Optionnelle : sans elle, la colonne taux d'utilisation ne s'affiche
  // simplement pas plutôt que d'afficher un chiffre faux.
  contraintes?: Contrainte[];
  // Gantt interactif (Phase 3) : glisser une barre change son jour de début (jamais sa
  // ressource — contraint à l'axe horizontal de sa propre ligne). `executionId` requis pour
  // pouvoir soumettre l'ajustement ; sans lui, `editable` reste sans effet.
  editable?: boolean;
  executionId?: string;
  onAjustementReussi?: (planning: PlanningAvecDurees) => void;
  // Unité d'affichage (voir src/lib/unite-duree.ts) — "jours" implicite si
  // absent. Ne change jamais le positionnement des barres (calculé en jours
  // bruts), seulement le texte affiché (graduations, tooltips).
  uniteDuree?: string | null;
}) {
  const queryClient = useQueryClient();
  const ajuster = useAjusterPlanning();
  const [operationsLocales, setOperationsLocales] = useState(planning.operations);
  const [drag, setDrag] = useState<EtatDrag | null>(null);

  // Toute nouvelle version du planning affiché (nouvelle exécution, bascule
  // original/ajusté...) réinitialise l'édition en cours — jamais un mélange
  // entre deux plannings différents. `ajuster` exclu volontairement : son
  // identité change à chaque mutation, la réintégrer redéclencherait cet
  // effet et effacerait l'édition en cours pile au moment d'afficher un
  // refus (violations).
  useEffect(() => {
    setOperationsLocales(planning.operations);
    ajuster.reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planning]);

  const peutEditer = editable && !!executionId;
  const operations = operationsAvecFin(operationsLocales, planning.durees);
  const makespan = operations.length > 0 ? Math.max(...operations.map((op) => op.fin)) : 0;
  // Recalculé sur `operationsLocales` (pas `planning.operations`) : glisser une barre au-delà de
  // son échéance la fait passer au rouge immédiatement, avant même d'enregistrer l'ajustement —
  // "voir tout de suite l'effet d'un changement".
  const tachesEnRetardIds = new Set(
    (contraintes ? tachesEnRetard(operations, contraintes) : []).map((r) => r.tache),
  );
  const estModifie = JSON.stringify(operationsLocales) !== JSON.stringify(planning.operations);
  const clesModifiees = new Set(
    operationsLocales
      .filter((op, i) => op.debut !== planning.operations[i]?.debut)
      .map((op) => cle(op)),
  );

  function reinitialiser() {
    setOperationsLocales(planning.operations);
    ajuster.reset();
  }

  function enregistrer() {
    if (!executionId) return;
    ajuster.mutate(
      { executionId, planning: { operations: operationsLocales } },
      {
        onSuccess: (reponse) => {
          if (reponse.legal && reponse.planning) {
            queryClient.invalidateQueries({ queryKey: prismeKeys.planningAjuste(executionId) });
            onAjustementReussi?.(reponse.planning);
          }
        },
      },
    );
  }

  function onPointerDownBarre(
    e: React.PointerEvent<HTMLDivElement>,
    cleOp: string,
    debutActuel: number,
  ) {
    if (!peutEditer) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const piste = e.currentTarget.parentElement;
    if (!piste) return;
    setDrag({
      cle: cleOp,
      xDepart: e.clientX,
      debutDepart: debutActuel,
      largeurPistePx: piste.getBoundingClientRect().width,
      makespanDepart: makespan,
    });
  }

  function onPointerMoveBarre(e: React.PointerEvent<HTMLDivElement>) {
    if (!drag || drag.largeurPistePx === 0 || drag.makespanDepart === 0) return;
    const deltaJours = Math.round(
      ((e.clientX - drag.xDepart) / drag.largeurPistePx) * drag.makespanDepart,
    );
    const nouveauDebut = Math.max(0, drag.debutDepart + deltaJours);
    setOperationsLocales((ops) =>
      ops.map((op) => (cle(op) === drag.cle ? { ...op, debut: nouveauDebut } : op)),
    );
  }

  function onPointerUpBarre() {
    setDrag(null);
  }

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
  const violations = ajuster.data && !ajuster.data.legal ? ajuster.data.violations : [];

  return (
    <div className="space-y-3">
      {peutEditer && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            Glisse une barre pour changer son jour de début — proposition revalidée avant tout
            enregistrement, jamais appliquée silencieusement.
          </p>
          {estModifie && (
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={reinitialiser}
                disabled={ajuster.isPending}
              >
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" /> Réinitialiser
              </Button>
              <Button size="sm" onClick={enregistrer} disabled={ajuster.isPending}>
                <Save className="mr-1.5 h-3.5 w-3.5" />
                {ajuster.isPending ? "Validation..." : "Enregistrer l'ajustement"}
              </Button>
            </div>
          )}
        </div>
      )}

      {violations.length > 0 && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <div className="flex items-center gap-2 font-medium">
            <AlertCircle className="h-4 w-4" /> Ajustement illégal — rien n'a été enregistré
          </div>
          <ul className="mt-1.5 list-disc space-y-1 pl-5">
            {violations.map((v, i) => (
              <li key={i}>{v.message}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="overflow-x-auto">
        <div className="min-w-160">
          <div className="mb-1 flex pl-36 text-xs text-muted-foreground">
            {graduations.map((g, i) => (
              <span key={i} className="flex-1 text-center first:text-left last:text-right">
                {formatDureeCourte(g, uniteDuree)}
              </span>
            ))}
          </div>
          <div className="space-y-2.5">
            {ressources.map((ressource) => {
              const operationsRessource = parRessource.get(ressource) ?? [];
              const taux = contraintes
                ? tauxUtilisationRessource(ressource, operationsRessource, makespan, contraintes)
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
                    {operationsRessource.map((op) => {
                      const gauche = (op.debut / makespan) * 100;
                      const largeur = ((op.fin - op.debut) / makespan) * 100;
                      const cleOp = cle(op);
                      const enRetard = tachesEnRetardIds.has(op.tache);
                      return (
                        <div
                          key={cleOp}
                          title={`${op.tache} : ${formatDureeCourte(op.debut, uniteDuree)} → ${formatDureeCourte(
                            op.fin,
                            uniteDuree,
                          )}${enRetard ? " (en retard)" : ""}`}
                          onPointerDown={(e) => onPointerDownBarre(e, cleOp, op.debut)}
                          onPointerMove={onPointerMoveBarre}
                          onPointerUp={onPointerUpBarre}
                          className={`absolute top-0 flex h-full items-center justify-center overflow-hidden rounded px-1.5 text-xs font-medium text-primary-foreground ${
                            enRetard ? "bg-destructive" : "bg-gradient-to-r from-primary to-accent"
                          } ${peutEditer ? "cursor-grab touch-none active:cursor-grabbing" : ""} ${
                            clesModifiees.has(cleOp) ? "ring-2 ring-yellow-400" : ""
                          }`}
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
    </div>
  );
}

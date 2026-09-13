import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, RotateCcw, Save, ZoomIn, ZoomOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  prismeKeys,
  useAjusterPlanning,
  type Contrainte,
  type OperationPlanifiee,
  type PlanningAvecDurees,
  type StatutCommande,
  type Tache,
} from "@/integrations/prisme";
import { tachesEnRetard, tauxUtilisationRessource } from "@/lib/charge-ressources";
import {
  dateDepuisAncrage,
  debutJour,
  formatDateRelative,
  type UniteTemps,
} from "@/lib/dates-relatives";

function cle(op: { tache: string; ressource: string }): string {
  return `${op.tache}|${op.ressource}`;
}

// Samedi/dimanche marqués non ouvrés sur le Gantt — purement visuel, ancré sur la même date que
// les graduations ; le DSL/solveur ne connaît aucune notion de jour ouvré (voir
// `ContrainteDisponibiliteRessource.jours_semaine_indisponibles` pour la vraie contrainte de
// planification, une notion distincte de cet affichage). Segments consécutifs (jours en mode
// jours, heures en mode heures) fusionnés en un seul, pour un rendu propre sans trait de jointure.
function segmentsWeekEnd(
  makespan: number,
  ancrage: Date,
  unite: UniteTemps,
): { debut: number; fin: number }[] {
  const segments: { debut: number; fin: number }[] = [];
  let debutCourant: number | null = null;
  for (let instant = 0; instant < makespan; instant++) {
    const weekEnd = [0, 6].includes(dateDepuisAncrage(instant, ancrage, unite).getDay());
    if (weekEnd && debutCourant === null) {
      debutCourant = instant;
    } else if (!weekEnd && debutCourant !== null) {
      segments.push({ debut: debutCourant, fin: instant });
      debutCourant = null;
    }
  }
  if (debutCourant !== null) segments.push({ debut: debutCourant, fin: makespan });
  return segments;
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
}

// Échelle fixe en pixels/unité (plutôt qu'un % de la durée totale) — une unité vaut un jour ou
// une heure selon `InstanceTRCO.unite_temps` (voir `uniteDuree` ci-dessous) : le DSL ne connaît
// que des entiers dans l'unité déclarée, jamais une précision plus fine. Constantes plus
// resserrées en mode heures : un planning de même durée réelle y compte ~24x plus d'unités.
const ECHELLE_PAR_UNITE: Record<
  UniteTemps,
  { defaut: number; min: number; max: number; pas: number }
> = {
  jours: { defaut: 48, min: 16, max: 160, pas: 16 },
  heures: { defaut: 8, min: 2, max: 48, pas: 2 },
};
const LARGEUR_COL_RESSOURCE = 144; // == w-36, dupliqué en px pour aligner l'offset de l'en-tête

export function GanttChart({
  planning,
  contraintes,
  taches,
  commandes,
  uniteDuree,
  editable = false,
  executionId,
  onAjustementReussi,
}: {
  planning: PlanningAvecDurees;
  // Optionnelle : sans elle, la colonne taux d'utilisation ne s'affiche
  // simplement pas plutôt que d'afficher un chiffre faux.
  contraintes?: Contrainte[];
  // Optionnelle : sans elle, les barres n'affichent que l'identifiant de tâche (pas de produit).
  taches?: Tache[];
  // Optionnelle : sans elle, aucune commande n'est affichée sur les barres ni d'échéance
  // marquée sur l'axe (voir GET /ingestion/{instance_id}/commandes). `date_limite` est sur le
  // même référentiel que `op.debut`/`op.fin` — comparable et positionnable directement sur cet
  // axe, aucune conversion nécessaire.
  commandes?: StatutCommande[];
  // "heures" bascule l'ancrage/l'échelle/le libellé des barres sur une précision horaire —
  // toute autre valeur (dont absente/null, l'instance n'a jamais été en mode heures) reste
  // "jours", comportement historique inchangé.
  uniteDuree?: string | null;
  // Gantt interactif (Phase 3) : glisser une barre change son instant de début (jamais sa
  // ressource — contraint à l'axe horizontal de sa propre ligne). `executionId` requis pour
  // pouvoir soumettre l'ajustement ; sans lui, `editable` reste sans effet.
  editable?: boolean;
  executionId?: string;
  onAjustementReussi?: (planning: PlanningAvecDurees) => void;
}) {
  const queryClient = useQueryClient();
  const ajuster = useAjusterPlanning();
  const unite: UniteTemps = uniteDuree === "heures" ? "heures" : "jours";
  const echelle = ECHELLE_PAR_UNITE[unite];
  // Instant 0 ancré sur la date réelle de l'exécution. Normalisé à minuit local en mode jours
  // (l'arithmétique "+N jours" reste exacte quelle que soit l'heure à laquelle le solveur a
  // tourné) ; gardé à sa précision complète en mode heures (l'heure exacte de l'exécution EST
  // l'ancrage, la tronquer perdrait l'information que l'unité existe justement pour capturer).
  const ancrage =
    unite === "heures"
      ? new Date(planning.date_execution)
      : debutJour(new Date(planning.date_execution));
  const formatAxe = (instant: number) => formatDateRelative(instant, ancrage, unite);
  const [operationsLocales, setOperationsLocales] = useState(planning.operations);
  const [drag, setDrag] = useState<EtatDrag | null>(null);
  const [pxParJour, setPxParJour] = useState(echelle.defaut);

  // Toute nouvelle version du planning affiché (nouvelle exécution, bascule
  // original/ajusté...) réinitialise l'édition en cours et le zoom — jamais un mélange
  // entre deux plannings différents. `ajuster` exclu volontairement : son
  // identité change à chaque mutation, la réintégrer redéclencherait cet
  // effet et effacerait l'édition en cours pile au moment d'afficher un
  // refus (violations).
  useEffect(() => {
    setOperationsLocales(planning.operations);
    setPxParJour(echelle.defaut);
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
  const produitParTache = new Map((taches ?? []).map((t) => [t.id, t.produit]));

  const commandesParTache = new Map<string, StatutCommande[]>();
  const commandesParEcheance = new Map<number, StatutCommande[]>();
  for (const commande of commandes ?? []) {
    for (const tache of commande.taches) {
      commandesParTache.set(tache, [...(commandesParTache.get(tache) ?? []), commande]);
    }
    if (commande.date_limite !== null) {
      commandesParEcheance.set(commande.date_limite, [
        ...(commandesParEcheance.get(commande.date_limite) ?? []),
        commande,
      ]);
    }
  }

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
    setDrag({ cle: cleOp, xDepart: e.clientX, debutDepart: debutActuel });
  }

  // Échelle fixe (pxParJour) : le delta en jours ne dépend plus de la largeur de la piste, une
  // simple division par l'échelle courante suffit (et reste correcte si le zoom change en cours
  // de glissement, relu à chaque évènement plutôt que figé au pointerdown).
  function onPointerMoveBarre(e: React.PointerEvent<HTMLDivElement>) {
    if (!drag) return;
    const deltaJours = Math.round((e.clientX - drag.xDepart) / pxParJour);
    const nouveauDebut = Math.max(0, drag.debutDepart + deltaJours);
    setOperationsLocales((ops) =>
      ops.map((op) => (cle(op) === drag.cle ? { ...op, debut: nouveauDebut } : op)),
    );
  }

  function onPointerUpBarre() {
    setDrag(null);
  }

  function zoomer(sens: 1 | -1) {
    setPxParJour((p) => Math.min(echelle.max, Math.max(echelle.min, p + sens * echelle.pas)));
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

  const jours = Array.from({ length: makespan }, (_, i) => i);
  const weekEnds = segmentsWeekEnd(makespan, ancrage, unite);
  const violations = ajuster.data && !ajuster.data.legal ? ajuster.data.violations : [];

  // Position (généralement fractionnaire) de l'instant présent sur l'axe du planning — masquée
  // si "maintenant" tombe hors de la plage affichée (planning entièrement passé, ou futur
  // au-delà de son propre horizon).
  const msParUnite = unite === "heures" ? 3_600_000 : 86_400_000;
  const joursDepuisAncrage = (Date.now() - ancrage.getTime()) / msParUnite;
  const afficherMaintenant = joursDepuisAncrage >= 0 && joursDepuisAncrage <= makespan;

  return (
    <div className="space-y-3">
      {peutEditer && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            Glisse une barre pour changer son instant de début — proposition revalidée avant tout
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

      <div className="flex flex-wrap items-center justify-between gap-2 text-[10px] text-muted-foreground">
        <div className="flex flex-wrap items-center gap-3">
          {weekEnds.length > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-2.5 rounded-sm bg-foreground/10" />
              Jours non ouvrés (samedi, dimanche)
            </div>
          )}
          {afficherMaintenant && (
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-0.5 bg-blue-500" />
              Aujourd'hui
            </div>
          )}
          {commandesParEcheance.size > 0 && (
            <div className="flex items-center gap-1.5">
              <span className="inline-block h-2.5 w-0.5 border-l-2 border-dashed border-amber-500" />
              Échéance commande
            </div>
          )}
        </div>
        <div className="flex items-center gap-1">
          <Button
            size="icon"
            variant="outline"
            className="h-6 w-6"
            onClick={() => zoomer(-1)}
            disabled={pxParJour <= echelle.min}
            aria-label="Réduire le zoom"
          >
            <ZoomOut className="h-3 w-3" />
          </Button>
          <span className="w-12 text-center font-mono">
            {pxParJour}px/{unite === "heures" ? "h" : "j"}
          </span>
          <Button
            size="icon"
            variant="outline"
            className="h-6 w-6"
            onClick={() => zoomer(1)}
            disabled={pxParJour >= echelle.max}
            aria-label="Augmenter le zoom"
          >
            <ZoomIn className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {(commandes ?? []).length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted-foreground">Commandes :</span>
          {(commandes ?? []).map((c) => (
            <span
              key={c.commande_id}
              className="rounded-md border border-border/50 bg-muted/30 px-1.5 py-0.5 font-mono text-[10px]"
              title={`${c.taches.length} tâche${c.taches.length > 1 ? "s" : ""} : ${c.taches.join(", ")}`}
            >
              {c.commande_id}
            </span>
          ))}
        </div>
      )}

      <div className="overflow-x-auto">
        <div>
          <div
            className="mb-1 flex text-xs text-muted-foreground"
            style={{ paddingLeft: LARGEUR_COL_RESSOURCE + 12 }}
          >
            {jours.map((j) => (
              <div
                key={j}
                className="shrink-0 truncate border-r border-border/40 px-1 text-center first:border-l"
                style={{ width: pxParJour }}
              >
                {formatAxe(j)}
              </div>
            ))}
          </div>
          <div className="space-y-2.5">
            {ressources.map((ressource) => {
              const operationsRessource = parRessource.get(ressource) ?? [];
              const taux = contraintes
                ? tauxUtilisationRessource(ressource, operationsRessource, makespan, contraintes)
                : null;
              const largeurPiste = makespan * pxParJour;
              return (
                <div key={ressource} className="flex items-center gap-3">
                  <div
                    className="shrink-0 truncate font-mono text-xs text-muted-foreground"
                    style={{ width: LARGEUR_COL_RESSOURCE }}
                    title={ressource}
                  >
                    {ressource}
                  </div>
                  <div
                    className="relative h-10 shrink-0 overflow-hidden rounded bg-muted/30"
                    style={{ width: largeurPiste }}
                  >
                    {jours.map((j) => (
                      <div
                        key={j}
                        className="absolute top-0 h-full w-px bg-border/40"
                        style={{ left: j * pxParJour }}
                      />
                    ))}
                    {weekEnds.map((w, i) => (
                      <div
                        key={i}
                        className="absolute top-0 h-full bg-foreground/10"
                        style={{
                          left: w.debut * pxParJour,
                          width: (w.fin - w.debut) * pxParJour,
                        }}
                        title="Non ouvré (week-end)"
                      />
                    ))}
                    {afficherMaintenant && (
                      <div
                        className="absolute top-0 z-10 h-full w-0.5 bg-blue-500"
                        style={{ left: joursDepuisAncrage * pxParJour }}
                        title="Aujourd'hui"
                      />
                    )}
                    {[...commandesParEcheance.entries()].map(([jourEcheance, cmds]) => (
                      <div
                        key={jourEcheance}
                        className="absolute top-0 z-10 h-full w-0.5 border-l-2 border-dashed border-amber-500"
                        style={{ left: jourEcheance * pxParJour }}
                        title={`Échéance (${formatAxe(jourEcheance)}) : ${cmds
                          .map((c) => c.commande_id)
                          .join(", ")}`}
                      />
                    ))}
                    {operationsRessource.map((op) => {
                      const cleOp = cle(op);
                      const enRetard = tachesEnRetardIds.has(op.tache);
                      const duree = op.fin - op.debut;
                      const produit = produitParTache.get(op.tache);
                      const commandesTache = commandesParTache.get(op.tache) ?? [];
                      const libelleCommandes =
                        commandesTache.length === 1
                          ? ` · ${commandesTache[0].commande_id}`
                          : commandesTache.length > 1
                            ? ` · ${commandesTache.length} commandes`
                            : "";
                      return (
                        <div
                          key={cleOp}
                          title={`${op.tache} : ${formatAxe(op.debut)} → ${formatAxe(op.fin)}${
                            enRetard ? " (en retard)" : ""
                          }${
                            commandesTache.length > 0
                              ? ` — commande(s) : ${commandesTache.map((c) => c.commande_id).join(", ")}`
                              : ""
                          }`}
                          onPointerDown={(e) => onPointerDownBarre(e, cleOp, op.debut)}
                          onPointerMove={onPointerMoveBarre}
                          onPointerUp={onPointerUpBarre}
                          className={`absolute top-0 flex h-full items-center overflow-hidden rounded px-1.5 text-xs font-medium text-primary-foreground ${
                            enRetard ? "bg-destructive" : "bg-gradient-to-r from-primary to-accent"
                          } ${peutEditer ? "cursor-grab touch-none active:cursor-grabbing" : ""} ${
                            clesModifiees.has(cleOp) ? "ring-2 ring-yellow-400" : ""
                          }`}
                          style={{ left: op.debut * pxParJour, width: duree * pxParJour }}
                        >
                          <span className="truncate">
                            {op.tache} ({duree}
                            {unite === "heures" ? "h" : "j"}){produit ? ` ${produit}` : ""}
                            {libelleCommandes}
                          </span>
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

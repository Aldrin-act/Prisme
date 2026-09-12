import { Calendar, dateFnsLocalizer, type Event as EvenementRBC } from "react-big-calendar";
import { format, getDay, parse, startOfWeek } from "date-fns";
import { fr } from "date-fns/locale";
import "react-big-calendar/lib/css/react-big-calendar.css";
import {
  type Contrainte,
  type PlanningAvecDurees,
  type StatutCommande,
  type Tache,
} from "@/integrations/prisme";
import { tachesEnRetard } from "@/lib/charge-ressources";
import { dateDepuisAncrage, debutJour } from "@/lib/dates-relatives";

const COULEUR_A_TEMPS = "#4f46e5"; // indigo-600, cohérent avec le dégradé primary/accent du Gantt fait main
const COULEUR_EN_RETARD = "#dc2626"; // red-600, même sémantique que la barre rouge du Gantt fait main
const COULEUR_ECHEANCE = "#f59e0b"; // amber-500, même sémantique que le repère pointillé du Gantt fait main

const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: (date: Date) => startOfWeek(date, { locale: fr }),
  getDay,
  locales: { fr },
});

function cle(op: { tache: string; ressource: string }): string {
  return `${op.tache}|${op.ressource}`;
}

// Un événement de tâche (coloré selon retard) ou un événement d'échéance de commande (fond ambre,
// distingué via `estEcheance`) — `resource` de `Event` (react-big-calendar) volontairement inutilisé
// ici : réservé à une éventuelle vue multi-ressources future, jamais réutilisé pour du métadonnée.
interface EvenementPlanning extends EvenementRBC {
  id: string;
  enRetard?: boolean;
  estEcheance?: boolean;
}

// Vue calendrier (react-big-calendar, gratuite, MIT — aucune fonctionnalité "resource" premium
// requise) du même planning que `GanttChart` — une tâche par événement, positionné sur de vraies
// dates calendaires (`dateDepuisAncrage`, ancrées sur `planning.date_execution`, même référentiel
// que le reste de l'app). Toujours affichée, même vierge (`planning === null`) — jamais cachée
// derrière un clic.
export function PlanningCalendar({
  planning,
  contraintes,
  taches,
  commandes,
}: {
  planning: PlanningAvecDurees | null;
  // Optionnelle : sans elle, aucune tâche n'est marquée "en retard" (rouge).
  contraintes?: Contrainte[];
  // Optionnelle : sans elle, le libellé de l'événement n'affiche que tâche/ressource (pas de produit).
  taches?: Tache[];
  // Optionnelle : sans elle, aucune commande n'apparaît sur les événements ni d'échéance marquée.
  commandes?: StatutCommande[];
}) {
  const evenements: EvenementPlanning[] = [];
  // Ouvre le calendrier sur le mois du planning affiché plutôt que sur "aujourd'hui" — un
  // planning passé ou futur resterait sinon invisible tant qu'on n'a pas navigué manuellement.
  const dateParDefaut = planning ? debutJour(new Date(planning.date_execution)) : new Date();

  if (planning) {
    const ancrage = debutJour(new Date(planning.date_execution));
    const produitParTache = new Map((taches ?? []).map((t) => [t.id, t.produit]));

    const commandesParTache = new Map<string, StatutCommande[]>();
    for (const commande of commandes ?? []) {
      for (const t of commande.taches) {
        commandesParTache.set(t, [...(commandesParTache.get(t) ?? []), commande]);
      }
    }

    const operationsAvecFin = planning.operations.map((op) => ({
      ...op,
      fin: op.debut + (planning.durees[cle(op)] ?? 0),
    }));
    const tachesEnRetardIds = new Set(
      (contraintes ? tachesEnRetard(operationsAvecFin, contraintes) : []).map((r) => r.tache),
    );

    for (const op of operationsAvecFin) {
      const enRetard = tachesEnRetardIds.has(op.tache);
      const produit = produitParTache.get(op.tache);
      const commandesTache = commandesParTache.get(op.tache) ?? [];
      const libelleCommandes =
        commandesTache.length > 0
          ? ` · ${commandesTache.map((c) => c.commande_id).join(", ")}`
          : "";
      evenements.push({
        id: cle(op),
        title: `${op.tache} · ${op.ressource}${produit ? ` (${produit})` : ""}${libelleCommandes}`,
        start: dateDepuisAncrage(op.debut, ancrage),
        // Fin exclusive côté react-big-calendar pour un événement sur plusieurs jours pleins —
        // comportement standard "all-day event", pas une erreur de décalage.
        end: dateDepuisAncrage(op.fin, ancrage),
        allDay: true,
        enRetard,
      });
    }

    const echeancesVues = new Set<number>();
    for (const commande of commandes ?? []) {
      if (commande.date_limite === null || echeancesVues.has(commande.date_limite)) continue;
      echeancesVues.add(commande.date_limite);
      const commandesMemeEcheance = (commandes ?? []).filter(
        (c) => c.date_limite === commande.date_limite,
      );
      const jour = dateDepuisAncrage(commande.date_limite, ancrage);
      evenements.push({
        id: `echeance-${commande.date_limite}`,
        title: `Échéance : ${commandesMemeEcheance.map((c) => c.commande_id).join(", ")}`,
        start: jour,
        end: jour,
        allDay: true,
        estEcheance: true,
      });
    }
  }

  return (
    <div className="planning-calendar rounded-2xl border border-border/50 bg-card p-3">
      <Calendar
        localizer={localizer}
        culture="fr"
        events={evenements}
        views={["month", "week", "agenda"]}
        defaultView="month"
        defaultDate={dateParDefaut}
        style={{ height: 650 }}
        eventPropGetter={(event) => {
          const e = event as EvenementPlanning;
          return {
            style: {
              backgroundColor: e.estEcheance
                ? COULEUR_ECHEANCE
                : e.enRetard
                  ? COULEUR_EN_RETARD
                  : COULEUR_A_TEMPS,
            },
          };
        }}
        messages={{
          today: "Aujourd'hui",
          previous: "Précédent",
          next: "Suivant",
          month: "Mois",
          week: "Semaine",
          agenda: "Liste",
          date: "Date",
          time: "Heure",
          event: "Tâche",
          noEventsInRange: "Aucune tâche sur cette période.",
        }}
      />
      {!planning && (
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Aucun planning sélectionné pour l'instant — choisis une exécution ci-dessous.
        </p>
      )}
    </div>
  );
}

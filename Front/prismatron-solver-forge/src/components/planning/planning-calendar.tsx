import { useState } from "react";
import {
  Calendar,
  dateFnsLocalizer,
  type Event as EvenementRBC,
  type View,
} from "react-big-calendar";
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
import { dateDepuisAncrage, debutJour, type UniteTemps } from "@/lib/dates-relatives";
import { finCalendaire, segmentsTravailles } from "@/lib/calendrier-ouvre";
import { finRepetitionParTache, segmentsRepetition } from "@/lib/repetition-commande";

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
  // Occurrence quotidienne répétée d'une tâche de commande (voir segmentsRepetition), pas l'opération planifiée elle-même.
  estRepetition?: boolean;
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
  uniteDuree,
}: {
  planning: PlanningAvecDurees | null;
  // Optionnelle : sans elle, aucune tâche n'est marquée "en retard" (rouge).
  contraintes?: Contrainte[];
  // Optionnelle : sans elle, le libellé de l'événement n'affiche que tâche/ressource (pas de produit).
  taches?: Tache[];
  // Optionnelle : sans elle, aucune commande n'apparaît sur les événements ni d'échéance marquée.
  commandes?: StatutCommande[];
  // "heures" affiche des événements à l'heure près (vue Semaine/Jour, grille horaire) plutôt
  // que des blocs "toute la journée" — toute autre valeur reste "jours", comportement inchangé.
  uniteDuree?: string | null;
}) {
  const unite: UniteTemps = uniteDuree === "heures" ? "heures" : "jours";
  const evenements: EvenementPlanning[] = [];
  // Ouvre le calendrier sur le mois du planning affiché plutôt que sur "aujourd'hui" — un
  // planning passé ou futur resterait sinon invisible tant qu'on n'a pas navigué manuellement.
  // `useState` avec initialiseur : ne se recalcule qu'au montage (nouveau planning = nouveau
  // composant, voir la `key` posée par l'appelant), jamais à chaque rendu.
  // Vue "Semaine" par défaut en mode heures — la grille horaire y montre la précision que le
  // mode "Mois" (blocs "toute la journée") écraserait.
  const [vue, setVue] = useState<View>(unite === "heures" ? "week" : "month");
  const [date, setDate] = useState<Date>(() =>
    planning ? debutJour(new Date(planning.date_execution)) : new Date(),
  );

  if (planning) {
    // Précision complète (heure/minute) gardée en mode heures — la tronquer à minuit perdrait
    // justement l'information que ce mode existe pour capturer (voir GanttChart, même principe).
    const ancrage =
      unite === "heures"
        ? new Date(planning.date_execution)
        : debutJour(new Date(planning.date_execution));
    const produitParTache = new Map((taches ?? []).map((t) => [t.id, t.produit]));

    const commandesParTache = new Map<string, StatutCommande[]>();
    for (const commande of commandes ?? []) {
      for (const t of commande.taches) {
        commandesParTache.set(t, [...(commandesParTache.get(t) ?? []), commande]);
      }
    }

    // `duree` = heures travaillées ; `fin` = fin réelle avec pauses (nuit, week-end) en mode heures.
    const operationsAvecFin = planning.operations.map((op) => {
      const duree = planning.durees[cle(op)] ?? 0;
      return { ...op, duree, fin: finCalendaire(op.debut, duree, ancrage, unite) };
    });
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
      // Une plage par jour ouvré traversé (19h-22h puis 8h-10h) : jamais d'événement qui recouvre
      // la nuit ou le week-end. En mode jours : une seule plage, comme avant.
      for (const segment of segmentsTravailles(op.debut, op.duree, ancrage, unite)) {
        evenements.push({
          id: `${cle(op)}|${segment.debut}`,
          title: `${op.tache} · ${op.ressource}${produit ? ` (${produit})` : ""}${libelleCommandes}`,
          start: dateDepuisAncrage(segment.debut, ancrage, unite),
          // Fin exclusive en mode jours (comportement standard "all-day event"), exacte en mode
          // heures (positionnée sur la grille horaire de la vue Semaine/Jour).
          end: dateDepuisAncrage(segment.fin, ancrage, unite),
          allDay: unite === "jours",
          enRetard,
        });
      }
    }

    // Chaque tâche liée à une commande se répète chaque jour ouvré (heures ouvrées en mode heures)
    // après son opération planifiée, jusqu'à la réalisation de la commande — purement visuel, le
    // planning ne contient qu'une opération par tâche (mêmes règles que le Gantt).
    const finRepetition = finRepetitionParTache(commandes ?? [], operationsAvecFin);
    for (const op of operationsAvecFin) {
      const commandesTache = commandesParTache.get(op.tache) ?? [];
      if (commandesTache.length === 0) continue;
      const produit = produitParTache.get(op.tache);
      const libelleCommandes = ` · ${commandesTache.map((c) => c.commande_id).join(", ")}`;
      for (const segment of segmentsRepetition(
        op.fin,
        finRepetition.get(op.tache) ?? op.fin,
        ancrage,
        unite,
      )) {
        evenements.push({
          id: `${cle(op)}|rep|${segment.debut}`,
          title: `Projection · ${op.tache} · ${op.ressource}${produit ? ` (${produit})` : ""}${libelleCommandes}`,
          start: dateDepuisAncrage(segment.debut, ancrage, unite),
          end: dateDepuisAncrage(segment.fin, ancrage, unite),
          allDay: unite === "jours",
          estRepetition: true,
        });
      }
    }

    const echeancesVues = new Set<number>();
    for (const commande of commandes ?? []) {
      if (commande.date_limite === null || echeancesVues.has(commande.date_limite)) continue;
      echeancesVues.add(commande.date_limite);
      const commandesMemeEcheance = (commandes ?? []).filter(
        (c) => c.date_limite === commande.date_limite,
      );
      // Marqueur toujours "toute la journée", même en mode heures — plus visible qu'un
      // événement ponctuel d'une heure, et une échéance reste lisible à l'échelle du jour.
      const jour = debutJour(dateDepuisAncrage(commande.date_limite, ancrage, unite));
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
        view={vue}
        onView={setVue}
        date={date}
        onNavigate={setDate}
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
              // Occurrence répétée : même couleur, plus pâle et en pointillés, pour la distinguer
              // de l'opération réellement planifiée.
              ...(e.estRepetition ? { opacity: 0.55, border: "1px dashed #c7d2fe" } : {}),
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
      {evenements.some((e) => e.estRepetition) && (
        <p className="mt-2 text-center text-xs text-muted-foreground">
          « Projection » (pâle, pointillés) : tâche répétée chaque jour ouvré jusqu'à la réalisation
          de la commande — visuel seulement, aucune capacité n'est réservée dans le planning.
        </p>
      )}
      {!planning && (
        <p className="mt-2 text-center text-xs text-muted-foreground">
          Aucun planning sélectionné pour l'instant — choisis une exécution ci-dessous.
        </p>
      )}
    </div>
  );
}

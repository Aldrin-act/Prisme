import type { StatutCommande } from "@/integrations/prisme";
import { dateDepuisAncrage, type UniteTemps } from "@/lib/dates-relatives";
import { estInstantOuvre } from "@/lib/calendrier-ouvre";

// Réexport : le calendrier ouvré vit désormais dans `calendrier-ouvre.ts`.
export { HEURE_FERMETURE, HEURE_OUVERTURE, estInstantOuvre } from "@/lib/calendrier-ouvre";

// Répétition d'une tâche de commande : un segment par jour ouvré entre `debut` et `fin` (jamais
// fusionnés d'un jour au suivant, pour que chaque jour se lise comme un bloc à lui) — en mode
// jours, un instant == un jour ; en mode heures, les heures ouvrées contiguës d'un même jour.
// Purement visuel : le planning, lui, ne contient qu'UNE opération par tâche.
export function segmentsRepetition(
  debut: number,
  fin: number,
  ancrage: Date,
  unite: UniteTemps,
): { debut: number; fin: number }[] {
  const segments: { debut: number; fin: number }[] = [];
  let jourCourant: string | null = null;
  for (let instant = debut; instant < fin; instant++) {
    if (!estInstantOuvre(instant, ancrage, unite)) {
      jourCourant = null;
      continue;
    }
    const jour = dateDepuisAncrage(instant, ancrage, unite).toDateString();
    const dernier = segments[segments.length - 1];
    if (jourCourant === jour && dernier && dernier.fin === instant) {
      dernier.fin = instant + 1;
    } else {
      segments.push({ debut: instant, fin: instant + 1 });
    }
    jourCourant = jour;
  }
  return segments;
}

// Jusqu'où une tâche se répète : la commande est « réalisée » à son échéance quand elle en a une
// (le travail court jusque-là, même si la dernière opération planifiée finit plus tôt), sinon à la
// fin de sa dernière opération planifiée ; jamais avant cette dernière opération, si l'échéance
// est déjà dépassée. Une tâche liée à plusieurs commandes prend la plus tardive. `date_limite` est
// exclusive comme dans le vérificateur de faisabilité (une opération finissant à `date_limite` est
// à l'heure) : le dernier bloc répété tombe donc la veille de l'échéance.
export function finRepetitionParTache(
  commandes: StatutCommande[],
  operations: { tache: string; fin: number }[],
): Map<string, number> {
  const parTache = new Map<string, number>();
  for (const commande of commandes) {
    const fins = operations.filter((op) => commande.taches.includes(op.tache)).map((op) => op.fin);
    if (fins.length === 0) continue;
    const fin = Math.max(...fins, commande.date_limite ?? 0);
    for (const tache of commande.taches) {
      parTache.set(tache, Math.max(parTache.get(tache) ?? 0, fin));
    }
  }
  return parTache;
}

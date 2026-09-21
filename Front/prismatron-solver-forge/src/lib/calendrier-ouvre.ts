import { dateDepuisAncrage, type UniteTemps } from "@/lib/dates-relatives";

// Miroir TypeScript de `dsl/calendrier.py` : mêmes heures ouvrées, même règle de pause. Une
// opération en mode heures ne travaille que pendant les heures ouvrées — démarrée à 19h avec 5 h de
// travail, elle travaille jusqu'à 22h, s'arrête, reprend à 8h le lendemain et finit à 10h. Sa durée
// (`durees["tache|ressource"]`) compte les heures *travaillées* ; sa fin réelle est `finCalendaire`.
// En mode jours, aucune pause : fin = début + durée (les week-ends restent gérés côté serveur).

// Heures ouvrées fixes 8h-22h, week-end fermé — mêmes valeurs que les défauts de `InstanceTRCO`
// (`heure_ouverture`/`heure_fermeture`/`jours_fermes`).
export const HEURE_OUVERTURE = 8;
export const HEURE_FERMETURE = 22;

// Ouvré = ni samedi/dimanche ni — en mode heures — hors 8h-22h. Ancré sur la même date que les
// graduations (l'heure réelle de l'exécution, celle qui a ancré le calendrier côté serveur).
export function estInstantOuvre(instant: number, ancrage: Date, unite: UniteTemps): boolean {
  const date = dateDepuisAncrage(instant, ancrage, unite);
  const weekEnd = [0, 6].includes(date.getDay());
  const horsHeuresOuvrees =
    unite === "heures" && (date.getHours() < HEURE_OUVERTURE || date.getHours() >= HEURE_FERMETURE);
  return !weekEnd && !horsHeuresOuvrees;
}

// Garde-fou contre une boucle infinie si aucune heure n'était ouvrée (calendrier vide).
const BORNE_RECHERCHE = 168 * 4;

/** Plages `[début, fin[` réellement travaillées par une opération (une par jour ouvré traversé).
 * En mode jours : une seule plage `[debut, debut + duree[`. */
export function segmentsTravailles(
  debut: number,
  duree: number,
  ancrage: Date,
  unite: UniteTemps,
): { debut: number; fin: number }[] {
  if (unite !== "heures" || duree <= 0) return [{ debut, fin: debut + duree }];
  const segments: { debut: number; fin: number }[] = [];
  let instant = debut;
  let restant = duree;
  let essais = 0;
  while (restant > 0) {
    if (essais++ > BORNE_RECHERCHE + duree * 24) return [{ debut, fin: debut + duree }];
    if (estInstantOuvre(instant, ancrage, unite)) {
      const dernier = segments[segments.length - 1];
      if (dernier && dernier.fin === instant) dernier.fin = instant + 1;
      else segments.push({ debut: instant, fin: instant + 1 });
      restant -= 1;
    }
    instant += 1;
  }
  return segments;
}

/** Instant qui suit la dernière heure travaillée (voir `fin_calendaire`, Python). */
export function finCalendaire(
  debut: number,
  duree: number,
  ancrage: Date,
  unite: UniteTemps,
): number {
  const segments = segmentsTravailles(debut, duree, ancrage, unite);
  return segments[segments.length - 1]?.fin ?? debut + duree;
}

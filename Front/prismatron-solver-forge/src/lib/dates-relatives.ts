// Le DSL ne connaît que des instants relatifs entiers (jamais une date calendaire — voir
// CLAUDE.md, "jamais une date calendaire n'entre dans le DSL ni le backend") : `echeance`,
// `debut`, `jours_indisponibles`... dans l'unité déclarée par `InstanceTRCO.unite_temps`
// ("jours" ou "heures", voir `dsl/schema/instance.py`). Ces fonctions ne servent qu'à convertir
// vers/depuis une date réelle *pour l'affichage et la saisie*, ancrées sur un point de référence
// explicite (`ancrage`) qui varie selon le contexte :
//   - après exécution : `date_execution` (ou `date_derniere_execution_reussie`), un fait
//     historique figé côté serveur, jamais recalculé ;
//   - avant exécution, dans les formulaires de configuration : `aujourdhui()`, une
//     prévisualisation "si exécuté maintenant" qui peut légitimement dériver si l'instance n'est
//     exécutée que plus tard — jamais une valeur persistée.
// Le DSL/backend ne voit jamais que l'entier qui ressort de ces conversions. `unite` (par défaut
// "jours", préserve tous les appels existants) bascule l'arithmétique jour ↔ heure ; en mode
// "heures", `ancrage` garde sa précision complète (heure/minute), jamais tronqué à minuit comme
// `debutJour` le fait pour le mode jours.
export type UniteTemps = "jours" | "heures";

const FORMATTEUR_DATE = new Intl.DateTimeFormat("fr-FR", {
  weekday: "short",
  day: "numeric",
  month: "short",
});

const FORMATTEUR_DATE_HEURE = new Intl.DateTimeFormat("fr-FR", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

const MS_PAR_HEURE = 3_600_000;
const MS_PAR_JOUR = 24 * MS_PAR_HEURE;

export function debutJour(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

// Ancrage "si exécuté aujourd'hui" pour les contextes sans exécution réelle — toujours minuit
// local, jamais recalculé plusieurs fois dans un même rendu (voir chaque appelant).
export function aujourdhui(): Date {
  return debutJour(new Date());
}

export function dateDepuisAncrage(
  instant: number,
  ancrage: Date,
  unite: UniteTemps = "jours",
): Date {
  const date = new Date(ancrage);
  if (unite === "heures") {
    date.setHours(date.getHours() + instant);
  } else {
    date.setDate(date.getDate() + instant);
  }
  return date;
}

export function jourDepuisAncrage(date: Date, ancrage: Date, unite: UniteTemps = "jours"): number {
  if (unite === "heures") {
    return Math.round((date.getTime() - ancrage.getTime()) / MS_PAR_HEURE);
  }
  return Math.round((debutJour(date).getTime() - debutJour(ancrage).getTime()) / MS_PAR_JOUR);
}

export function formatDateRelative(
  instant: number,
  ancrage: Date,
  unite: UniteTemps = "jours",
): string {
  const date = dateDepuisAncrage(instant, ancrage, unite);
  return unite === "heures" ? FORMATTEUR_DATE_HEURE.format(date) : FORMATTEUR_DATE.format(date);
}

// Jour seul (sans l'heure), même format que le mode jours de `formatDateRelative` — utilisé par
// l'axe du Gantt en mode heures pour une ligne de regroupement par jour distincte de la ligne
// d'heures (voir `gantt-chart.tsx`), plutôt que de répéter la date entière sur chaque colonne.
export function formatJour(date: Date): string {
  return FORMATTEUR_DATE.format(date);
}

// Heure seule ("HH:mm"), en heure locale — deuxième ligne de l'axe du Gantt en mode heures.
export function formatHeure(date: Date): string {
  return `${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

// Format "YYYY-MM-DD" attendu par <input type="date">, en heure locale — jamais
// `toISOString().slice(0, 10)`, qui bascule en UTC et peut faire glisser d'un jour selon le
// fuseau de l'utilisateur.
export function formatEntreeDate(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function parseEntreeDate(valeur: string): Date | null {
  if (!valeur) return null;
  const [y, m, d] = valeur.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

// Mêmes principes que `formatEntreeDate`/`parseEntreeDate`, pour <input type="datetime-local">
// (mode heures) — format "YYYY-MM-DDTHH:mm", toujours en heure locale.
export function formatEntreeDateHeure(date: Date): string {
  const h = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${formatEntreeDate(date)}T${h}:${min}`;
}

export function parseEntreeDateHeure(valeur: string): Date | null {
  if (!valeur) return null;
  const [partieDate, partieHeure] = valeur.split("T");
  const date = parseEntreeDate(partieDate);
  if (!date || !partieHeure) return null;
  const [h, min] = partieHeure.split(":").map(Number);
  if (h === undefined || min === undefined || Number.isNaN(h) || Number.isNaN(min)) return null;
  date.setHours(h, min, 0, 0);
  return date;
}

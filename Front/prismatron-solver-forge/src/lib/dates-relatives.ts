// Le DSL ne connaît que des jours relatifs entiers (jamais une date calendaire — voir CLAUDE.md,
// "jamais une date calendaire n'entre dans le DSL ni le backend") : `echeance`, `debut`,
// `jours_indisponibles`... Ces fonctions ne servent qu'à convertir vers/depuis une date réelle
// *pour l'affichage et la saisie*, ancrées sur un point de référence explicite (`ancrage`) qui
// varie selon le contexte :
//   - après exécution : `date_execution` (ou `date_derniere_execution_reussie`), un fait
//     historique figé côté serveur, jamais recalculé ;
//   - avant exécution, dans les formulaires de configuration : `aujourdhui()`, une
//     prévisualisation "si exécuté maintenant" qui peut légitimement dériver si l'instance n'est
//     exécutée que plus tard — jamais une valeur persistée.
// Le DSL/backend ne voit jamais que l'entier de jours qui ressort de ces conversions.

const FORMATTEUR_DATE = new Intl.DateTimeFormat("fr-FR", {
  weekday: "short",
  day: "numeric",
  month: "short",
});

const MS_PAR_JOUR = 86_400_000;

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

export function dateDepuisAncrage(jour: number, ancrage: Date): Date {
  const date = new Date(ancrage);
  date.setDate(date.getDate() + jour);
  return date;
}

export function jourDepuisAncrage(date: Date, ancrage: Date): number {
  return Math.round((debutJour(date).getTime() - debutJour(ancrage).getTime()) / MS_PAR_JOUR);
}

export function formatDateRelative(jour: number, ancrage: Date): string {
  return FORMATTEUR_DATE.format(dateDepuisAncrage(jour, ancrage));
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

// Unité dans laquelle l'interface affiche les durées/échéances d'une
// instance — purement cosmétique : le DSL, le solveur généré, le
// vérificateur de faisabilité et le banc synthétique continuent de
// raisonner en jours entiers, inchangés. Plus une saisie manuelle : calculée
// une fois côté backend à l'ingestion, à partir des durées réelles de
// l'instance (voir `api/unite_duree.py::detecter_unite_duree`). "jours" est
// le défaut implicite (valeur absente/`null` côté API, ex. instance
// ingérée avant ce calcul).
export type UniteDuree = "jours" | "semaines" | "mois";

export const LABELS_UNITE_DUREE: Record<UniteDuree, string> = {
  jours: "Jours",
  semaines: "Semaines",
  mois: "Mois",
};

// Approximations documentées (pas de calendrier réel dans PRISME — voir
// CLAUDE.md, "jamais une date calendaire") : une semaine = 7 jours, un mois
// = 30 jours.
const JOURS_PAR_UNITE: Record<UniteDuree, number> = {
  jours: 1,
  semaines: 7,
  mois: 30,
};

function uniteConnue(valeur: string | null | undefined): UniteDuree {
  return valeur === "semaines" || valeur === "mois" ? valeur : "jours";
}

// Convertit un entier-jours en texte lisible dans l'unité choisie. Garde
// toujours le compte exact en jours entre parenthèses quand l'unité
// affichée n'est pas "jours" (ex. "3,6 semaines (25 j.)") — rien n'est
// jamais perdu, même quand la conversion n'est pas un nombre rond.
export function formatDuree(jours: number, unite?: string | null): string {
  const uniteEffective = uniteConnue(unite);
  if (uniteEffective === "jours") {
    return `${jours} jour${Math.abs(jours) > 1 ? "s" : ""}`;
  }
  const valeur = jours / JOURS_PAR_UNITE[uniteEffective];
  const arrondi = Math.round(valeur * 10) / 10;
  const libelle = uniteEffective === "semaines" ? "semaine" : "mois";
  const pluriel = uniteEffective === "semaines" && Math.abs(arrondi) > 1 ? "s" : "";
  const texteValeur = arrondi.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
  return `${texteValeur} ${libelle}${pluriel} (${jours} j.)`;
}

// Étiquette courte pour un axe/une puce (Gantt, graphe par jour) — jamais le
// rappel entre parenthèses, qui surchargerait un axe à plusieurs graduations.
export function formatDureeCourte(jours: number, unite?: string | null): string {
  const uniteEffective = uniteConnue(unite);
  if (uniteEffective === "jours") return `${jours} j.`;
  const valeur = jours / JOURS_PAR_UNITE[uniteEffective];
  const arrondi = Math.round(valeur * 10) / 10;
  const abbrev = uniteEffective === "semaines" ? "sem." : "mois";
  return `${arrondi.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ${abbrev}`;
}

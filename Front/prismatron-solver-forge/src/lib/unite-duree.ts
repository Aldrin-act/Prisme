// Unité dans laquelle l'interface affiche les durées/échéances d'une
// instance — purement cosmétique : le solveur généré et le vérificateur de
// faisabilité continuent de raisonner sur l'entier brut, inchangés (voir
// `InstanceTRCO.unite_temps`, "jours" ou "heures" — le vrai référentiel de
// cet entier — et `api/unite_duree.py::detecter_unite_duree`, qui calcule ce
// libellé d'affichage : "heures" directement si `unite_temps == "heures"`,
// sinon une sur-échelle jours/semaines/mois choisie selon la magnitude). Plus
// une saisie manuelle. "jours" est le défaut implicite (valeur absente/`null`
// côté API, ex. instance ingérée avant ce calcul).
export type UniteDuree = "heures" | "jours" | "semaines" | "mois";

export const LABELS_UNITE_DUREE: Record<UniteDuree, string> = {
  heures: "Heures",
  jours: "Jours",
  semaines: "Semaines",
  mois: "Mois",
};

// Base commune : les heures, seule unité qui soit une SOUS-division du jour plutôt qu'un
// multiple — un `JOURS_PAR_UNITE` (base jours) ne peut pas représenter "heures" (semaines/mois
// s'expriment naturellement comme un nombre entier de jours, jamais l'inverse). Approximations
// documentées pour semaines/mois (pas de calendrier réel dans PRISME — voir CLAUDE.md, "jamais
// une date calendaire") : une semaine = 7 jours, un mois = 30 jours.
const HEURES_PAR_UNITE: Record<UniteDuree, number> = {
  heures: 1,
  jours: 24,
  semaines: 7 * 24,
  mois: 30 * 24,
};

function uniteConnue(valeur: string | null | undefined): UniteDuree {
  return valeur === "heures" || valeur === "semaines" || valeur === "mois" ? valeur : "jours";
}

// Convertit l'entier brut d'une instance (jours ou heures selon `InstanceTRCO.unite_temps`,
// voir `unite` ci-dessous) en texte lisible dans l'unité d'affichage choisie (`uniteAffichage`,
// "jours"/"semaines"/"mois" pour une instance en mode jours, "heures" pour une instance en mode
// heures — jamais un mélange des deux). Garde toujours le compte exact entre parenthèses quand
// l'unité affichée diffère de l'unité brute (ex. "3,6 semaines (25 j.)") — rien n'est jamais
// perdu, même quand la conversion n'est pas un nombre rond.
export function formatDuree(valeurBrute: number, uniteAffichage?: string | null): string {
  const uniteEffective = uniteConnue(uniteAffichage);
  if (uniteEffective === "heures") {
    return `${valeurBrute} heure${Math.abs(valeurBrute) > 1 ? "s" : ""}`;
  }
  if (uniteEffective === "jours") {
    return `${valeurBrute} jour${Math.abs(valeurBrute) > 1 ? "s" : ""}`;
  }
  const heuresBrutes = valeurBrute * HEURES_PAR_UNITE.jours; // valeurBrute est en jours ici
  const valeur = heuresBrutes / HEURES_PAR_UNITE[uniteEffective];
  const arrondi = Math.round(valeur * 10) / 10;
  const libelle = uniteEffective === "semaines" ? "semaine" : "mois";
  const pluriel = uniteEffective === "semaines" && Math.abs(arrondi) > 1 ? "s" : "";
  const texteValeur = arrondi.toLocaleString("fr-FR", { maximumFractionDigits: 1 });
  return `${texteValeur} ${libelle}${pluriel} (${valeurBrute} j.)`;
}

// Étiquette courte pour un axe/une puce (Gantt, graphe par jour) — jamais le
// rappel entre parenthèses, qui surchargerait un axe à plusieurs graduations.
export function formatDureeCourte(valeurBrute: number, uniteAffichage?: string | null): string {
  const uniteEffective = uniteConnue(uniteAffichage);
  if (uniteEffective === "heures") return `${valeurBrute} h.`;
  if (uniteEffective === "jours") return `${valeurBrute} j.`;
  const heuresBrutes = valeurBrute * HEURES_PAR_UNITE.jours;
  const valeur = heuresBrutes / HEURES_PAR_UNITE[uniteEffective];
  const arrondi = Math.round(valeur * 10) / 10;
  const abbrev = uniteEffective === "semaines" ? "sem." : "mois";
  return `${arrondi.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ${abbrev}`;
}

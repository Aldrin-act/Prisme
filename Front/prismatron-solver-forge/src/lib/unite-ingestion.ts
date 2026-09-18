import type { UniteTemps } from "./dates-relatives";

// Tout ce qui, dans les formulaires d'ingestion, dépend de l'unité de temps choisie (jours ou
// heures) sans rien convertir côté serveur : gabarits téléchargeables, nom de la colonne de durée
// des CSV, libellés. Le backend ne convertit jamais un entier — il le lit dans l'unité déclarée
// à l'import (`unite_temps`, voir adapters/csv_import/traducteur.py::_colonne_duree) — d'où
// l'importance que le gabarit téléchargé et le libellé affiché suivent le même choix.

export type EntiteGabaritCsv = "taches" | "ressources" | "contraintes" | "commandes";

// Aucun gabarit ne porte de durée (elle se fixe à la commande) : seule commandes.csv dépend de
// l'unité, par sa date_limite. contraintes.csv garde une variante "_heures" par simple cohérence
// de nommage, son contenu étant identique (scripts/generer_gabarit_csv.py, recopiés dans
// public/gabarits/). taches.csv et ressources.csv servent les deux unités tels quels.
const ENTITES_AVEC_VARIANTE_UNITE: EntiteGabaritCsv[] = ["contraintes", "commandes"];

export function nomGabaritCsv(entite: EntiteGabaritCsv, unite: UniteTemps): string {
  const suffixe =
    unite === "heures" && ENTITES_AVEC_VARIANTE_UNITE.includes(entite) ? "_heures" : "";
  return `${entite}${suffixe}.csv`;
}

export function hrefGabaritCsv(entite: EntiteGabaritCsv, unite: UniteTemps): string {
  return `/gabarits/${nomGabaritCsv(entite, unite)}`;
}

export function nomGabaritJson(unite: UniteTemps): string {
  return unite === "heures" ? "instance_exemple_heures.json" : "instance_exemple.json";
}

export function hrefGabaritJson(unite: UniteTemps): string {
  return `/gabarits/${nomGabaritJson(unite)}`;
}

// Colonne de durée attendue dans contraintes.csv pour cette unité. Le backend accepte aussi une
// colonne neutre `duree`, mais le gabarit nomme toujours l'unité, pour qu'un fichier rempli
// reste lisible hors de PRISME.
export function colonneDureeCsv(unite: UniteTemps): "duree_jours" | "duree_heures" {
  return unite === "heures" ? "duree_heures" : "duree_jours";
}

export function libelleUnite(unite: UniteTemps): string {
  return unite === "heures" ? "heures" : "jours";
}

export const HEURES_PAR_JOUR = 24;

// Conversion d'une durée déjà saisie (texte brut d'un <input type="number">) quand l'utilisateur
// change d'unité en cours de saisie : jours → heures multiplie par 24, heures → jours divise par
// 24 en arrondissant au jour supérieur (le DSL n'accepte que des entiers, et arrondir vers le bas
// raccourcirait une tâche — une durée plus courte que la réalité rend un planning infaisable sur
// le terrain, une durée un peu plus longue non). Une saisie vide ou non numérique est laissée
// telle quelle : rien à convertir, jamais inventer une valeur.
export function convertirDureeSaisie(valeur: string, de: UniteTemps, vers: UniteTemps): string {
  if (de === vers || valeur.trim() === "") return valeur;
  const nombre = Number(valeur);
  if (!Number.isFinite(nombre)) return valeur;
  if (de === "jours" && vers === "heures") return String(Math.round(nombre * HEURES_PAR_JOUR));
  const jours = Math.ceil(nombre / HEURES_PAR_JOUR);
  return String(nombre > 0 ? Math.max(1, jours) : jours);
}

// Échéance saisie : "YYYY-MM-DD" (<input type="date">, mode jours) ↔ "YYYY-MM-DDTHH:mm"
// (<input type="datetime-local">, mode heures). Jours → heures ancre en début de journée (00:00),
// même convention que `debutJour` (dates-relatives.ts). Heures → jours garde le jour calendaire
// de l'instant saisi.
export function convertirDateSaisie(valeur: string, de: UniteTemps, vers: UniteTemps): string {
  if (de === vers || !valeur) return valeur;
  if (vers === "heures") return valeur.includes("T") ? valeur : `${valeur}T00:00`;
  return valeur.slice(0, 10);
}

// Indisponibilités ponctuelles : en mode jours une entrée = un jour entier, en mode heures une
// entrée = un créneau d'une heure. Jours → heures déplie donc chaque jour en ses 24 créneaux (un
// jour indisponible reste indisponible toute la journée, pas seulement à minuit). Heures → jours
// rend indisponible tout jour ayant au moins un créneau indisponible — conversion prudente : elle
// peut retirer de la capacité, jamais en ajouter une qui n'existait pas.
export function convertirDatesIndisponibles(
  valeurs: string[],
  de: UniteTemps,
  vers: UniteTemps,
): string[] {
  if (de === vers) return valeurs;
  if (vers === "heures") {
    return valeurs.flatMap((jour) =>
      Array.from(
        { length: HEURES_PAR_JOUR },
        (_, h) => `${jour.slice(0, 10)}T${String(h).padStart(2, "0")}:00`,
      ),
    );
  }
  return [...new Set(valeurs.map((v) => v.slice(0, 10)))].sort();
}

// Motif hebdomadaire : jour de semaine JS (0-6) en mode jours, index plat jourSemaine×24+heure
// (0-167) en mode heures (voir GrilleMotifHebdomadaireHeures). Même logique que ci-dessus :
// déplier un jour en 24 heures, ou replier en marquant tout jour ayant au moins une heure fermée.
export function convertirMotifHebdomadaire(
  valeurs: number[],
  de: UniteTemps,
  vers: UniteTemps,
): number[] {
  if (de === vers) return valeurs;
  if (vers === "heures") {
    return valeurs.flatMap((jour) =>
      Array.from({ length: HEURES_PAR_JOUR }, (_, h) => jour * HEURES_PAR_JOUR + h),
    );
  }
  return [...new Set(valeurs.map((v) => Math.floor(v / HEURES_PAR_JOUR)))].sort((a, b) => a - b);
}

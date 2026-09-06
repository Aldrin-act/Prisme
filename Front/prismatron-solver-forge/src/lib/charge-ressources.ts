import type { Contrainte } from "@/integrations/prisme";

// Capacité effective d'une ressource un jour donné : `ContrainteCapacite` (défaut 1) si le jour
// n'est pas dans ses `jours_indisponibles` déclarés (`ContrainteDisponibiliteRessource`), 0 sinon.
// `jours_semaine_indisponibles` (motif hebdomadaire récurrent) n'est volontairement pas pris en
// compte ici — même limitation que le calcul dont ceci dérive (voir plus bas), pas une régression
// introduite par ce module.
function capaciteJour(ressource: string, jour: number, contraintes: Contrainte[]): number {
  const indisponible = contraintes.some(
    (c) =>
      c.type === "disponibilite_ressource" &&
      c.ressource === ressource &&
      c.jours_indisponibles.includes(jour),
  );
  if (indisponible) return 0;
  return (
    contraintes.find(
      (c): c is Contrainte & { type: "capacite" } =>
        c.type === "capacite" && c.ressource === ressource,
    )?.capacite ?? 1
  );
}

// Taux d'utilisation d'une ressource sur tout le makespan, conscient de la capacité et de la
// disponibilité — pas une simple charge/makespan, qui sous-estimerait une ressource à capacité > 1
// et surestimerait une ressource avec des jours indisponibles déclarés. Déplacé depuis
// `components/planning/gantt-chart.tsx` (comportement inchangé) pour être partagé avec la page
// Analytique, onglet "Charge des ressources", plutôt que dupliqué.
export function tauxUtilisationRessource(
  ressource: string,
  operations: { debut: number; fin: number }[],
  makespan: number,
  contraintes: Contrainte[],
): number {
  let capaciteTotale = 0;
  for (let jour = 0; jour < makespan; jour++) {
    capaciteTotale += capaciteJour(ressource, jour, contraintes);
  }
  if (capaciteTotale === 0) return 0;
  const charge = operations.reduce((somme, op) => somme + (op.fin - op.debut), 0);
  return Math.min(100, (charge / capaciteTotale) * 100);
}

export interface ChargeRessource {
  ressource: string;
  capacite: number;
  charge: number;
  disponible: number;
  taux: number; // 0-100
}

// Capacité/charge/disponible/taux par ressource — même calcul que
// `tauxUtilisationRessource`, mais expose aussi les quantités brutes
// (capacité et disponible) plutôt que seulement le ratio, pour le détail par
// ressource (goulots d'étranglement, capacité encore disponible).
export function chargeParRessource(
  ressources: string[],
  operations: { ressource: string; debut: number; fin: number }[],
  contraintes: Contrainte[],
  makespan: number,
): ChargeRessource[] {
  return ressources.map((ressource) => {
    const operationsRessource = operations.filter((op) => op.ressource === ressource);
    let capacite = 0;
    for (let jour = 0; jour < makespan; jour++) {
      capacite += capaciteJour(ressource, jour, contraintes);
    }
    const charge = operationsRessource.reduce((somme, op) => somme + (op.fin - op.debut), 0);
    const taux = capacite === 0 ? 0 : Math.min(100, (charge / capacite) * 100);
    return { ressource, capacite, charge, disponible: Math.max(0, capacite - charge), taux };
  });
}

export interface TacheEnRetard {
  tache: string;
  fin: number;
  echeance: number;
  retard: number;
}

// Tâches dont la fin dépasse leur `Echeance` déclarée — même comparaison que
// `api/comparaison_scenarios.py::calculer_metriques` (`taches_en_retard`),
// reproduite ici côté client faute d'une exécution unique déjà exposée par
// cet endpoint (il ne sert que la comparaison de scénarios).
export function tachesEnRetard(
  operations: { tache: string; fin: number }[],
  contraintes: Contrainte[],
): TacheEnRetard[] {
  const echeanceParTache = new Map(
    contraintes
      .filter((c): c is Contrainte & { type: "echeance" } => c.type === "echeance")
      .map((c) => [c.tache, c.echeance]),
  );
  const finParTache = new Map<string, number>();
  for (const op of operations) finParTache.set(op.tache, op.fin);

  const resultat: TacheEnRetard[] = [];
  for (const [tache, fin] of finParTache) {
    const echeance = echeanceParTache.get(tache);
    if (echeance !== undefined && fin > echeance) {
      resultat.push({ tache, fin, echeance, retard: fin - echeance });
    }
  }
  return resultat.sort((a, b) => b.retard - a.retard);
}

export interface ChargeJour {
  jour: number;
  capacite: number;
  charge: number;
}

// Même principe que `tauxUtilisationRessource`, mais jour par jour plutôt qu'agrégé sur tout le
// makespan — pour un graphe temporel. `ressources` limite le calcul à un sous-ensemble (filtre de
// la page) ; passer toutes les ressources de l'instance pour une vue non filtrée.
export function chargeParJour(
  ressources: string[],
  operations: { ressource: string; debut: number; fin: number }[],
  contraintes: Contrainte[],
  makespan: number,
): ChargeJour[] {
  const ensembleRessources = new Set(ressources);
  const operationsIncluses = operations.filter((op) => ensembleRessources.has(op.ressource));

  const resultat: ChargeJour[] = [];
  for (let jour = 0; jour < makespan; jour++) {
    const capacite = ressources.reduce((somme, r) => somme + capaciteJour(r, jour, contraintes), 0);
    const charge = operationsIncluses.filter((op) => op.debut <= jour && jour < op.fin).length;
    resultat.push({ jour, capacite, charge });
  }
  return resultat;
}

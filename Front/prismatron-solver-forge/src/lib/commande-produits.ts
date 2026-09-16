import type { GammeCommandeStatut } from "@/integrations/prisme";

/**
 * Libellé lisible des produits (gammes) référencés par une commande — ex.
 * "Vanne V12 (x5), Bride B7" — `null` pour une commande qui ne référence que des tâches choisies
 * directement (voir `StatutCommande.taches`). Partagé entre la page Commandes (tableau global) et
 * la liste des commandes d'une instance (onglet Flux), jamais dupliqué.
 */
export function libelleProduitsCommande(gammes: GammeCommandeStatut[]): string | null {
  if (gammes.length === 0) return null;
  return gammes
    .map((g) => {
      const nom = g.nom ? `${g.produit} — ${g.nom}` : g.produit;
      return g.quantite ? `${nom} (x${g.quantite})` : nom;
    })
    .join(", ");
}

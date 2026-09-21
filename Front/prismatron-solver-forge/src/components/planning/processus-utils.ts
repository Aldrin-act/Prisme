// Utilitaires partagés par l'éditeur de processus et son inspecteur d'étape — dans un module sans
// composant, pour que le rechargement à chaud de React reste possible sur les deux fichiers.

/** Compétences saisies en texte libre, séparées par des virgules. */
export function competencesDe(texte: string): string[] {
  return texte
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean);
}

// Identifiant technique proposé à partir du libellé : « Contrôle final » → CONTROLE_FINAL. L'id
// reste modifiable, mais un chef d'atelier n'a pas à inventer un code quand il nomme une étape.
export function idDepuisNom(nom: string): string {
  return nom
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 40);
}

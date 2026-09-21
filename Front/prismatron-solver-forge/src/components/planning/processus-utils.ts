import type { EtapeProcessus, InstanceTRCO } from "@/integrations/prisme";

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

/** Étapes dans l'ordre de la chaîne, ou `null` si le processus n'est pas une simple suite (étapes
 * parallèles, fusion) ou si une étape a plusieurs compétences — ce que la liste ne sait pas dire. */
export function ordreChaine(etapes: EtapeProcessus[]): EtapeProcessus[] | null {
  if (etapes.length === 0) return [];
  if (etapes.some((e) => e.competences.length !== 1 || e.predecesseurs.length > 1)) return null;
  const racines = etapes.filter((e) => e.predecesseurs.length === 0);
  if (racines.length !== 1) return null;
  const ordre = [racines[0]];
  while (ordre.length < etapes.length) {
    const dernier = ordre[ordre.length - 1];
    const suivantes = etapes.filter((e) => e.predecesseurs[0] === dernier.id);
    if (suivantes.length !== 1) return null;
    ordre.push(suivantes[0]);
  }
  return ordre;
}

export function estProcessusSimple(etapes: EtapeProcessus[]): boolean {
  return ordreChaine(etapes) !== null;
}

/** Processus proposé à partir des tâches déjà présentes dans l'atelier : une tâche = une étape.
 * Les tâches de même nom (une copie par commande, en pratique) se replient en une seule étape ;
 * l'ordre vient des précédences, les compétences des `competence_requise`, la durée par pièce de
 * la durée la plus courte déclarée sur une ressource compatible. Rien n'est inventé : une étape
 * sans compétence ou sans durée reste vide, à compléter avant d'enregistrer. Une proposition,
 * jamais enregistrée sans validation humaine. */
export function etapesDepuisTaches(
  instance: Pick<InstanceTRCO, "taches" | "contraintes">,
): EtapeProcessus[] {
  const etapes = new Map<string, EtapeProcessus>();
  const etapeParTache = new Map<string, string>();

  for (const tache of instance.taches) {
    const nom = tache.nom?.trim() || tache.id;
    const id = idDepuisNom(nom) || idDepuisNom(tache.id) || "ETAPE";
    if (!etapes.has(id)) {
      etapes.set(id, { id, nom, competences: [], predecesseurs: [], duree_par_piece: 0 });
    }
    etapeParTache.set(tache.id, id);
  }

  for (const c of instance.contraintes) {
    if (c.type === "competence_requise") {
      const etape = etapes.get(etapeParTache.get(c.tache) ?? "");
      if (etape && !etape.competences.includes(c.competence)) etape.competences.push(c.competence);
    } else if (c.type === "compatibilite_ressource_tache") {
      const etape = etapes.get(etapeParTache.get(c.tache) ?? "");
      if (etape && (etape.duree_par_piece === 0 || c.duree < etape.duree_par_piece)) {
        etape.duree_par_piece = c.duree;
      }
    } else if (c.type === "precedence") {
      const avant = etapeParTache.get(c.avant);
      const apres = etapeParTache.get(c.apres);
      const etape = apres ? etapes.get(apres) : undefined;
      if (etape && avant && avant !== apres && !etape.predecesseurs.includes(avant)) {
        etape.predecesseurs.push(avant);
      }
    }
  }
  return [...etapes.values()];
}

/** Enchaînements distincts d'un ensemble d'étapes : groupes d'étapes reliés entre eux par des
 * précédences (composantes connexes). Un atelier n'a qu'un seul processus — plus d'un groupe
 * signale des étapes sans aucun lien avec le reste, à vérifier. Une étape isolée forme son propre
 * groupe. Purement informatif, jamais bloquant. */
export function enchainementsDistincts(etapes: EtapeProcessus[]): EtapeProcessus[][] {
  const parent = new Map(etapes.map((e) => [e.id, e.id]));
  const racine = (id: string): string => {
    let courant = id;
    while (parent.get(courant) !== courant) courant = parent.get(courant) ?? courant;
    return courant;
  };
  for (const e of etapes) {
    for (const p of e.predecesseurs) {
      if (parent.has(p)) parent.set(racine(e.id), racine(p));
    }
  }
  const groupes = new Map<string, EtapeProcessus[]>();
  for (const e of etapes) {
    const r = racine(e.id);
    groupes.set(r, [...(groupes.get(r) ?? []), e]);
  }
  return [...groupes.values()];
}

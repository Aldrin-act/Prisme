import dagre from "@dagrejs/dagre";

export const LARGEUR_NOEUD = 180;
export const HAUTEUR_NOEUD = 54;

// Mise en page one-shot (pas un solveur de contraintes persistant) — dagre
// gère les cycles en interne (inversion temporaire pour la mise en page,
// restauration ensuite), aucun garde-fou anti-cycle nécessaire ici. Ne
// renvoie que des positions (pas des Node/Edge React Flow tout faits) pour
// rester partagé entre le graphe en lecture seule (flow-graph.tsx, `data`
// figée à l'affichage) et l'éditeur (flow-graph-editor.tsx, `data` mutable
// par l'utilisateur) sans leur imposer la même forme de nœud.
export function calculerPositions(
  idsNoeuds: string[],
  aretes: { source: string; target: string }[],
): Map<string, { x: number; y: number }> {
  const graphe = new dagre.graphlib.Graph();
  graphe.setDefaultEdgeLabel(() => ({}));
  graphe.setGraph({ rankdir: "LR", nodesep: 30, ranksep: 80 });

  for (const id of idsNoeuds) {
    graphe.setNode(id, { width: LARGEUR_NOEUD, height: HAUTEUR_NOEUD });
  }
  for (const a of aretes) {
    graphe.setEdge(a.source, a.target);
  }
  dagre.layout(graphe);

  const positions = new Map<string, { x: number; y: number }>();
  for (const id of idsNoeuds) {
    const position = graphe.node(id);
    positions.set(id, { x: position.x - LARGEUR_NOEUD / 2, y: position.y - HAUTEUR_NOEUD / 2 });
  }
  return positions;
}

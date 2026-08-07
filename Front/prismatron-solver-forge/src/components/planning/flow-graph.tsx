import { useMemo } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
} from "@xyflow/react";
import dagre from "@dagrejs/dagre";
import "@xyflow/react/dist/style.css";
import "./flow-graph.css";
import type { Contrainte, Tache } from "@/integrations/prisme";

const LARGEUR_NOEUD = 180;
const HAUTEUR_NOEUD = 54;

type NoeudTache = Node<{ label: string; ressources: string[] }, "tache">;

// Nœud personnalisé plutôt que le type "default" de React Flow : le CSS de
// base de la lib (`@xyflow/react/dist/style.css`) fixe un fond blanc sur
// `.react-flow__node-default` en dehors de toute cascade layer Tailwind — nos
// classes `bg-card`/`border-border` (émises dans une layer Tailwind v4) ne
// peuvent jamais l'emporter, peu importe l'ordre d'import des deux feuilles
// de style (une règle hors layer bat toujours une règle dans une layer). Un
// nœud personnalisé génère son propre balisage, sans hériter de ce style.
// Poignées à gauche/droite (pas haut/bas, le défaut du type "default") pour
// suivre le sens de la mise en page dagre (`rankdir: "LR"`).
function NoeudTache({ data }: NodeProps<NoeudTache>) {
  // Liste, jamais une seule ressource choisie : en FJSP flexible une tâche
  // peut avoir plusieurs ressources compatibles, l'affectation réelle n'est
  // décidée qu'à l'exécution du solveur — jamais fixée dans l'instance
  // elle-même (même raisonnement que le refus des "swimlanes" façon BPMN).
  const ressourcesTexte =
    data.ressources.length > 0 ? data.ressources.join(", ") : "aucune ressource compatible";
  return (
    <div
      className="rounded-lg border border-border bg-card px-3 py-2 text-xs font-mono text-foreground"
      style={{ width: LARGEUR_NOEUD }}
      title={`${data.label}\nRessources : ${ressourcesTexte}`}
    >
      <Handle type="target" position={Position.Left} />
      <div className="truncate">{data.label}</div>
      <div className="truncate text-muted-foreground">{ressourcesTexte}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const TYPES_NOEUD = { tache: NoeudTache };

// Mise en page une seule fois par rendu (pas de recalcul dans une boucle) —
// dagre gère les cycles en interne (inversion temporaire pour la mise en
// page, restauration ensuite), aucun garde-fou anti-cycle nécessaire ici.
function disposer(
  taches: Tache[],
  aretes: { source: string; target: string }[],
  ressourcesParTache: Map<string, string[]>,
) {
  const graphe = new dagre.graphlib.Graph();
  graphe.setDefaultEdgeLabel(() => ({}));
  graphe.setGraph({ rankdir: "LR", nodesep: 30, ranksep: 80 });

  for (const t of taches) {
    graphe.setNode(t.id, { width: LARGEUR_NOEUD, height: HAUTEUR_NOEUD });
  }
  for (const a of aretes) {
    graphe.setEdge(a.source, a.target);
  }
  dagre.layout(graphe);

  const noeuds: NoeudTache[] = taches.map((t) => {
    const position = graphe.node(t.id);
    return {
      id: t.id,
      type: "tache",
      position: { x: position.x - LARGEUR_NOEUD / 2, y: position.y - HAUTEUR_NOEUD / 2 },
      data: {
        label: t.nom ? `${t.id} — ${t.nom}` : t.id,
        ressources: ressourcesParTache.get(t.id) ?? [],
      },
    };
  });

  const arcs: Edge[] = aretes.map((a, i) => ({
    id: `${a.source}->${a.target}-${i}`,
    source: a.source,
    target: a.target,
    type: "smoothstep",
    markerEnd: { type: MarkerType.ArrowClosed },
    style: { stroke: "var(--muted-foreground)" },
  }));

  return { noeuds, arcs };
}

export function FlowGraph({ taches, contraintes }: { taches: Tache[]; contraintes: Contrainte[] }) {
  const aretes = useMemo(
    () =>
      contraintes
        .filter((c): c is Contrainte & { type: "precedence" } => c.type === "precedence")
        .map((c) => ({ source: c.avant, target: c.apres })),
    [contraintes],
  );

  const ressourcesParTache = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const c of contraintes) {
      if (c.type !== "compatibilite_ressource_tache") continue;
      map.set(c.tache, [...(map.get(c.tache) ?? []), c.ressource]);
    }
    return map;
  }, [contraintes]);

  const { noeuds, arcs } = useMemo(
    () => disposer(taches, aretes, ressourcesParTache),
    [taches, aretes, ressourcesParTache],
  );

  if (taches.length === 0) {
    return <p className="text-sm text-muted-foreground">Aucune tâche pour cette instance.</p>;
  }

  return (
    <div className="h-[500px] w-full rounded-lg border border-border">
      <ReactFlowProvider>
        <ReactFlow
          nodes={noeuds}
          edges={arcs}
          nodeTypes={TYPES_NOEUD}
          fitView
          nodesConnectable={false}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls />
        </ReactFlow>
      </ReactFlowProvider>
    </div>
  );
}

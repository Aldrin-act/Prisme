import { useMemo, useState } from "react";
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
import "@xyflow/react/dist/style.css";
import "./flow-graph.css";
import { Button } from "@/components/ui/button";
import type { Contrainte, Tache } from "@/integrations/prisme";
import { LARGEUR_NOEUD, calculerPositions } from "./flow-graph-layout";
import { AvertissementEnchainements } from "./avertissement-enchainements";
import { etapesDepuisTaches } from "./processus-utils";

type NoeudTache = Node<
  { label: string; ressources: string[]; occurrences: number; ids: string[] },
  "tache"
>;

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
      title={`${data.label}${data.occurrences > 1 ? ` (×${data.occurrences})` : ""}\n${data.ids.join(", ")}\nRessources : ${ressourcesTexte}`}
    >
      <Handle type="target" position={Position.Left} />
      <div className="truncate">
        {data.label}
        {data.occurrences > 1 && (
          <span className="ml-1.5 text-muted-foreground">×{data.occurrences}</span>
        )}
      </div>
      <div className="truncate text-muted-foreground">{ressourcesTexte}</div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const TYPES_NOEUD = { tache: NoeudTache };

// Une étape du graphe : une tâche seule (vue « Tâches ») ou toutes les tâches de même nom (vue
// « Processus de l'atelier »).
interface Etape {
  cle: string;
  label: string;
  ids: string[];
}

// Le libellé d'une étape est le nom de la tâche récupérée (« Découpe laser »), jamais son
// identifiant technique (« CMD-2026-0412-OP10 »), gardé seulement dans l'info-bulle. Sans nom,
// l'identifiant reste le seul libellé possible.
function libelleTache(t: Tache): string {
  return t.nom?.trim() || t.id;
}

function etapesParTache(taches: Tache[]): Etape[] {
  return taches.map((t) => ({ cle: t.id, label: libelleTache(t), ids: [t.id] }));
}

// Processus de l'atelier : les tâches de même nom (une par commande, en pratique) se replient en
// une seule étape, et les précédences se déduisent d'une étape à l'autre — on lit alors
// l'enchaînement de l'atelier une fois, pas une copie par commande.
function etapesParProcessus(taches: Tache[]): Etape[] {
  const parNom = new Map<string, Etape>();
  for (const t of taches) {
    const label = libelleTache(t);
    const etape = parNom.get(label) ?? { cle: label, label, ids: [] };
    etape.ids.push(t.id);
    parNom.set(label, etape);
  }
  return [...parNom.values()];
}

function disposer(
  etapes: Etape[],
  aretes: { source: string; target: string }[],
  ressourcesParTache: Map<string, string[]>,
) {
  const cleParTache = new Map(etapes.flatMap((e) => e.ids.map((id) => [id, e.cle] as const)));
  const aretesEtapes = new Map<string, { source: string; target: string }>();
  for (const a of aretes) {
    const source = cleParTache.get(a.source);
    const target = cleParTache.get(a.target);
    if (source === undefined || target === undefined || source === target) continue;
    aretesEtapes.set(`${source}->${target}`, { source, target });
  }
  const arcsBruts = [...aretesEtapes.values()];

  const positions = calculerPositions(
    etapes.map((e) => e.cle),
    arcsBruts,
  );

  const noeuds: NoeudTache[] = etapes.map((e) => ({
    id: e.cle,
    type: "tache",
    position: positions.get(e.cle) ?? { x: 0, y: 0 },
    data: {
      label: e.label,
      ids: e.ids,
      occurrences: e.ids.length,
      ressources: [...new Set(e.ids.flatMap((id) => ressourcesParTache.get(id) ?? []))],
    },
  }));

  const arcs: Edge[] = arcsBruts.map((a, i) => ({
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

  const etapesTaches = useMemo(() => etapesParTache(taches), [taches]);
  const etapesProcessus = useMemo(() => etapesParProcessus(taches), [taches]);
  // Vue par défaut : le processus de l'atelier dès qu'il replie quelque chose (plusieurs commandes
  // sur le même enchaînement) — sinon les deux vues seraient identiques, autant rester sur les tâches.
  const [vue, setVue] = useState<"processus" | "taches">(
    etapesProcessus.length < etapesTaches.length ? "processus" : "taches",
  );
  const peutReplier = etapesProcessus.length < etapesTaches.length;
  const vueEffective = peutReplier ? vue : "taches";

  const { noeuds, arcs } = useMemo(
    () =>
      disposer(
        vueEffective === "processus" ? etapesProcessus : etapesTaches,
        aretes,
        ressourcesParTache,
      ),
    [vueEffective, etapesProcessus, etapesTaches, aretes, ressourcesParTache],
  );

  if (taches.length === 0) {
    return <p className="text-sm text-muted-foreground">Aucune tâche pour cette instance.</p>;
  }

  return (
    <div className="space-y-2">
      <AvertissementEnchainements etapes={etapesDepuisTaches({ taches, contraintes })} />
      {peutReplier && (
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant={vueEffective === "processus" ? "default" : "outline"}
            onClick={() => setVue("processus")}
          >
            Processus de l'atelier
          </Button>
          <Button
            size="sm"
            variant={vueEffective === "taches" ? "default" : "outline"}
            onClick={() => setVue("taches")}
          >
            Toutes les tâches ({etapesTaches.length})
          </Button>
        </div>
      )}
      <div className="h-[500px] w-full rounded-lg border border-border">
        <ReactFlowProvider>
          <ReactFlow
            key={vueEffective}
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
    </div>
  );
}

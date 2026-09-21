import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  Handle,
  Position,
  MarkerType,
  useNodesState,
  useEdgesState,
  useReactFlow,
  addEdge,
  type Node,
  type Edge,
  type NodeProps,
  type Connection,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./flow-graph.css";
import { Wand2, AlertCircle, X, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  useDefinirProcessus,
  type EtapeProcessus,
  type PrismeAPIError,
} from "@/integrations/prisme";
import { ErreursAPI } from "@/components/ingestion/ingestion-dialog";
import { LARGEUR_NOEUD, calculerPositions } from "./flow-graph-layout";
import { InspecteurEtapeProcessus } from "./inspecteur-etape-processus";
import { competencesDe } from "./processus-utils";

export type DonneesNoeudEtape = {
  id: string;
  nom: string;
  competencesTexte: string; // libre, séparées par des virgules — même patron que
  // RessourceLigne.competencesTexte dans ingestion-dialog.tsx
  dureeParPiece: string;
  /** Unité courte (« h », « j »), ajoutée pour l'affichage du nœud seulement — jamais saisie. */
  dureeUnite?: string;
};

type NoeudEtape = Node<DonneesNoeudEtape, "etape">;

// Même motif que le DSL, borné à 40 caractères : l'id de tâche généré préfixe celui de l'étape
// par l'id de commande, et doit tenir dans les 64 caractères d'un Identifiant (voir
// adapters/processus_derivation.py).
const MOTIF_IDENTIFIANT = /^[A-Za-z0-9_-]{1,40}$/;

function uniteCourte(uniteTemps: "jours" | "heures"): string {
  return uniteTemps === "heures" ? "h" : "j";
}

function NoeudEtapeGraphe({ data, selected }: NodeProps<NoeudEtape>) {
  const competences = competencesDe(data.competencesTexte);
  return (
    <div
      className={cn(
        "cursor-pointer rounded-lg border bg-card px-3 py-2 text-xs text-foreground",
        selected ? "border-primary ring-2 ring-primary" : "border-border",
      )}
      style={{ width: LARGEUR_NOEUD }}
    >
      <Handle type="target" position={Position.Left} />
      <div className="truncate font-medium">{data.nom || data.id || "(étape sans nom)"}</div>
      <div className="truncate font-mono text-muted-foreground">
        {competences.length > 0 ? competences.join(", ") : "aucune compétence"}
      </div>
      <div className="text-muted-foreground">
        {data.dureeParPiece ? `${data.dureeParPiece} ${data.dureeUnite ?? ""} / pièce` : "durée ?"}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const TYPES_NOEUD = { etape: NoeudEtapeGraphe };

function noeudsInitiaux(etapes: EtapeProcessus[]): { noeuds: NoeudEtape[]; aretes: Edge[] } {
  const aretesBrutes = etapes.flatMap((e) =>
    e.predecesseurs.map((p) => ({ source: p, target: e.id })),
  );
  const positions = calculerPositions(
    etapes.map((e) => e.id),
    aretesBrutes,
  );
  const noeuds: NoeudEtape[] = etapes.map((e) => ({
    id: e.id,
    type: "etape",
    position: positions.get(e.id) ?? { x: 0, y: 0 },
    data: {
      id: e.id,
      nom: e.nom ?? "",
      competencesTexte: e.competences.join(", "),
      dureeParPiece: String(e.duree_par_piece),
    },
  }));
  const aretes: Edge[] = aretesBrutes.map((a, i) => ({
    id: `${a.source}->${a.target}-${i}`,
    source: a.source,
    target: a.target,
    type: "smoothstep",
    markerEnd: { type: MarkerType.ArrowClosed },
    style: { stroke: "var(--muted-foreground)" },
  }));
  return { noeuds, aretes };
}

// Les arêtes relient des ids de nœuds React Flow ; une étape renommée garde son id de nœud, donc
// on retraduit chaque extrémité vers le code d'étape actuel au moment d'enregistrer.
function construireEtapes(noeuds: NoeudEtape[], aretes: Edge[]): EtapeProcessus[] {
  const codeParNoeud = new Map(noeuds.map((n) => [n.id, n.data.id]));
  return noeuds.map((n) => ({
    id: n.data.id,
    nom: n.data.nom.trim() || null,
    competences: competencesDe(n.data.competencesTexte),
    predecesseurs: aretes
      .filter((a) => a.target === n.id)
      .map((a) => codeParNoeud.get(a.source) ?? a.source),
    duree_par_piece: Number(n.data.dureeParPiece),
  }));
}

/**
 * Éditeur du processus unique d'un atelier : les étapes (nom, compétences requises, durée par
 * pièce) et leur enchaînement. `ReactFlowProvider` séparé du corps éditable — `useReactFlow`
 * (suppression depuis l'inspecteur, « Réorganiser ») exige d'être monté sous le provider.
 */
export function EditeurProcessus(props: {
  instanceId: string;
  etapes: EtapeProcessus[];
  uniteTemps: "jours" | "heures";
  competencesAtelier: string[];
  /** Tâches de l'atelier (une entrée par nom de tâche) : le nom d'une étape se choisit dans cette liste. */
  tachesAtelier: EtapeProcessus[];
  onEnregistre: () => void;
  onAnnuler: () => void;
}) {
  return (
    <ReactFlowProvider>
      <CorpsEditeurProcessus {...props} />
    </ReactFlowProvider>
  );
}

function CorpsEditeurProcessus({
  instanceId,
  etapes,
  uniteTemps,
  competencesAtelier,
  tachesAtelier,
  onEnregistre,
  onAnnuler,
}: {
  instanceId: string;
  etapes: EtapeProcessus[];
  uniteTemps: "jours" | "heures";
  competencesAtelier: string[];
  tachesAtelier: EtapeProcessus[];
  onEnregistre: () => void;
  onAnnuler: () => void;
}) {
  const definir = useDefinirProcessus();
  const erreurApi = definir.error as PrismeAPIError | null;

  const initial = useMemo(() => noeudsInitiaux(etapes), [etapes]);
  const [nodes, setNodes, onNodesChange] = useNodesState<NoeudEtape>(initial.noeuds);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initial.aretes);
  const [noeudSelectionneId, setNoeudSelectionneId] = useState<string | null>(null);
  const { deleteElements, fitView } = useReactFlow();

  // L'unité ne vit pas dans les données d'une étape : injectée à l'affichage seulement.
  const nodesAffiches = useMemo(
    () => nodes.map((n) => ({ ...n, data: { ...n.data, dureeUnite: uniteCourte(uniteTemps) } })),
    [nodes, uniteTemps],
  );

  const onConnect = useCallback(
    (params: Connection) => {
      if (params.source === params.target) return;
      setEdges((eds) =>
        addEdge(
          {
            id: `${params.source}->${params.target}-${crypto.randomUUID()}`,
            ...params,
            type: "smoothstep",
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: "var(--muted-foreground)" },
          },
          eds,
        ),
      );
    },
    [setEdges],
  );

  function ajouterEtape() {
    const id = crypto.randomUUID();
    const decalageX =
      nodes.length > 0 ? Math.max(...nodes.map((n) => n.position.x)) + LARGEUR_NOEUD + 60 : 0;
    const nouveau: NoeudEtape = {
      id,
      type: "etape",
      position: { x: decalageX, y: 0 },
      data: { id: "", nom: "", competencesTexte: "", dureeParPiece: "" },
    };
    setNodes((ns) => [...ns, nouveau]);
    setNoeudSelectionneId(id);
    // Sans ça, la nouvelle étape peut atterrir hors du cadrage actuel : l'inspecteur s'ouvrirait
    // sur une étape invisible à l'écran.
    requestAnimationFrame(() => fitView());
  }

  function reorganiser() {
    const positions = calculerPositions(
      nodes.map((n) => n.id),
      edges.map((e) => ({ source: e.source, target: e.target })),
    );
    setNodes((ns) => ns.map((n) => ({ ...n, position: positions.get(n.id) ?? n.position })));
    requestAnimationFrame(() => fitView());
  }

  function patchNoeud(id: string, patch: Partial<DonneesNoeudEtape>) {
    setNodes((ns) => ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n)));
  }

  const noeudSelectionne = nodes.find((n) => n.id === noeudSelectionneId) ?? null;

  // Vérifié ici avant envoi pour guider la saisie ; le serveur revalide tout (cycles compris).
  const erreursNoeud = useMemo(() => {
    const occurrences = new Map<string, number>();
    for (const n of nodes) occurrences.set(n.data.id, (occurrences.get(n.data.id) ?? 0) + 1);
    const erreurs = new Map<string, string>();
    for (const n of nodes) {
      const duree = Number(n.data.dureeParPiece);
      if (!MOTIF_IDENTIFIANT.test(n.data.id)) {
        erreurs.set(
          n.id,
          "Code requis : lettres, chiffres, « _ » ou « - », 40 caractères au plus.",
        );
      } else if ((occurrences.get(n.data.id) ?? 0) > 1) {
        erreurs.set(n.id, "Ce code est déjà utilisé par une autre étape.");
      } else if (competencesDe(n.data.competencesTexte).length === 0) {
        erreurs.set(n.id, "Indiquez au moins une compétence requise.");
      } else if (!Number.isInteger(duree) || duree < 1) {
        erreurs.set(n.id, "Indiquez une durée par pièce entière, d'au moins 1.");
      }
    }
    return erreurs;
  }, [nodes]);

  const peutEnregistrer = nodes.length > 0 && erreursNoeud.size === 0;

  function enregistrer() {
    definir.mutate(
      { instanceId, etapes: construireEtapes(nodes, edges) },
      { onSuccess: onEnregistre },
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-2">
          <Button type="button" size="sm" variant="outline" onClick={ajouterEtape}>
            <Plus className="mr-1.5 h-3.5 w-3.5" /> Étape
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={reorganiser}>
            <Wand2 className="mr-1.5 h-3.5 w-3.5" /> Réorganiser
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Glissez du bord droit d'une étape vers une autre pour indiquer l'ordre.
        </p>
      </div>

      <div className="flex h-105 gap-2">
        <div className="min-w-0 flex-1 rounded-lg border border-border">
          <ReactFlow
            nodes={nodesAffiches}
            edges={edges}
            nodeTypes={TYPES_NOEUD}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_event, node) => setNoeudSelectionneId(node.id)}
            onPaneClick={() => setNoeudSelectionneId(null)}
            fitView
            proOptions={{ hideAttribution: true }}
          >
            <Background />
            <Controls />
          </ReactFlow>
        </div>
        {noeudSelectionne && (
          <InspecteurEtapeProcessus
            donnees={noeudSelectionne.data}
            erreur={erreursNoeud.get(noeudSelectionne.id) ?? null}
            uniteTemps={uniteTemps}
            competencesAtelier={competencesAtelier}
            tachesAtelier={tachesAtelier}
            nomsDejaPris={nodes.filter((n) => n.id !== noeudSelectionne.id).map((n) => n.data.nom)}
            onPatch={(patch) => patchNoeud(noeudSelectionne.id, patch)}
            onSupprimer={() => deleteElements({ nodes: [{ id: noeudSelectionne.id }] })}
            onFermer={() => setNoeudSelectionneId(null)}
          />
        )}
      </div>

      {nodes.length === 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-400">
          <AlertCircle className="h-4 w-4 shrink-0" /> Ajoutez au moins une étape.
        </div>
      )}
      {nodes.length > 0 && erreursNoeud.size > 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-400">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {erreursNoeud.size === 1
            ? "Une étape est incomplète : cliquez dessus pour la compléter."
            : `${erreursNoeud.size} étapes sont incomplètes : cliquez dessus pour les compléter.`}
        </div>
      )}

      {erreurApi && <ErreursAPI erreur={erreurApi} />}

      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onAnnuler} disabled={definir.isPending}>
          <X className="mr-1.5 h-3.5 w-3.5" /> Annuler
        </Button>
        <Button size="sm" onClick={enregistrer} disabled={!peutEnregistrer || definir.isPending}>
          {definir.isPending ? "Enregistrement..." : "Enregistrer le processus"}
        </Button>
      </div>
    </div>
  );
}

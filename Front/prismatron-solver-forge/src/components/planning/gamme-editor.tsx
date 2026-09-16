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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import {
  useCreerGamme,
  useModifierGamme,
  type EtapeGamme,
  type GammeProduit,
  type PrismeAPIError,
} from "@/integrations/prisme";
import { ErreursAPI } from "@/components/ingestion/ingestion-dialog";
import { LARGEUR_NOEUD, calculerPositions } from "./flow-graph-layout";
import { InspecteurEtapeGamme } from "./inspecteur-etape-gamme";

export type DonneesNoeudEtape = {
  id: string;
  competencesTexte: string; // libre, séparées par des virgules — même patron que
  // RessourceLigne.competencesTexte dans ingestion-dialog.tsx
  dureeNominale: string;
};

type NoeudEtape = Node<DonneesNoeudEtape, "etape">;

const MOTIF_IDENTIFIANT = /^[A-Za-z0-9_-]{1,64}$/;

function competencesDe(texte: string): string[] {
  return texte
    .split(",")
    .map((c) => c.trim())
    .filter(Boolean);
}

// Nœud personnalisé dédié à la gamme — même raisonnement de style que
// NoeudTacheEdition (flow-graph-editor.tsx), forme de données différente.
function NoeudEtapeGraphe({ data, selected }: NodeProps<NoeudEtape>) {
  const competences = competencesDe(data.competencesTexte);
  return (
    <div
      className={cn(
        "cursor-pointer rounded-lg border bg-card px-3 py-2 text-xs font-mono text-foreground",
        selected ? "border-primary ring-2 ring-primary" : "border-border",
      )}
      style={{ width: LARGEUR_NOEUD }}
    >
      <Handle type="target" position={Position.Left} />
      <div className="truncate">{data.id || "(id manquant)"}</div>
      <div className="truncate text-muted-foreground">
        {competences.length > 0 ? competences.join(", ") : "aucune compétence"}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const TYPES_NOEUD = { etape: NoeudEtapeGraphe };

function noeudsInitiaux(gamme: GammeProduit | undefined): { noeuds: NoeudEtape[]; aretes: Edge[] } {
  if (!gamme || gamme.etapes.length === 0) {
    return { noeuds: [], aretes: [] };
  }
  const aretesBrutes = gamme.etapes.flatMap((e) =>
    e.predecesseurs.map((p) => ({ source: p, target: e.id })),
  );
  const positions = calculerPositions(
    gamme.etapes.map((e) => e.id),
    aretesBrutes,
  );
  const noeuds: NoeudEtape[] = gamme.etapes.map((e) => ({
    id: e.id,
    type: "etape",
    position: positions.get(e.id) ?? { x: 0, y: 0 },
    data: {
      id: e.id,
      competencesTexte: e.competences.join(", "),
      dureeNominale: e.duree_nominale != null ? String(e.duree_nominale) : "",
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

function construireEtapes(noeuds: NoeudEtape[], aretes: Edge[]): EtapeGamme[] {
  return noeuds.map((n) => ({
    id: n.data.id,
    competences: competencesDe(n.data.competencesTexte),
    predecesseurs: aretes.filter((a) => a.target === n.id).map((a) => a.source),
    duree_nominale: n.data.dureeNominale ? Number(n.data.dureeNominale) : null,
  }));
}

// Point d'entrée : `ReactFlowProvider` séparé du corps éditable — même raison
// que flow-graph-editor.tsx (useReactFlow, ici pour le bouton de suppression
// de l'inspecteur et "Réorganiser", exige d'être monté sous le provider).
export function GammeEditor({
  gamme,
  onEnregistre,
  onAnnuler,
}: {
  /** Absent = création d'une nouvelle gamme ; présent = édition en place. */
  gamme?: GammeProduit;
  onEnregistre: () => void;
  onAnnuler: () => void;
}) {
  return (
    <ReactFlowProvider>
      <EditeurGamme gamme={gamme} onEnregistre={onEnregistre} onAnnuler={onAnnuler} />
    </ReactFlowProvider>
  );
}

function EditeurGamme({
  gamme,
  onEnregistre,
  onAnnuler,
}: {
  gamme?: GammeProduit;
  onEnregistre: () => void;
  onAnnuler: () => void;
}) {
  const creer = useCreerGamme();
  const modifier = useModifierGamme();
  const mutationEnCours = gamme ? modifier.isPending : creer.isPending;
  const erreur = (gamme ? modifier.error : creer.error) as PrismeAPIError | null;

  const [produit, setProduit] = useState(gamme?.produit ?? "");
  const [nom, setNom] = useState(gamme?.nom ?? "");

  const initial = useMemo(() => noeudsInitiaux(gamme), [gamme]);
  const [nodes, setNodes, onNodesChange] = useNodesState<NoeudEtape>(initial.noeuds);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initial.aretes);
  const [noeudSelectionneId, setNoeudSelectionneId] = useState<string | null>(null);
  const { deleteElements, fitView } = useReactFlow();

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
      data: { id: "", competencesTexte: "", dureeNominale: "" },
    };
    setNodes((ns) => [...ns, nouveau]);
    setNoeudSelectionneId(id);
    // Sans ça, la nouvelle étape peut atterrir hors du cadrage actuel (la vue reste centrée sur
    // les étapes précédentes) — l'inspecteur s'ouvre alors sur une étape invisible à l'écran,
    // donnant l'impression trompeuse qu'une étape déjà présente est en erreur.
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

  // Vérification côté client avant envoi : motif/unicité de l'id (même piège
  // que flow-graph-editor.tsx) et présence d'au moins une compétence — le
  // backend l'exige aussi (`EtapeGammeRequete.competences`, min_length=1),
  // autant l'éviter avant un aller-retour réseau.
  const erreursNoeud = useMemo(() => {
    const occurrences = new Map<string, number>();
    for (const n of nodes) occurrences.set(n.data.id, (occurrences.get(n.data.id) ?? 0) + 1);
    const erreurs = new Map<string, string>();
    for (const n of nodes) {
      if (!MOTIF_IDENTIFIANT.test(n.data.id)) {
        erreurs.set(n.id, "id requis : lettres/chiffres/_/- uniquement, 1 à 64 caractères");
      } else if ((occurrences.get(n.data.id) ?? 0) > 1) {
        erreurs.set(n.id, "id déjà utilisé par une autre étape");
      } else if (competencesDe(n.data.competencesTexte).length === 0) {
        erreurs.set(n.id, "au moins une compétence requise");
      }
    }
    return erreurs;
  }, [nodes]);

  const peutEnregistrer = produit.trim().length > 0 && nodes.length > 0 && erreursNoeud.size === 0;

  function enregistrer() {
    const etapes = construireEtapes(nodes, edges);
    if (gamme) {
      modifier.mutate(
        { gammeId: gamme.gamme_id, produit: produit.trim(), etapes, nom: nom.trim() || undefined },
        { onSuccess: onEnregistre },
      );
    } else {
      creer.mutate(
        { produit: produit.trim(), etapes, nom: nom.trim() || undefined },
        { onSuccess: onEnregistre },
      );
    }
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label>Produit</Label>
          <Input
            value={produit}
            onChange={(e) => setProduit(e.target.value)}
            placeholder="ex: Vanne V12"
          />
        </div>
        <div className="space-y-1">
          <Label>Nom (optionnel)</Label>
          <Input
            value={nom}
            onChange={(e) => setNom(e.target.value)}
            placeholder="ex: Gamme vanne V12"
          />
        </div>
      </div>

      <div className="flex items-center justify-between gap-2">
        <div className="flex gap-2">
          <Button type="button" size="sm" variant="outline" onClick={ajouterEtape}>
            <Plus className="mr-1.5 h-3.5 w-3.5" /> Étape
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={reorganiser}>
            <Wand2 className="mr-1.5 h-3.5 w-3.5" /> Réorganiser
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Glisser depuis le bord droit d'une étape vers une autre pour créer une précédence.
        </p>
      </div>

      <div className="flex h-[420px] gap-2">
        <div className="min-w-0 flex-1 rounded-lg border border-border">
          <ReactFlow
            nodes={nodes}
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
          <InspecteurEtapeGamme
            donnees={noeudSelectionne.data}
            idInvalide={erreursNoeud.get(noeudSelectionne.id) ?? null}
            onPatch={(patch) => patchNoeud(noeudSelectionne.id, patch)}
            onSupprimer={() => deleteElements({ nodes: [{ id: noeudSelectionne.id }] })}
            onFermer={() => setNoeudSelectionneId(null)}
          />
        )}
      </div>

      {nodes.length === 0 && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" /> Ajoutez au moins une étape.
        </div>
      )}

      {erreur && <ErreursAPI erreur={erreur} />}

      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onAnnuler} disabled={mutationEnCours}>
          <X className="mr-1.5 h-3.5 w-3.5" /> Annuler
        </Button>
        <Button size="sm" onClick={enregistrer} disabled={!peutEnregistrer || mutationEnCours}>
          {mutationEnCours ? "Enregistrement..." : "Enregistrer"}
        </Button>
      </div>
    </div>
  );
}

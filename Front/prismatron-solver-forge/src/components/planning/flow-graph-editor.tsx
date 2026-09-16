import { useCallback, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
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
import { Pencil, Wand2, AlertCircle, X, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  useModifierInstance,
  prismeKeys,
  type Contrainte,
  type InstanceDetail,
  type InstanceTRCO,
  type PrismeAPIError,
  type Tache,
} from "@/integrations/prisme";
import { ErreursAPI } from "@/components/ingestion/ingestion-dialog";
import { FlowGraph } from "./flow-graph";
import { LARGEUR_NOEUD, calculerPositions } from "./flow-graph-layout";
import { InspecteurTache } from "./inspecteur-tache";

export type CompatibiliteLigne = { clef: string; ressource: string; duree: string };

export type DonneesNoeudEdition = {
  dslId: string;
  nom?: string;
  produit?: string;
  priorite?: number;
  // Un id vide/dupliqué n'est bloquant que pour une tâche nouvellement créée
  // dans cette session d'édition — l'id d'une tâche déjà existante reste
  // figé (renommer une tâche en cascade sur toutes ses contraintes est hors
  // périmètre v1, voir CLAUDE.md/plan).
  estNouveau: boolean;
  compatibilites: CompatibiliteLigne[];
};

type NoeudEdition = Node<DonneesNoeudEdition, "tache-edition">;

const MOTIF_IDENTIFIANT = /^[A-Za-z0-9_-]{1,64}$/;

const PALETTE_PRODUIT = [
  "#f59e0b",
  "#3b82f6",
  "#22c55e",
  "#a855f7",
  "#ec4899",
  "#14b8a6",
  "#ef4444",
  "#84cc16",
];

// Hash déterministe (style djb2) — juste assez pour répartir des couleurs
// stables par valeur de `produit`, sans registre ni légende à gérer.
function couleurProduit(produit?: string): string | undefined {
  if (!produit) return undefined;
  let hash = 5381;
  for (let i = 0; i < produit.length; i++) {
    hash = (hash * 33 + produit.charCodeAt(i)) >>> 0;
  }
  return PALETTE_PRODUIT[hash % PALETTE_PRODUIT.length];
}

// Nœud personnalisé dédié à l'édition (pas de réutilisation de `NoeudTache`
// de flow-graph.tsx : forme de `data` différente — dslId éditable, accent
// produit, état "sélectionné"). Mêmes poignées gauche/droite que le graphe
// en lecture seule, pour rester cohérent avec la mise en page dagre (LR).
function NoeudTacheEdition({ data, selected }: NodeProps<NoeudEdition>) {
  const compte = data.compatibilites.filter((c) => c.ressource).length;
  const accent = couleurProduit(data.produit);
  return (
    <div
      className={cn(
        "cursor-pointer rounded-lg border bg-card px-3 py-2 text-xs font-mono text-foreground",
        selected ? "border-primary ring-2 ring-primary" : "border-border",
      )}
      style={{
        width: LARGEUR_NOEUD,
        borderLeftWidth: 4,
        borderLeftColor: accent ?? "var(--border)",
      }}
    >
      <Handle type="target" position={Position.Left} />
      <div className="truncate">{data.dslId || "(id manquant)"}</div>
      {data.nom && <div className="truncate text-muted-foreground">{data.nom}</div>}
      <div className="truncate text-muted-foreground">
        {compte > 0 ? `${compte} ressource${compte > 1 ? "s" : ""}` : "aucune ressource"}
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

const TYPES_NOEUD = { "tache-edition": NoeudTacheEdition };

// Types de contrainte que ce graphe ne gère pas (restent édités via le
// formulaire `ingestion-dialog.tsx`) mais qui peuvent référencer une tâche —
// utilisé pour bloquer la suppression d'un nœud plutôt que de les propager
// en silence (dsl/schema/contraintes.py, §4.2).
const LABEL_CONTRAINTE_NON_GEREE: Partial<Record<Contrainte["type"], string>> = {
  echeance: "échéance",
  competence_requise: "compétence requise",
  taille_lot: "taille de lot",
  changement_serie: "changement de série",
  incompatibilite: "incompatibilité",
};

function contraintesBloquantesParTache(contraintes: Contrainte[]): Map<string, string[]> {
  const map = new Map<string, string[]>();
  function ajouter(tacheId: string, label: string) {
    map.set(tacheId, [...(map.get(tacheId) ?? []), label]);
  }
  for (const c of contraintes) {
    switch (c.type) {
      case "echeance":
      case "competence_requise":
      case "taille_lot":
        ajouter(c.tache, LABEL_CONTRAINTE_NON_GEREE[c.type]!);
        break;
      case "changement_serie":
        ajouter(c.tache_avant, LABEL_CONTRAINTE_NON_GEREE.changement_serie!);
        ajouter(c.tache_apres, LABEL_CONTRAINTE_NON_GEREE.changement_serie!);
        break;
      case "incompatibilite":
        ajouter(c.tache, LABEL_CONTRAINTE_NON_GEREE.incompatibilite!);
        ajouter(c.tache_incompatible, LABEL_CONTRAINTE_NON_GEREE.incompatibilite!);
        break;
      default:
        break;
    }
  }
  return map;
}

function noeudsInitiaux(instance: InstanceDetail): { noeuds: NoeudEdition[]; aretes: Edge[] } {
  const compatParTache = new Map<string, CompatibiliteLigne[]>();
  for (const c of instance.contraintes) {
    if (c.type !== "compatibilite_ressource_tache") continue;
    const liste = compatParTache.get(c.tache) ?? [];
    liste.push({ clef: crypto.randomUUID(), ressource: c.ressource, duree: String(c.duree) });
    compatParTache.set(c.tache, liste);
  }

  const aretesBrutes = instance.contraintes
    .filter((c): c is Contrainte & { type: "precedence" } => c.type === "precedence")
    .map((c) => ({ source: c.avant, target: c.apres }));

  const positions = calculerPositions(
    instance.taches.map((t) => t.id),
    aretesBrutes,
  );

  const noeuds: NoeudEdition[] = instance.taches.map((t) => ({
    id: t.id,
    type: "tache-edition",
    position: positions.get(t.id) ?? { x: 0, y: 0 },
    data: {
      dslId: t.id,
      nom: t.nom,
      produit: t.produit,
      priorite: t.priorite,
      estNouveau: false,
      compatibilites: compatParTache.get(t.id) ?? [],
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

// Reconstruction complète (§ `PUT /ingestion/{instance_id}` exige l'instance
// entière, pas un patch) — même logique que `construireInstance` de
// ingestion-dialog.tsx : ressources/objectifs inchangés, et tout type de
// contrainte que ce graphe ne gère pas repassé tel quel.
function construireInstanceDepuisGraphe(
  instance: InstanceDetail,
  noeuds: NoeudEdition[],
  aretes: Edge[],
): InstanceTRCO {
  const idParNoeud = new Map(noeuds.map((n) => [n.id, n.data.dslId]));

  const taches: Tache[] = noeuds.map((n) => ({
    id: n.data.dslId,
    ...(n.data.nom ? { nom: n.data.nom } : {}),
    ...(n.data.produit ? { produit: n.data.produit } : {}),
    ...(n.data.priorite ? { priorite: n.data.priorite } : {}),
  }));

  const precedences: Contrainte[] = aretes.map((a) => ({
    type: "precedence" as const,
    avant: idParNoeud.get(a.source) ?? a.source,
    apres: idParNoeud.get(a.target) ?? a.target,
  }));

  const compatibilites: Contrainte[] = noeuds.flatMap((n) =>
    n.data.compatibilites
      .filter((c) => c.ressource)
      .map((c) => ({
        type: "compatibilite_ressource_tache" as const,
        tache: n.data.dslId,
        ressource: c.ressource,
        duree: Number(c.duree),
      })),
  );

  const contraintesNonGerees = instance.contraintes.filter(
    (c) => c.type !== "precedence" && c.type !== "compatibilite_ressource_tache",
  );

  return {
    taches,
    ressources: instance.ressources,
    contraintes: [...precedences, ...compatibilites, ...contraintesNonGerees],
    objectifs: instance.objectifs,
  };
}

// Canevas éditable proprement dit — composant séparé de `FlowGraphEditor`
// car `useReactFlow()` (bouton de suppression dans l'inspecteur, action
// "Réorganiser") exige d'être monté sous `<ReactFlowProvider>`.
function EditeurCanvas({
  instance,
  modifier,
  erreurModification,
  onAnnuler,
  onEnregistre,
}: {
  instance: InstanceDetail;
  modifier: ReturnType<typeof useModifierInstance>;
  erreurModification: PrismeAPIError | null;
  onAnnuler: () => void;
  onEnregistre: () => void;
}) {
  const initial = useMemo(() => noeudsInitiaux(instance), [instance]);
  const [nodes, setNodes, onNodesChange] = useNodesState<NoeudEdition>(initial.noeuds);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initial.aretes);
  const [noeudSelectionneId, setNoeudSelectionneId] = useState<string | null>(null);
  const [messageBlocage, setMessageBlocage] = useState<string | null>(null);
  const { deleteElements, fitView } = useReactFlow();

  const contraintesBloquantes = useMemo(
    () => contraintesBloquantesParTache(instance.contraintes),
    [instance.contraintes],
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

  // Suppr/Retour (et le bouton "Supprimer cette tâche" de l'inspecteur, via
  // `deleteElements`) passent tous les deux par ce garde-fou — une tâche
  // encore référencée par une contrainte que ce graphe ne gère pas est
  // retirée du lot plutôt que supprimée en silence (voir §4.2/Étape 4 du plan).
  const onBeforeDelete = useCallback(
    async ({
      nodes: aSupprimer,
      edges: aretesASupprimer,
    }: {
      nodes: NoeudEdition[];
      edges: Edge[];
    }) => {
      const bloques = new Set<string>();
      const messages: string[] = [];
      for (const n of aSupprimer) {
        const labels = contraintesBloquantes.get(n.data.dslId);
        if (labels && labels.length > 0) {
          bloques.add(n.id);
          messages.push(`${n.data.dslId || n.id} (${labels.join(", ")})`);
        }
      }
      setMessageBlocage(
        messages.length > 0 ? `Suppression bloquée pour : ${messages.join(" ; ")}` : null,
      );
      return {
        nodes: aSupprimer.filter((n) => !bloques.has(n.id)),
        edges: aretesASupprimer,
      };
    },
    [contraintesBloquantes],
  );

  function ajouterTache() {
    const id = crypto.randomUUID();
    const decalageX =
      nodes.length > 0 ? Math.max(...nodes.map((n) => n.position.x)) + LARGEUR_NOEUD + 60 : 0;
    const nouveau: NoeudEdition = {
      id,
      type: "tache-edition",
      position: { x: decalageX, y: 0 },
      data: { dslId: "", estNouveau: true, compatibilites: [] },
    };
    setNodes((ns) => [...ns, nouveau]);
    setNoeudSelectionneId(id);
    // Sans ça, la nouvelle tâche peut atterrir hors du cadrage actuel (la vue reste centrée sur
    // les tâches précédentes) — l'inspecteur s'ouvre alors sur une tâche invisible à l'écran,
    // donnant l'impression trompeuse qu'une tâche déjà présente est en erreur.
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

  function patchNoeud(id: string, patch: Partial<DonneesNoeudEdition>) {
    setNodes((ns) => ns.map((n) => (n.id === id ? { ...n, data: { ...n.data, ...patch } } : n)));
  }

  const noeudSelectionne = nodes.find((n) => n.id === noeudSelectionneId) ?? null;

  // Vérification côté client avant envoi — seul l'id (motif + unicité) est
  // pré-validé ici : c'est l'erreur la plus fréquente et la plus facile à
  // éviter ; une tâche sans ressource compatible reste volontairement
  // envoyée au serveur (§6.7 la rejette avec un 422 explicite, affiché via
  // `ErreursAPI` — scénario de vérification du plan).
  const erreursId = useMemo(() => {
    const occurrences = new Map<string, number>();
    for (const n of nodes) occurrences.set(n.data.dslId, (occurrences.get(n.data.dslId) ?? 0) + 1);
    const erreurs = new Map<string, string>();
    for (const n of nodes) {
      if (!MOTIF_IDENTIFIANT.test(n.data.dslId)) {
        erreurs.set(n.id, "id requis : lettres/chiffres/_/- uniquement, 1 à 64 caractères");
      } else if ((occurrences.get(n.data.dslId) ?? 0) > 1) {
        erreurs.set(n.id, "id déjà utilisé par une autre tâche");
      }
    }
    return erreurs;
  }, [nodes]);

  const peutEnregistrer = erreursId.size === 0 && nodes.length > 0;

  function enregistrer() {
    const instanceComplete = construireInstanceDepuisGraphe(instance, nodes, edges);
    modifier.mutate(
      { instanceId: instance.instance_id, instance: instanceComplete },
      { onSuccess: onEnregistre },
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex gap-2">
          <Button type="button" size="sm" variant="outline" onClick={ajouterTache}>
            <Plus className="mr-1.5 h-3.5 w-3.5" /> Tâche
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={reorganiser}>
            <Wand2 className="mr-1.5 h-3.5 w-3.5" /> Réorganiser
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Glisser depuis le bord droit d'une tâche vers une autre pour créer une précédence.
        </p>
      </div>

      <div className="flex flex-col gap-2 sm:h-[500px] sm:flex-row">
        {/* `flex-1` seulement à partir de `sm:` — sur mobile (ligne sans
        hauteur définie), `flex-basis: 0%` de flex-1 court-circuiterait la
        hauteur explicite ci-dessous (le canevas s'écraserait à ~0px, faute
        d'espace disponible à distribuer par flex-grow). */}
        <div className="h-[350px] min-w-0 rounded-lg border border-border sm:h-auto sm:flex-1">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={TYPES_NOEUD}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onBeforeDelete={onBeforeDelete}
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
          <InspecteurTache
            donnees={noeudSelectionne.data}
            ressourcesDisponibles={instance.ressources}
            idInvalide={erreursId.get(noeudSelectionne.id) ?? null}
            onPatch={(patch) => patchNoeud(noeudSelectionne.id, patch)}
            onSupprimer={() => deleteElements({ nodes: [{ id: noeudSelectionne.id }] })}
            onFermer={() => setNoeudSelectionneId(null)}
          />
        )}
      </div>

      {messageBlocage && (
        <div className="flex items-center gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" /> {messageBlocage}
        </div>
      )}

      {erreurModification && <ErreursAPI erreur={erreurModification} />}

      <div className="flex justify-end gap-2">
        <Button variant="outline" size="sm" onClick={onAnnuler} disabled={modifier.isPending}>
          <X className="mr-1.5 h-3.5 w-3.5" /> Annuler
        </Button>
        <Button size="sm" onClick={enregistrer} disabled={!peutEnregistrer || modifier.isPending}>
          {modifier.isPending ? "Enregistrement..." : "Enregistrer"}
        </Button>
      </div>
    </div>
  );
}

// Point d'entrée de l'onglet "Flux" — bascule entre le graphe en lecture
// seule (FlowGraph) et le canevas éditable, même pattern que l'édition
// inline des objectifs dans instances.tsx (enEdition local, mutation +
// invalidation React Query au succès).
export function FlowGraphEditor({ instance }: { instance: InstanceDetail }) {
  const queryClient = useQueryClient();
  const modifier = useModifierInstance();
  const [enEdition, setEnEdition] = useState(false);

  const erreurModification = modifier.error as PrismeAPIError | null;

  function commencerEdition() {
    modifier.reset();
    setEnEdition(true);
  }

  function annuler() {
    modifier.reset();
    setEnEdition(false);
  }

  if (!enEdition) {
    return (
      <div className="space-y-2">
        <div className="flex justify-end">
          <Button size="sm" variant="outline" onClick={commencerEdition}>
            <Pencil className="mr-1.5 h-3.5 w-3.5" /> Modifier
          </Button>
        </div>
        <FlowGraph taches={instance.taches} contraintes={instance.contraintes} />
      </div>
    );
  }

  return (
    <ReactFlowProvider>
      <EditeurCanvas
        instance={instance}
        modifier={modifier}
        erreurModification={erreurModification}
        onAnnuler={annuler}
        onEnregistre={() => {
          queryClient.invalidateQueries({ queryKey: prismeKeys.instance(instance.instance_id) });
          queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
          setEnEdition(false);
        }}
      />
    </ReactFlowProvider>
  );
}

import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Code2,
  Cpu,
  Eye,
  FolderKanban,
  GitCompareArrows,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { PageHeader, EmptyState } from "@/components/app-page";
import { FlowGraphEditor } from "@/components/planning/flow-graph-editor";
import {
  IngestionDialog,
  SectionObjectifs,
  construireObjectifs,
  objectifVersLigne,
  type ObjectifLigne,
} from "@/components/ingestion/ingestion-dialog";
import {
  prismeKeys,
  useInstances,
  useInstance,
  useLabelsInstances,
  useSupprimerInstance,
  useModifierObjectifs,
  useSolveurs,
  useCodeSourceSolveur,
  useJobsGeneration,
  useComparaisonScenarios,
  useAjouterCommande,
  useCommandesInstance,
  usePropositionsSupervision,
  PrismeAPIError,
  type Contrainte,
  type InstanceDetail,
  type InstanceInfo,
  type Objectif,
  type StatutCommande,
} from "@/integrations/prisme";
import { formatDuree, formatDureeCourte } from "@/lib/unite-duree";
import { BadgeTypeSignal } from "./supervision";

export const Route = createFileRoute("/_authenticated/instances")({
  head: () => ({ meta: [{ title: "Instances — PRISME" }] }),
  component: InstancesPage,
});

function InstancesPage() {
  const [dialogOuvert, setDialogOuvert] = useState(false);
  const [aSupprimer, setASupprimer] = useState<string | null>(null);
  const [aVoir, setAVoir] = useState<string | null>(null);
  // Instance complète à éditer en place dans IngestionDialog (bouton
  // "Modifier", ouvert depuis DialogDetailInstance qui l'a déjà chargée en
  // entier — pas de fetch séparé).
  const [instanceAModifier, setInstanceAModifier] = useState<InstanceDetail | null>(null);
  // Instance servant de point de départ pour un nouveau scénario comparatif
  // (bouton "Créer un scénario", onglet Scénarios de DialogDetailInstance) —
  // même mécanisme qu'instanceAModifier, jamais les deux en même temps.
  const [instanceScenarioDeBase, setInstanceScenarioDeBase] = useState<InstanceDetail | null>(null);
  const { data: instances, isLoading } = useInstances();
  const { data: jobsGeneration } = useJobsGeneration();
  const queryClient = useQueryClient();
  const supprimer = useSupprimerInstance();

  const instancesEnGeneration = new Set(
    (jobsGeneration ?? []).filter((j) => !j.termine).map((j) => j.instance_id),
  );

  // /supervision/instances ne relie pas les instances à leur source — le
  // label (nom de la source + rang de génération) vient de useLabelsInstances.
  const labels = useLabelsInstances();

  const boutonAllerDonnees = (
    <Button asChild className="bg-gradient-to-r from-primary to-accent">
      <Link to="/donnees">Aller à Données</Link>
    </Button>
  );

  function ouvrirConfirmation(instanceId: string) {
    supprimer.reset();
    setASupprimer(instanceId);
  }

  function confirmerSuppression() {
    if (!aSupprimer) return;
    supprimer.mutate(aSupprimer, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
        queryClient.invalidateQueries({ queryKey: prismeKeys.executions() });
        queryClient.invalidateQueries({ queryKey: prismeKeys.sources() });
        setASupprimer(null);
      },
    });
  }

  const erreurSuppression = supprimer.error as PrismeAPIError | null;

  // Seul point d'entrée vers le formulaire de création vierge (onglets Saisie
  // T-R-C-O/Import ERP/Fichier Excel/Fichiers CSV/CSV Local/Fichier JSON) —
  // sans instanceAEditer ni scenarioDeBase, IngestionDialog s'ouvre dans son
  // mode par défaut.
  function ouvrirCreationVierge() {
    setInstanceAModifier(null);
    setInstanceScenarioDeBase(null);
    setDialogOuvert(true);
  }

  function ouvrirModification(instance: InstanceDetail) {
    setAVoir(null);
    setInstanceAModifier(instance);
    setDialogOuvert(true);
  }

  function ouvrirCreationScenario(instance: InstanceDetail) {
    setAVoir(null);
    setInstanceScenarioDeBase(instance);
    setDialogOuvert(true);
  }

  function fermerDialogIngestion(open: boolean) {
    setDialogOuvert(open);
    if (!open) {
      setInstanceAModifier(null);
      setInstanceScenarioDeBase(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Instances"
        desc="Regroupez vos problèmes de planification, définitions DSL et solveurs générés en instances."
        action={
          <Button
            onClick={ouvrirCreationVierge}
            className="bg-gradient-to-r from-primary to-accent"
          >
            <Plus className="mr-2 h-4 w-4" /> Nouvelle instance
          </Button>
        }
      />

      {!isLoading && instances && instances.length === 0 && (
        <EmptyState
          icon={FolderKanban}
          title="Aucune instance pour l'instant"
          desc="Une instance regroupe votre DSL, vos solveurs générés, vos exécutions et votre historique d'audit. Ingérez des données brutes depuis la page Données pour générer votre première instance."
          action={boutonAllerDonnees}
        />
      )}

      {instances && instances.length > 0 && (
        <>
          <div className="glass overflow-hidden rounded-2xl">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Instance</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Client</TableHead>
                    <TableHead>Structure des contraintes</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {instances.map((instance) => {
                    const info = labels.get(instance.instance_id);
                    return (
                      <TableRow key={instance.instance_id}>
                        <TableCell className="font-mono text-xs" title={instance.instance_id}>
                          {info ? info.label : instance.instance_id}
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-col items-start gap-1">
                            <Badge variant="outline" className="text-xs">
                              {LABELS_CANAL_INGESTION[instance.canal_ingestion ?? ""] ?? "—"}
                            </Badge>
                            {info?.sourceId && (
                              <Link
                                to="/donnees"
                                search={{ source: info.sourceId }}
                                className="text-primary text-xs underline-offset-2 hover:underline"
                              >
                                {info.nomSource}
                              </Link>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>{instance.client_id}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="font-mono text-xs">
                            {instance.structure_contraintes}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          {instancesEnGeneration.has(instance.instance_id) ? (
                            <Badge variant="secondary" className="gap-1.5">
                              <Loader2 className="h-3 w-3 animate-spin" /> Génération en cours
                            </Badge>
                          ) : (
                            <Badge variant={instance.executee ? "secondary" : "outline"}>
                              {instance.executee ? "Exécutée" : "En attente"}
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-1">
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label="Voir l'instance"
                              onClick={() => setAVoir(instance.instance_id)}
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              aria-label="Supprimer l'instance"
                              onClick={() => ouvrirConfirmation(instance.instance_id)}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </div>
        </>
      )}

      <IngestionDialog
        key={instanceAModifier?.instance_id ?? instanceScenarioDeBase?.instance_id ?? "nouvelle"}
        open={dialogOuvert}
        onOpenChange={fermerDialogIngestion}
        instanceAEditer={instanceAModifier ?? undefined}
        scenarioDeBase={instanceScenarioDeBase ?? undefined}
      />

      <AlertDialog open={!!aSupprimer} onOpenChange={(open) => !open && setASupprimer(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cette instance ?</AlertDialogTitle>
            <AlertDialogDescription>
              Cette action supprime définitivement l'instance{" "}
              <span className="font-mono text-xs">{aSupprimer}</span>, ainsi que toutes les
              exécutions et plannings associés. Les solveurs enregistrés ne sont pas affectés —
              seule la source de données qui a éventuellement généré cette instance perd son lien de
              provenance vers elle. Cette action est irréversible.
            </AlertDialogDescription>
          </AlertDialogHeader>

          {erreurSuppression && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              <div className="flex items-center gap-2 font-medium">
                <AlertCircle className="h-4 w-4" /> Échec de la suppression
              </div>
              <p className="mt-1">{erreurSuppression.message}</p>
            </div>
          )}

          <AlertDialogFooter>
            <AlertDialogCancel disabled={supprimer.isPending}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmerSuppression}
              disabled={supprimer.isPending}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              {supprimer.isPending ? "Suppression..." : "Supprimer"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <DialogDetailInstance
        instanceId={aVoir}
        instances={instances ?? []}
        onOpenChange={(open) => !open && setAVoir(null)}
        onModifier={ouvrirModification}
        onCreerScenario={ouvrirCreationScenario}
      />
    </>
  );
}

// Canal d'ingestion (voir Types.InstanceInfo.canal_ingestion) — purement
// informatif, jamais lu par le solveur.
const LABELS_CANAL_INGESTION: Record<string, string> = {
  manuel: "Manuel",
  csv: "CSV",
  json: "JSON",
  api: "API",
  agent_ia: "Agent IA",
  scenario: "Scénario",
};

const LABELS_TYPE_CONTRAINTE: Record<Contrainte["type"], string> = {
  precedence: "Précédence",
  compatibilite_ressource_tache: "Compatibilité ressource-tâche",
  echeance: "Échéance",
  competence_requise: "Compétence requise",
  capacite: "Capacité",
  disponibilite_ressource: "Disponibilité ressource",
  incompatibilite: "Incompatibilité",
  taille_lot: "Taille de lot",
  changement_serie: "Changement de série",
};

// Phrases complètes, destinées à un lecteur métier — distinct du badge
// compact `structure_contraintes` (liste de types bruts) affiché ailleurs.
function decrireContrainte(c: Contrainte, uniteDuree?: string | null): string {
  const enJours = !uniteDuree || uniteDuree === "jours";
  switch (c.type) {
    case "precedence":
      return `La tâche ${c.avant} doit être terminée avant que ${c.apres} commence.`;
    case "compatibilite_ressource_tache":
      return `${c.tache} peut être réalisée sur ${c.ressource} (durée : ${formatDuree(c.duree, uniteDuree)}).`;
    case "echeance":
      return `${c.tache} doit être terminée au plus tard dans ${formatDuree(c.echeance, uniteDuree)}.`;
    case "competence_requise":
      return `${c.tache} exige la compétence « ${c.competence} ».`;
    case "capacite":
      return `${c.ressource} peut traiter jusqu'à ${c.capacite} opération${c.capacite > 1 ? "s" : ""} simultanément.`;
    case "disponibilite_ressource": {
      const parties: string[] = [];
      if (c.jours_indisponibles.length > 0) {
        const pluriel = c.jours_indisponibles.length > 1;
        parties.push(
          enJours
            ? `le${pluriel ? "s" : ""} jour${pluriel ? "s" : ""} ${c.jours_indisponibles.join(", ")}`
            : `${pluriel ? "aux dates" : "à la date"} ${c.jours_indisponibles
                .map((j) => formatDureeCourte(j, uniteDuree))
                .join(", ")}`,
        );
      }
      if (c.jours_semaine_indisponibles && c.jours_semaine_indisponibles.length > 0) {
        parties.push(
          `chaque semaine aux positions ${c.jours_semaine_indisponibles.join(", ")} (motif récurrent)`,
        );
      }
      // Évite un ".." si `parties` se termine déjà par l'abréviation pointée
      // d'une unité courte ("j.", "sem.") — jamais avec l'unité "jours" par
      // défaut, qui n'utilise pas `formatDureeCourte` ci-dessus.
      const phrase = `${c.ressource} est indisponible ${parties.join(" et ")}`;
      return phrase.endsWith(".") ? phrase : `${phrase}.`;
    }
    case "incompatibilite":
      return `${c.tache} et ${c.tache_incompatible} ne peuvent jamais partager la même ressource.`;
    case "taille_lot":
      return `${c.tache} doit produire entre ${c.lot_min} et ${c.lot_max} unités.`;
    case "changement_serie":
      return `Sur ${c.ressource}, faire suivre ${c.tache_avant} par ${c.tache_apres} exige un changement de série de ${formatDuree(c.duree_setup, uniteDuree)}.`;
  }
}

// Ordre pédagogique (noyau minimal d'abord, extensions ensuite) plutôt
// qu'alphabétique — voir dsl/schema/contraintes.py pour le même ordre.
const ORDRE_TYPE_CONTRAINTE: Contrainte["type"][] = [
  "precedence",
  "compatibilite_ressource_tache",
  "competence_requise",
  "echeance",
  "capacite",
  "disponibilite_ressource",
  "incompatibilite",
  "taille_lot",
  "changement_serie",
];

function SectionContraintes({
  contraintes,
  uniteDuree,
}: {
  contraintes: Contrainte[];
  uniteDuree?: string | null;
}) {
  if (contraintes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aucune contrainte déclarée pour cette instance.
      </p>
    );
  }

  const groupes = new Map<Contrainte["type"], Contrainte[]>();
  for (const c of contraintes) {
    groupes.set(c.type, [...(groupes.get(c.type) ?? []), c]);
  }

  return (
    <div className="space-y-5">
      {ORDRE_TYPE_CONTRAINTE.map((type) => {
        const groupe = groupes.get(type);
        if (!groupe) return null;
        return (
          <div key={type}>
            <h4 className="mb-2 text-sm font-semibold">
              {LABELS_TYPE_CONTRAINTE[type]} ({groupe.length})
            </h4>
            <ul className="space-y-1.5 text-sm text-muted-foreground">
              {groupe.map((c, i) => (
                <li key={i}>{decrireContrainte(c, uniteDuree)}</li>
              ))}
            </ul>
          </div>
        );
      })}
    </div>
  );
}

const LABELS_TYPE_OBJECTIF: Record<Objectif["type"], string> = {
  minimiser_makespan: "Minimiser le makespan",
  equilibrer_charge: "Équilibrer la charge",
  minimiser_retards: "Minimiser les retards",
  maximiser_utilisation: "Maximiser l'utilisation",
  minimiser_changements: "Minimiser les changements",
};

function decrireObjectif(o: Objectif): string {
  const poids = o.poids !== undefined ? ` (poids ${o.poids})` : "";
  return `${LABELS_TYPE_OBJECTIF[o.type]}${poids}`;
}

// Même calcul que api/etat.py::signature_objectifs — types d'objectifs
// uniques, triés, joints par virgule. Reproduit côté client plutôt
// qu'exposé par le backend : instance.objectifs suffit déjà.
function calculerSignatureObjectifs(objectifs: Objectif[]): string {
  return Array.from(new Set(objectifs.map((o) => o.type)))
    .sort()
    .join(",");
}

function SectionSolveurs({
  instanceId,
  clientId,
  structureContraintes,
  signatureObjectifs,
}: {
  instanceId: string;
  clientId: string;
  structureContraintes: string;
  signatureObjectifs: string;
}) {
  const { data: solveurs, isLoading } = useSolveurs();
  const { data: jobsInstance } = useJobsGeneration(instanceId);
  const [idAffiche, setIdAffiche] = useState<string | null>(null);
  const { data: codeSource, isLoading: chargementCode } = useCodeSourceSolveur(idAffiche);

  const jobActif = jobsInstance?.find((j) => !j.termine);

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Chargement...</p>;
  }

  const correspondants = (solveurs ?? []).filter(
    (s) =>
      s.client_id === clientId &&
      s.structure_contraintes === structureContraintes &&
      s.signature_objectifs === signatureObjectifs,
  );

  const banniereJob = jobActif && (
    <div className="mb-3 flex items-center gap-3 rounded-lg border border-primary/40 bg-primary/10 p-3 text-sm">
      <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
      <span>Une génération de solveur est en cours pour cette instance.</span>
    </div>
  );

  if (correspondants.length === 0) {
    return (
      <div>
        {banniereJob}
        <EmptyState
          icon={Cpu}
          title="Aucun solveur généré pour cette instance"
          desc="Génère un solveur correspondant à cette structure de contraintes et ces objectifs depuis la page Générateur de solveurs."
        />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {banniereJob}
      {correspondants.map((s) => (
        <div key={s.id} className="rounded-lg border border-border/50 p-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Badge variant="secondary" className="font-mono text-xs">
                {s.id}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {new Date(s.date_validation).toLocaleString()}
              </span>
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setIdAffiche((courant) => (courant === s.id ? null : s.id))}
            >
              <Code2 className="mr-1.5 h-3.5 w-3.5" />
              {idAffiche === s.id ? "Masquer le code" : "Aperçu du code"}
            </Button>
          </div>
          <p className="mt-1.5 font-mono text-xs text-muted-foreground">
            sha256 : {s.empreinte_sha256}
          </p>

          {idAffiche === s.id && (
            <pre className="mt-3 max-h-80 overflow-auto rounded-md border border-border/50 bg-muted/30 p-3 text-xs">
              <code>{chargementCode ? "Chargement du code..." : codeSource?.code_source}</code>
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}

function SectionScenarios({
  instance,
  estExecutee,
  onCreerScenario,
}: {
  instance: InstanceDetail;
  estExecutee: boolean;
  onCreerScenario: (instance: InstanceDetail) => void;
}) {
  const { data: comparaison, isLoading } = useComparaisonScenarios(instance.instance_id);
  // Signaux de l'agent de supervision (§2, MT7) en attente d'une décision —
  // un scénario est une instance comme une autre pour ces détecteurs
  // (`supervision/detecteurs.py` ne filtre jamais sur groupe_scenario_id),
  // donc "signature orpheline" (aucun solveur ne matche) et "à replanifier"
  // (jamais exécutée / modifiée depuis) s'y déclenchent déjà — seule leur
  // affichage manquait ici, relégué à la page /supervision séparée.
  const { data: propositions } = usePropositionsSupervision(true);
  const propositionParInstance = new Map(
    (propositions ?? []).filter((p) => p.instance_id).map((p) => [p.instance_id, p]),
  );

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {estExecutee
            ? "Compare cette instance à ses variantes (what-if) sur leur dernière exécution réussie connue — n'exécute jamais rien elle-même."
            : "Exécutez d'abord cette instance : sans exécution de référence, il n'y a rien à comparer entre elle et ses scénarios."}
        </p>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onCreerScenario(instance)}
          disabled={!estExecutee}
          title={estExecutee ? undefined : "Exécutez d'abord cette instance"}
        >
          <GitCompareArrows className="mr-1.5 h-3.5 w-3.5" /> Créer un scénario
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Chargement...</p>
      ) : (
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Instance</TableHead>
                <TableHead>Makespan</TableHead>
                <TableHead>Utilisation moy.</TableHead>
                <TableHead>Tâches en retard</TableHead>
                <TableHead>Exécuté le</TableHead>
                <TableHead>Supervision</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(comparaison?.scenarios ?? []).map((s) => {
                const taux = Object.values(s.metriques?.taux_utilisation_par_ressource ?? {});
                const moyenne =
                  taux.length > 0 ? taux.reduce((a, b) => a + b, 0) / taux.length : null;
                const proposition = propositionParInstance.get(s.instance_id);
                return (
                  <TableRow key={s.instance_id}>
                    <TableCell className="font-mono text-xs">
                      {s.instance_id}
                      {s.est_instance_de_base && (
                        <Badge variant="secondary" className="ml-1.5 text-xs">
                          base
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell>{s.metriques ? s.metriques.makespan : "—"}</TableCell>
                    <TableCell>{moyenne !== null ? `${moyenne.toFixed(0)}%` : "—"}</TableCell>
                    <TableCell>{s.metriques ? s.metriques.taches_en_retard.length : "—"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {s.date_execution ? new Date(s.date_execution).toLocaleString() : "jamais"}
                    </TableCell>
                    <TableCell>
                      {proposition ? (
                        <Link
                          to="/supervision"
                          title={proposition.resume}
                          className="inline-block hover:opacity-80"
                        >
                          <BadgeTypeSignal type={proposition.type_signal} />
                        </Link>
                      ) : (
                        <span className="text-muted-foreground">—</span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  );
}

// Associe des tâches déjà présentes dans l'instance à une commande et en dérive une échéance
// (voir api/routes/ingestion.py, POST /ingestion/{instance_id}/commandes) — ne crée jamais de
// tâche : contrairement à l'ancienne explosion de gamme, il faut que l'instance ait déjà les
// tâches concernées (via l'ingestion normale).
// Timeline compacte d'une commande : une ligne par tâche, échelonnée entre 0 et le plus tardif
// de (sa propre fin, son échéance) — jamais le makespan de tout l'atelier, qui noierait la
// commande dans le reste de l'activité. Rien à tracer avant sa première exécution réussie
// (`planifiee`) : le badge de statut au-dessus suffit alors.
function CommandeTimeline({
  commande,
  uniteDuree,
}: {
  commande: StatutCommande;
  uniteDuree?: string | null;
}) {
  if (!commande.planifiee || commande.operations.length === 0) return null;

  const echelleMax = Math.max(
    commande.date_limite ?? 0,
    ...commande.operations.map((op) => op.fin),
  );
  if (echelleMax === 0) return null;
  const limitePct =
    commande.date_limite !== null ? (commande.date_limite / echelleMax) * 100 : null;

  return (
    <div className="space-y-1">
      {commande.operations.map((op) => {
        const enRetard = commande.date_limite !== null && op.fin > commande.date_limite;
        const gauche = (op.debut / echelleMax) * 100;
        const largeur = Math.max(((op.fin - op.debut) / echelleMax) * 100, 1.5);
        return (
          <div key={op.tache} className="flex items-center gap-2">
            <span
              className="w-20 shrink-0 truncate font-mono text-[10px] text-muted-foreground"
              title={op.tache}
            >
              {op.tache}
            </span>
            <div className="relative h-4 flex-1 rounded bg-muted/30">
              {limitePct !== null && (
                <div
                  className="absolute top-0 h-full w-px bg-foreground/50"
                  style={{ left: `${limitePct}%` }}
                  title={`Échéance : ${formatDureeCourte(commande.date_limite as number, uniteDuree)}`}
                />
              )}
              <div
                className={`absolute top-0 h-full rounded ${
                  enRetard ? "bg-destructive" : "bg-gradient-to-r from-primary to-accent"
                }`}
                style={{ left: `${gauche}%`, width: `${largeur}%` }}
                title={`${formatDureeCourte(op.debut, uniteDuree)} → ${formatDureeCourte(op.fin, uniteDuree)}${
                  enRetard ? " (en retard)" : ""
                }`}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SectionNouvelleCommande({ instance }: { instance: InstanceDetail }) {
  const queryClient = useQueryClient();
  const ajouter = useAjouterCommande();
  const { data: commandes } = useCommandesInstance(instance.instance_id);
  const [ouvert, setOuvert] = useState(false);
  const [tachesChoisies, setTachesChoisies] = useState<string[]>([]);
  const [dateLimite, setDateLimite] = useState("");
  const [dernierCommandeId, setDernierCommandeId] = useState<string | null>(null);

  const erreur = ajouter.error as PrismeAPIError | null;

  function ouvrir() {
    setTachesChoisies([]);
    setDateLimite("");
    setDernierCommandeId(null);
    ajouter.reset();
    setOuvert(true);
  }

  function basculerTache(tacheId: string) {
    setTachesChoisies((prev) =>
      prev.includes(tacheId) ? prev.filter((id) => id !== tacheId) : [...prev, tacheId],
    );
  }

  function soumettre() {
    ajouter.mutate(
      {
        instanceId: instance.instance_id,
        requete: {
          taches: tachesChoisies,
          date_limite: dateLimite ? Number(dateLimite) : undefined,
        },
      },
      {
        onSuccess: (resultat) => {
          queryClient.invalidateQueries({ queryKey: prismeKeys.instance(instance.instance_id) });
          queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
          queryClient.invalidateQueries({
            queryKey: prismeKeys.commandesInstance(instance.instance_id),
          });
          setDernierCommandeId(resultat.commande_id);
          setOuvert(false);
        },
      },
    );
  }

  if (instance.taches.length === 0) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">Commandes</h4>
        {!ouvert && (
          <Button size="sm" variant="outline" onClick={ouvrir}>
            <Plus className="mr-1.5 h-3.5 w-3.5" /> Nouvelle commande
          </Button>
        )}
      </div>

      {commandes && commandes.length > 0 && (
        <div className="space-y-1.5">
          {commandes.map((c) => (
            <div
              key={c.commande_id}
              className="space-y-2 rounded-lg border border-border/50 px-3 py-2"
            >
              <div className="flex items-center justify-between">
                <div className="text-sm">
                  <span className="font-mono text-xs">{c.commande_id}</span>
                  <span className="ml-2 text-xs text-muted-foreground">
                    {c.taches.length} tâche{c.taches.length > 1 ? "s" : ""}
                    {c.date_limite !== null && ` · échéance J+${c.date_limite}`}
                  </span>
                </div>
                <Badge
                  variant={c.en_retard ? "destructive" : c.planifiee ? "secondary" : "outline"}
                >
                  {c.en_retard
                    ? "En retard"
                    : c.planifiee
                      ? "Planifiée"
                      : c.taches_manquantes.length > 0
                        ? "Tâches manquantes au planning"
                        : "En attente d'exécution"}
                </Badge>
              </div>
              <CommandeTimeline commande={c} uniteDuree={instance.unite_duree} />
            </div>
          ))}
        </div>
      )}

      {ouvert && (
        <div className="space-y-3 rounded-lg border border-border/50 p-3">
          <div className="space-y-1">
            <Label>Tâches concernées</Label>
            <div className="max-h-40 space-y-1.5 overflow-y-auto rounded-md border border-border/50 p-2">
              {instance.taches.map((t) => (
                <label key={t.id} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={tachesChoisies.includes(t.id)}
                    onCheckedChange={() => basculerTache(t.id)}
                  />
                  {t.nom ? `${t.nom} (${t.id})` : t.id}
                </label>
              ))}
            </div>
          </div>
          <div className="space-y-1">
            <Label>Échéance (jours)</Label>
            <Input
              type="number"
              min={0}
              value={dateLimite}
              onChange={(e) => setDateLimite(e.target.value)}
            />
          </div>

          {erreur && (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
              <div className="flex items-center gap-2 font-medium">
                <AlertCircle className="h-4 w-4" /> Échec de l'ajout
              </div>
              <p className="mt-1">{erreur.message}</p>
            </div>
          )}

          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setOuvert(false)}
              disabled={ajouter.isPending}
            >
              Annuler
            </Button>
            <Button
              size="sm"
              onClick={soumettre}
              disabled={tachesChoisies.length === 0 || ajouter.isPending}
            >
              {ajouter.isPending ? "Ajout..." : "Ajouter la commande"}
            </Button>
          </div>
        </div>
      )}

      {dernierCommandeId && (
        <p className="text-xs text-muted-foreground">Commande {dernierCommandeId} créée.</p>
      )}
    </div>
  );
}

function DialogDetailInstance({
  instanceId,
  instances,
  onOpenChange,
  onModifier,
  onCreerScenario,
}: {
  instanceId: string | null;
  instances: InstanceInfo[];
  onOpenChange: (open: boolean) => void;
  onModifier: (instance: InstanceDetail) => void;
  onCreerScenario: (instance: InstanceDetail) => void;
}) {
  // Une instance jamais exécutée n'a aucune référence à comparer — voir
  // SectionScenarios, qui désactive "Créer un scénario" tant que c'est vrai.
  const estExecutee = instances.find((i) => i.instance_id === instanceId)?.executee ?? false;
  const { data: instance, isLoading } = useInstance(instanceId);
  const queryClient = useQueryClient();
  const modifier = useModifierObjectifs();
  const [enEdition, setEnEdition] = useState(false);
  const [objectifsEdition, setObjectifsEdition] = useState<ObjectifLigne[]>([]);

  const erreurModification = modifier.error as PrismeAPIError | null;

  function fermer(open: boolean) {
    if (!open) {
      setEnEdition(false);
      modifier.reset();
    }
    onOpenChange(open);
  }

  function commencerEdition() {
    if (!instance) return;
    setObjectifsEdition(instance.objectifs.map(objectifVersLigne));
    modifier.reset();
    setEnEdition(true);
  }

  function enregistrerObjectifs() {
    if (!instanceId) return;
    modifier.mutate(
      { instanceId, objectifs: construireObjectifs(objectifsEdition) },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: prismeKeys.instance(instanceId) });
          queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
          setEnEdition(false);
        },
      },
    );
  }

  return (
    <Dialog open={!!instanceId} onOpenChange={fermer}>
      <DialogContent className="max-h-[85vh] max-w-5xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Détail de l'instance</DialogTitle>
          <DialogDescription className="font-mono text-xs">{instanceId}</DialogDescription>
        </DialogHeader>

        {isLoading || !instance ? (
          <p className="text-sm text-muted-foreground">Chargement...</p>
        ) : (
          <Tabs defaultValue="details">
            <TabsList>
              <TabsTrigger value="details">Détails</TabsTrigger>
              <TabsTrigger value="flux">Flux</TabsTrigger>
              <TabsTrigger value="contraintes">Contraintes</TabsTrigger>
              <TabsTrigger value="solveurs">Solveurs</TabsTrigger>
              <TabsTrigger value="scenarios">Scénarios</TabsTrigger>
            </TabsList>

            <TabsContent value="details" className="space-y-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="secondary">{instance.client_id}</Badge>
                  <Badge variant="outline" className="font-mono text-xs">
                    {instance.structure_contraintes}
                  </Badge>
                </div>
                <Button size="sm" variant="outline" onClick={() => onModifier(instance)}>
                  <Pencil className="mr-1.5 h-3.5 w-3.5" /> Modifier
                </Button>
              </div>

              <div>
                <h4 className="mb-2 text-sm font-semibold">Tâches ({instance.taches.length})</h4>
                <div className="flex flex-wrap gap-1.5">
                  {instance.taches.map((t) => (
                    <Badge key={t.id} variant="outline" className="font-mono text-xs">
                      {t.id}
                      {t.nom ? ` — ${t.nom}` : ""}
                      {t.priorite ? ` · p${t.priorite}` : ""}
                    </Badge>
                  ))}
                </div>
              </div>

              <div>
                <h4 className="mb-2 text-sm font-semibold">
                  Ressources ({instance.ressources.length})
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {instance.ressources.map((r) => (
                    <Badge key={r.id} variant="outline" className="font-mono text-xs">
                      {r.id}
                      {r.nom ? ` — ${r.nom}` : ""}
                      {r.competences.length > 0 ? ` · ${r.competences.join(", ")}` : ""}
                    </Badge>
                  ))}
                </div>
              </div>

              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h4 className="text-sm font-semibold">Objectifs ({instance.objectifs.length})</h4>
                  {!enEdition && (
                    <Button size="sm" variant="outline" onClick={commencerEdition}>
                      <Pencil className="mr-1.5 h-3.5 w-3.5" /> Modifier
                    </Button>
                  )}
                </div>

                {enEdition ? (
                  <div className="space-y-3">
                    <SectionObjectifs
                      objectifs={objectifsEdition}
                      setObjectifs={setObjectifsEdition}
                    />

                    {erreurModification && (
                      <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                        <div className="flex items-center gap-2 font-medium">
                          <AlertCircle className="h-4 w-4" /> Échec de la modification
                        </div>
                        <p className="mt-1">{erreurModification.message}</p>
                      </div>
                    )}

                    <div className="flex justify-end gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setEnEdition(false)}
                        disabled={modifier.isPending}
                      >
                        <X className="mr-1.5 h-3.5 w-3.5" /> Annuler
                      </Button>
                      <Button
                        size="sm"
                        onClick={enregistrerObjectifs}
                        disabled={modifier.isPending}
                      >
                        {modifier.isPending ? "Enregistrement..." : "Enregistrer"}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {instance.objectifs.map((o, i) => (
                      <Badge key={i} variant="secondary" className="text-xs">
                        {decrireObjectif(o)}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="flux" className="space-y-4">
              <SectionNouvelleCommande instance={instance} />
              <FlowGraphEditor instance={instance} />
            </TabsContent>

            <TabsContent value="contraintes">
              <SectionContraintes
                contraintes={instance.contraintes}
                uniteDuree={instance.unite_duree}
              />
            </TabsContent>

            <TabsContent value="solveurs">
              <SectionSolveurs
                instanceId={instance.instance_id}
                clientId={instance.client_id}
                structureContraintes={instance.structure_contraintes}
                signatureObjectifs={calculerSignatureObjectifs(instance.objectifs)}
              />
            </TabsContent>

            <TabsContent value="scenarios">
              <SectionScenarios
                instance={instance}
                estExecutee={estExecutee}
                onCreerScenario={onCreerScenario}
              />
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}

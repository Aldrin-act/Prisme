import { useMemo, useState } from "react";
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
import { FlowGraph } from "@/components/planning/flow-graph";
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
  useNomsProjet,
  useComparaisonScenarios,
  PrismeAPIError,
  LABELS_SECTEUR_ACTIVITE,
  type Contrainte,
  type InstanceDetail,
  type Objectif,
  type SecteurActivite,
} from "@/integrations/prisme";

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
  const { data: nomsProjetConnus } = useNomsProjet();
  const queryClient = useQueryClient();
  const supprimer = useSupprimerInstance();

  const instancesEnGeneration = new Set(
    (jobsGeneration ?? []).filter((j) => !j.termine).map((j) => j.instance_id),
  );

  // Filtrage côté client — quelques dizaines d'instances au plus, le filtre
  // serveur existe déjà sur GET /supervision/instances si le volume grossit.
  const [filtreNomProjet, setFiltreNomProjet] = useState("");
  const [filtreSecteur, setFiltreSecteur] = useState<SecteurActivite | "">("");
  const instancesFiltrees = useMemo(() => {
    return (instances ?? []).filter((i) => {
      if (filtreNomProjet && i.nom_projet !== filtreNomProjet) return false;
      if (filtreSecteur && i.secteur_activite !== filtreSecteur) return false;
      return true;
    });
  }, [instances, filtreNomProjet, filtreSecteur]);

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
          <div className="mb-4 flex flex-wrap items-end gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="filtre_nom_projet" className="text-xs text-muted-foreground">
                Projet
              </Label>
              <Input
                id="filtre_nom_projet"
                list="filtre-noms-projet-suggestions"
                value={filtreNomProjet}
                onChange={(e) => setFiltreNomProjet(e.target.value)}
                placeholder="Tous les projets"
                className="w-56"
              />
              <datalist id="filtre-noms-projet-suggestions">
                {nomsProjetConnus?.map((n) => (
                  <option key={n.nom_projet} value={n.nom_projet} />
                ))}
              </datalist>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="filtre_secteur" className="text-xs text-muted-foreground">
                Secteur
              </Label>
              <Select
                value={filtreSecteur}
                onValueChange={(v) => setFiltreSecteur(v === "_tous" ? "" : (v as SecteurActivite))}
              >
                <SelectTrigger id="filtre_secteur" className="w-56">
                  <SelectValue placeholder="Tous les secteurs" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_tous">Tous les secteurs</SelectItem>
                  {(Object.keys(LABELS_SECTEUR_ACTIVITE) as SecteurActivite[]).map((s) => (
                    <SelectItem key={s} value={s}>
                      {LABELS_SECTEUR_ACTIVITE[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {instancesFiltrees.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucune instance ne correspond à ces filtres.
            </p>
          ) : (
            <div className="glass overflow-hidden rounded-2xl">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Instance</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead>Client</TableHead>
                    <TableHead>Projet</TableHead>
                    <TableHead>Secteur</TableHead>
                    <TableHead>Structure des contraintes</TableHead>
                    <TableHead>Statut</TableHead>
                    <TableHead />
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {instancesFiltrees.map((instance) => {
                    const info = labels.get(instance.instance_id);
                    return (
                      <TableRow key={instance.instance_id}>
                        <TableCell className="font-mono text-xs" title={instance.instance_id}>
                          {info ? info.label : instance.instance_id}
                        </TableCell>
                        <TableCell>
                          {info?.sourceId ? (
                            <Link
                              to="/donnees"
                              search={{ source: info.sourceId }}
                              className="text-primary underline-offset-2 hover:underline"
                            >
                              {info.nomSource}
                            </Link>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
                        <TableCell>{instance.client_id}</TableCell>
                        <TableCell>
                          {instance.nom_projet ?? <span className="text-muted-foreground">—</span>}
                        </TableCell>
                        <TableCell>
                          {instance.secteur_activite ? (
                            <Badge variant="outline">
                              {LABELS_SECTEUR_ACTIVITE[
                                instance.secteur_activite as SecteurActivite
                              ] ?? instance.secteur_activite}
                            </Badge>
                          ) : (
                            <span className="text-muted-foreground">—</span>
                          )}
                        </TableCell>
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
          )}
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
        onOpenChange={(open) => !open && setAVoir(null)}
        onModifier={ouvrirModification}
        onCreerScenario={ouvrirCreationScenario}
      />
    </>
  );
}

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
function decrireContrainte(c: Contrainte): string {
  switch (c.type) {
    case "precedence":
      return `La tâche ${c.avant} doit être terminée avant que ${c.apres} commence.`;
    case "compatibilite_ressource_tache":
      return `${c.tache} peut être réalisée sur ${c.ressource} (durée : ${c.duree} jour${c.duree > 1 ? "s" : ""}).`;
    case "echeance":
      return `${c.tache} doit être terminée au plus tard au jour ${c.echeance}.`;
    case "competence_requise":
      return `${c.tache} exige la compétence « ${c.competence} ».`;
    case "capacite":
      return `${c.ressource} peut traiter jusqu'à ${c.capacite} opération${c.capacite > 1 ? "s" : ""} simultanément.`;
    case "disponibilite_ressource": {
      const parties: string[] = [];
      if (c.jours_indisponibles.length > 0) {
        parties.push(
          `le${c.jours_indisponibles.length > 1 ? "s" : ""} jour${
            c.jours_indisponibles.length > 1 ? "s" : ""
          } ${c.jours_indisponibles.join(", ")}`,
        );
      }
      if (c.jours_semaine_indisponibles && c.jours_semaine_indisponibles.length > 0) {
        parties.push(
          `chaque semaine aux positions ${c.jours_semaine_indisponibles.join(", ")} (motif récurrent)`,
        );
      }
      return `${c.ressource} est indisponible ${parties.join(" et ")}.`;
    }
    case "incompatibilite":
      return `${c.tache} et ${c.tache_incompatible} ne peuvent jamais partager la même ressource.`;
    case "taille_lot":
      return `${c.tache} doit produire entre ${c.lot_min} et ${c.lot_max} unités.`;
    case "changement_serie":
      return `Sur ${c.ressource}, faire suivre ${c.tache_avant} par ${c.tache_apres} exige un changement de série de ${c.duree_setup} jour${c.duree_setup > 1 ? "s" : ""}.`;
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

function SectionContraintes({ contraintes }: { contraintes: Contrainte[] }) {
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
                <li key={i}>{decrireContrainte(c)}</li>
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
  onCreerScenario,
}: {
  instance: InstanceDetail;
  onCreerScenario: (instance: InstanceDetail) => void;
}) {
  const { data: comparaison, isLoading } = useComparaisonScenarios(instance.instance_id);

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          Compare cette instance à ses variantes (what-if) sur leur dernière exécution réussie
          connue — n'exécute jamais rien elle-même.
        </p>
        <Button size="sm" variant="outline" onClick={() => onCreerScenario(instance)}>
          <GitCompareArrows className="mr-1.5 h-3.5 w-3.5" /> Créer un scénario
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Chargement...</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Instance</TableHead>
              <TableHead>Projet</TableHead>
              <TableHead>Makespan</TableHead>
              <TableHead>Utilisation moy.</TableHead>
              <TableHead>Tâches en retard</TableHead>
              <TableHead>Exécuté le</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {(comparaison?.scenarios ?? []).map((s) => {
              const taux = Object.values(s.metriques?.taux_utilisation_par_ressource ?? {});
              const moyenne =
                taux.length > 0 ? taux.reduce((a, b) => a + b, 0) / taux.length : null;
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
                  <TableCell>{s.nom_projet ?? "—"}</TableCell>
                  <TableCell>{s.metriques ? s.metriques.makespan : "—"}</TableCell>
                  <TableCell>{moyenne !== null ? `${moyenne.toFixed(0)}%` : "—"}</TableCell>
                  <TableCell>{s.metriques ? s.metriques.taches_en_retard.length : "—"}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    {s.date_execution ? new Date(s.date_execution).toLocaleString() : "jamais"}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </div>
  );
}

function DialogDetailInstance({
  instanceId,
  onOpenChange,
  onModifier,
  onCreerScenario,
}: {
  instanceId: string | null;
  onOpenChange: (open: boolean) => void;
  onModifier: (instance: InstanceDetail) => void;
  onCreerScenario: (instance: InstanceDetail) => void;
}) {
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

            <TabsContent value="flux">
              <FlowGraph taches={instance.taches} contraintes={instance.contraintes} />
            </TabsContent>

            <TabsContent value="contraintes">
              <SectionContraintes contraintes={instance.contraintes} />
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
              <SectionScenarios instance={instance} onCreerScenario={onCreerScenario} />
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
}

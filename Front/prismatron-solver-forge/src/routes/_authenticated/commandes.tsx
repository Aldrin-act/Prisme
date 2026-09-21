import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  AlertTriangle,
  CalendarClock,
  CheckCircle2,
  ClipboardList,
  Clock,
  Factory,
  Plus,
  Search,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader, EmptyState } from "@/components/app-page";
import { FormulaireNouvelleCommande } from "@/components/commandes/formulaire-nouvelle-commande";
import {
  useChangerStatutCommande,
  useCommandes,
  useInstance,
  useInstances,
  useLabelsInstances,
  type InstanceInfo,
  type StatutCommande,
  type StatutRealisationCommande,
} from "@/integrations/prisme";
import {
  aujourdhui,
  dateDepuisAncrage,
  debutJour,
  formatDateRelative,
  type UniteTemps,
} from "@/lib/dates-relatives";

export const Route = createFileRoute("/_authenticated/commandes")({
  head: () => ({ meta: [{ title: "Commandes — PRISME" }] }),
  component: CommandesPage,
});

// ---------------------------------------------------------------------------------------------
// Statut et dates
// ---------------------------------------------------------------------------------------------

type Statut = "en_retard" | "a_temps" | "sans_echeance" | "non_planifiee";

function statutCommande(c: StatutCommande): Statut {
  if (c.en_retard) return "en_retard";
  if (!c.planifiee) return "non_planifiee";
  // en_retard reste `null` (jamais faux) tant qu'aucune échéance n'est déclarée — voir
  // calculer_statut_commande, api/comparaison_scenarios.py : rien à comparer.
  if (c.date_limite === null) return "sans_echeance";
  return "a_temps";
}

// En retard d'abord, puis à temps, puis sans échéance, puis non planifiée — priorités
// numériques explicites plutôt que comparer `en_retard` (`true | false | null`) directement,
// `null` étant incomparable (un comparateur naïf sur ces trois valeurs n'est pas transitif).
const PRIORITE_STATUT: Record<Statut, number> = {
  en_retard: 0,
  a_temps: 1,
  sans_echeance: 2,
  non_planifiee: 3,
};

function comparerUrgence(a: StatutCommande, b: StatutCommande): number {
  const ecart = PRIORITE_STATUT[statutCommande(a)] - PRIORITE_STATUT[statutCommande(b)];
  if (ecart !== 0) return ecart;
  if (a.date_limite === null || b.date_limite === null) return 0;
  return a.date_limite - b.date_limite;
}

// Unité des instants relatifs d'une commande = celle de son atelier (instance). `unite_duree`
// vaut "heures" exactement quand l'instance est en mode heures (api/unite_duree.py) ; sinon
// l'instance est en jours. Sans cette information, une commande en heures s'afficherait avec des
// dates 24 fois trop éloignées.
function uniteDeLAtelier(instance: InstanceInfo | undefined): UniteTemps {
  return instance?.unite_duree === "heures" ? "heures" : "jours";
}

// Ancrage calendaire : horodatage réel de la dernière exécution réussie de l'atelier (fait
// historique figé côté serveur) si connu, sinon "aujourd'hui" — une prévisualisation "si exécuté
// maintenant". En mode heures l'ancrage garde son heure (voir src/lib/dates-relatives.ts).
function ancrage(commande: StatutCommande, unite: UniteTemps): Date {
  if (!commande.date_execution) return aujourdhui();
  const date = new Date(commande.date_execution);
  return unite === "heures" ? date : debutJour(date);
}

const MS_PAR_HEURE = 3_600_000;

// "dans 3 j", "il y a 5 h" — par rapport à maintenant, pour qu'une échéance se
// lise d'un coup d'œil sans calcul mental.
function delaiRelatif(date: Date): { texte: string; passe: boolean; proche: boolean } {
  const heures = (date.getTime() - Date.now()) / MS_PAR_HEURE;
  const passe = heures < 0;
  const absolu = Math.abs(heures);
  let valeur: string;
  if (absolu < 1) valeur = "moins d'1 h";
  else if (absolu < 48) valeur = `${Math.round(absolu)} h`;
  else valeur = `${Math.round(absolu / 24)} j`;
  return {
    texte: passe ? `il y a ${valeur}` : `dans ${valeur}`,
    passe,
    proche: !passe && heures <= 72,
  };
}

// Écart lisible dans l'unité de l'atelier : "5 j", "7 h", "3 j 4 h" — jamais "2554 heures".
function formatEcart(valeur: number, unite: UniteTemps): string {
  if (unite === "jours") return `${valeur} j`;
  if (valeur < 24) return `${valeur} h`;
  const jours = Math.floor(valeur / 24);
  const heures = valeur % 24;
  return heures === 0 ? `${jours} j` : `${jours} j ${heures} h`;
}

// ---------------------------------------------------------------------------------------------
// Petits composants
// ---------------------------------------------------------------------------------------------

const CONFIG_STATUT: Record<
  Statut,
  { label: string; icone: typeof AlertTriangle; badge: string; bordure: string }
> = {
  en_retard: {
    label: "En retard",
    icone: AlertTriangle,
    badge: "border-destructive/40 bg-destructive/15 text-destructive",
    bordure: "border-l-destructive",
  },
  a_temps: {
    label: "À temps",
    icone: CheckCircle2,
    badge: "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    bordure: "border-l-emerald-500",
  },
  sans_echeance: {
    label: "Sans échéance",
    icone: CalendarClock,
    badge: "border-border bg-muted/40 text-muted-foreground",
    bordure: "border-l-border",
  },
  non_planifiee: {
    label: "Non planifiée",
    icone: Clock,
    badge: "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400",
    bordure: "border-l-amber-500",
  },
};

function BadgeStatut({ statut }: { statut: Statut }) {
  const { label, icone: Icone, badge } = CONFIG_STATUT[statut];
  return (
    <Badge variant="outline" className={`gap-1 whitespace-nowrap ${badge}`}>
      <Icone className="h-3 w-3" /> {label}
    </Badge>
  );
}

// Avancement réel dans l'atelier, déclaré par un humain — jamais déduit du planning, qui ne
// dit que ce qui devrait arriver (voir api/routes/ingestion.py::changer_statut_commande).
const LIBELLE_AVANCEMENT: Record<StatutRealisationCommande, string> = {
  non_debutee: "Non débutée",
  en_cours: "En cours",
  realisee: "Réalisée",
};

const STYLE_AVANCEMENT: Record<StatutRealisationCommande, string> = {
  non_debutee: "text-muted-foreground",
  en_cours: "text-sky-600 dark:text-sky-400",
  realisee: "text-emerald-600 dark:text-emerald-400",
};

function SelecteurAvancement({ commande, unite }: { commande: StatutCommande; unite: UniteTemps }) {
  const changer = useChangerStatutCommande();

  // Fin prévue dépassée sans confirmation humaine : on le signale, on ne conclut rien. Une
  // date passée ne prouve pas que le travail a été fait (panne, absence, matière manquante).
  const finPrevuePassee =
    commande.date_fin_prevue !== null &&
    dateDepuisAncrage(commande.date_fin_prevue, ancrage(commande, unite), unite).getTime() <
      Date.now();
  const aConfirmer = commande.statut_realisation !== "realisee" && finPrevuePassee;

  return (
    <div className="min-w-36">
      <Select
        value={commande.statut_realisation}
        disabled={changer.isPending}
        onValueChange={(statut) =>
          changer.mutate(
            {
              commandeId: commande.commande_id,
              requete: { statut: statut as StatutRealisationCommande },
            },
            {
              onSuccess: (maj) =>
                toast.success(
                  `Commande ${maj.numero ?? maj.commande_id} : ${LIBELLE_AVANCEMENT[
                    maj.statut_realisation
                  ].toLowerCase()}`,
                ),
              onError: (erreur: Error) =>
                toast.error("Statut non enregistré", { description: erreur.message }),
            },
          )
        }
      >
        <SelectTrigger
          className={`h-8 text-xs ${STYLE_AVANCEMENT[commande.statut_realisation]}`}
          aria-label="Avancement déclaré"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(Object.keys(LIBELLE_AVANCEMENT) as StatutRealisationCommande[]).map((statut) => (
            <SelectItem key={statut} value={statut}>
              {LIBELLE_AVANCEMENT[statut]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {aConfirmer && (
        <div className="mt-1 text-[11px] text-amber-600 dark:text-amber-400">
          Échue — à confirmer
        </div>
      )}
      {commande.statut_realisation === "realisee" && commande.date_realisation && (
        <div className="mt-1 text-[11px] text-muted-foreground">
          Le {new Date(commande.date_realisation).toLocaleDateString("fr-FR")}
        </div>
      )}
    </div>
  );
}

function CarteIndicateur({
  label,
  valeur,
  icone: Icone,
  accent,
  actif,
  onClick,
}: {
  label: string;
  valeur: number | undefined;
  icone: typeof AlertTriangle;
  accent: string;
  actif: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={actif}
      className={`glass flex items-center gap-3 rounded-2xl p-4 text-left transition hover:ring-1 hover:ring-primary/40 ${
        actif ? "ring-2 ring-primary" : ""
      }`}
    >
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${accent}`}>
        <Icone className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold leading-none tabular-nums">
          {valeur === undefined ? <Skeleton className="h-6 w-8" /> : valeur}
        </div>
        <div className="mt-1 truncate text-xs text-muted-foreground">{label}</div>
      </div>
    </button>
  );
}

// ---------------------------------------------------------------------------------------------
// Dialogue « Nouvelle commande »
// ---------------------------------------------------------------------------------------------

// Choix de l'atelier puis le même formulaire que l'onglet Flux d'une instance
// (`FormulaireNouvelleCommande`, jamais dupliqué). Dans un dialogue plutôt qu'en tête de page :
// la liste des commandes reste la première chose visible, la création est une action ponctuelle.
function DialogueNouvelleCommande({
  ouvert,
  onOpenChange,
  instances,
  labels,
}: {
  ouvert: boolean;
  onOpenChange: (v: boolean) => void;
  instances: InstanceInfo[];
  labels: ReturnType<typeof useLabelsInstances>;
}) {
  const [instanceId, setInstanceId] = useState<string | null>(null);
  const [editionProcessus, setEditionProcessus] = useState(false);
  const { data: instance, isLoading } = useInstance(instanceId);

  function changerOuverture(v: boolean) {
    if (!v) {
      setInstanceId(null);
      setEditionProcessus(false);
    }
    onOpenChange(v);
  }

  return (
    <Dialog open={ouvert} onOpenChange={changerOuverture}>
      {/* L'éditeur de processus (graphe + panneau d'étape) a besoin de bien plus de largeur que
          le formulaire : le dialogue s'élargit le temps de l'édition. */}
      <DialogContent
        className={`max-h-[90vh] overflow-y-auto ${editionProcessus ? "sm:max-w-5xl" : "sm:max-w-xl"}`}
      >
        <DialogHeader>
          <DialogTitle>Nouvelle commande</DialogTitle>
          <DialogDescription>
            Une commande reprend le processus de l'atelier pour une quantité et une échéance. Le
            planning de l'atelier est recalculé automatiquement après l'ajout.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-1.5">
          <Label htmlFor="commande_atelier">Atelier</Label>
          <Select
            value={instanceId ?? undefined}
            onValueChange={setInstanceId}
            disabled={editionProcessus}
          >
            <SelectTrigger id="commande_atelier">
              <SelectValue placeholder="Choisir l'atelier concerné" />
            </SelectTrigger>
            <SelectContent>
              {instances.map((inst) => (
                <SelectItem key={inst.instance_id} value={inst.instance_id}>
                  {libelleAtelier(inst.instance_id, labels)} · {inst.client_id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {instanceId && isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-9 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        )}
        {instance && (
          <FormulaireNouvelleCommande
            key={instance.instance_id}
            instance={instance}
            integre
            onEditionProcessus={setEditionProcessus}
            onAnnuler={() => changerOuverture(false)}
            onCommandeAjoutee={(resultat) => {
              changerOuverture(false);
              if (resultat.execution_reussie === false) {
                toast.warning(`Commande ${resultat.commande_id} créée`, {
                  description: `Replanification échouée : ${resultat.erreur_execution ?? "erreur inconnue"}`,
                });
              } else {
                toast.success(`Commande ${resultat.commande_id} créée`, {
                  description:
                    resultat.execution_reussie === true
                      ? "Planning de l'atelier mis à jour."
                      : "Le planning sera recalculé à la prochaine exécution.",
                });
              }
              resultat.avertissements.forEach((a) => toast.warning(a));
            }}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}

function libelleAtelier(instanceId: string, labels: ReturnType<typeof useLabelsInstances>): string {
  return labels.get(instanceId)?.label ?? `Atelier ${instanceId.slice(0, 8)}`;
}

// ---------------------------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------------------------

type FiltreStatut = Statut | "toutes";

function CommandesPage() {
  const { data: commandes, isLoading } = useCommandes();
  const { data: instances } = useInstances();
  const labels = useLabelsInstances();

  const [dialogueOuvert, setDialogueOuvert] = useState(false);
  const [recherche, setRecherche] = useState("");
  const [filtreStatut, setFiltreStatut] = useState<FiltreStatut>("toutes");
  const [filtreAtelier, setFiltreAtelier] = useState<string>("tous");

  const instanceParId = useMemo(
    () => new Map((instances ?? []).map((i) => [i.instance_id, i])),
    [instances],
  );

  const compteurs = useMemo(() => {
    const base = { toutes: 0, en_retard: 0, a_temps: 0, sans_echeance: 0, non_planifiee: 0 };
    (commandes ?? []).forEach((c) => {
      base.toutes += 1;
      base[statutCommande(c)] += 1;
    });
    return base;
  }, [commandes]);

  // Ateliers réellement présents dans les commandes — un filtre vers un atelier sans commande
  // ne renverrait qu'une liste vide.
  const ateliersAvecCommandes = useMemo(
    () => [...new Set((commandes ?? []).map((c) => c.instance_id))],
    [commandes],
  );

  const commandesFiltrees = useMemo(() => {
    const terme = recherche.trim().toLowerCase();
    return [...(commandes ?? [])]
      .filter((c) => filtreStatut === "toutes" || statutCommande(c) === filtreStatut)
      .filter((c) => filtreAtelier === "tous" || c.instance_id === filtreAtelier)
      .filter((c) => {
        if (!terme) return true;
        return [
          c.commande_id,
          c.numero,
          c.nom_client,
          c.client_id,
          c.description,
          libelleAtelier(c.instance_id, labels),
          ...c.taches,
        ]
          .filter(Boolean)
          .some((v) => (v as string).toLowerCase().includes(terme));
      })
      .sort(comparerUrgence);
  }, [commandes, filtreStatut, filtreAtelier, recherche, labels]);

  const filtresActifs = recherche !== "" || filtreStatut !== "toutes" || filtreAtelier !== "tous";

  function reinitialiserFiltres() {
    setRecherche("");
    setFiltreStatut("toutes");
    setFiltreAtelier("tous");
  }

  function basculerStatut(statut: FiltreStatut) {
    setFiltreStatut((actuel) => (actuel === statut ? "toutes" : statut));
  }

  const boutonNouvelleCommande = (
    <Button onClick={() => setDialogueOuvert(true)}>
      <Plus className="mr-1.5 h-4 w-4" /> Nouvelle commande
    </Button>
  );

  const aucuneCommande = !isLoading && commandes && commandes.length === 0;

  return (
    <>
      <PageHeader
        title="Commandes"
        desc="Suivez les commandes clients à travers tous les ateliers — échéance, début d'exécution prévu et risque de retard."
        action={boutonNouvelleCommande}
      />

      <DialogueNouvelleCommande
        ouvert={dialogueOuvert}
        onOpenChange={setDialogueOuvert}
        instances={instances ?? []}
        labels={labels}
      />

      {aucuneCommande ? (
        <EmptyState
          icon={ClipboardList}
          title="Aucune commande pour l'instant"
          desc="Une commande relie des tâches déjà présentes dans un atelier à une échéance client."
          action={boutonNouvelleCommande}
        />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <CarteIndicateur
              label="Commandes"
              valeur={isLoading ? undefined : compteurs.toutes}
              icone={ClipboardList}
              accent="bg-primary/15 text-primary"
              actif={filtreStatut === "toutes"}
              onClick={() => setFiltreStatut("toutes")}
            />
            <CarteIndicateur
              label="En retard"
              valeur={isLoading ? undefined : compteurs.en_retard}
              icone={AlertTriangle}
              accent="bg-destructive/15 text-destructive"
              actif={filtreStatut === "en_retard"}
              onClick={() => basculerStatut("en_retard")}
            />
            <CarteIndicateur
              label="À temps"
              valeur={isLoading ? undefined : compteurs.a_temps}
              icone={CheckCircle2}
              accent="bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
              actif={filtreStatut === "a_temps"}
              onClick={() => basculerStatut("a_temps")}
            />
            <CarteIndicateur
              label="Non planifiées"
              valeur={isLoading ? undefined : compteurs.non_planifiee}
              icone={Clock}
              accent="bg-amber-500/15 text-amber-600 dark:text-amber-400"
              actif={filtreStatut === "non_planifiee"}
              onClick={() => basculerStatut("non_planifiee")}
            />
          </div>

          <div className="glass overflow-hidden rounded-2xl">
            <div className="flex flex-wrap items-center gap-2 border-b border-border/50 p-3">
              <div className="relative min-w-48 flex-1">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={recherche}
                  onChange={(e) => setRecherche(e.target.value)}
                  placeholder="Rechercher une commande, un client, une tâche..."
                  className="pl-8"
                  aria-label="Rechercher une commande"
                />
              </div>
              <Select
                value={filtreStatut}
                onValueChange={(v) => setFiltreStatut(v as FiltreStatut)}
              >
                <SelectTrigger className="w-full sm:w-44" aria-label="Filtrer par statut">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="toutes">Tous les statuts</SelectItem>
                  {(Object.keys(CONFIG_STATUT) as Statut[]).map((s) => (
                    <SelectItem key={s} value={s}>
                      {CONFIG_STATUT[s].label} ({compteurs[s]})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={filtreAtelier} onValueChange={setFiltreAtelier}>
                <SelectTrigger className="w-full sm:w-52" aria-label="Filtrer par atelier">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="tous">Tous les ateliers</SelectItem>
                  {ateliersAvecCommandes.map((id) => (
                    <SelectItem key={id} value={id}>
                      {libelleAtelier(id, labels)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {filtresActifs && (
                <Button variant="ghost" size="sm" onClick={reinitialiserFiltres}>
                  <X className="mr-1 h-3.5 w-3.5" /> Réinitialiser
                </Button>
              )}
            </div>

            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Commande</TableHead>
                    <TableHead>Client</TableHead>
                    <TableHead>Atelier</TableHead>
                    <TableHead>Contenu</TableHead>
                    <TableHead>Début prévu</TableHead>
                    <TableHead>Échéance</TableHead>
                    <TableHead>Statut prévu</TableHead>
                    <TableHead>Avancement réel</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {isLoading &&
                    Array.from({ length: 5 }, (_, i) => (
                      <TableRow key={`squelette-${i}`}>
                        {Array.from({ length: 8 }, (_, j) => (
                          <TableCell key={j}>
                            <Skeleton className="h-5 w-full" />
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  {!isLoading &&
                    commandesFiltrees.map((commande) => (
                      <LigneCommande
                        key={commande.commande_id}
                        commande={commande}
                        unite={uniteDeLAtelier(instanceParId.get(commande.instance_id))}
                        atelier={libelleAtelier(commande.instance_id, labels)}
                        onFiltrerAtelier={() => setFiltreAtelier(commande.instance_id)}
                      />
                    ))}
                  {!isLoading && commandesFiltrees.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={8} className="py-10 text-center">
                        <p className="text-sm text-muted-foreground">
                          Aucune commande ne correspond à ces filtres.
                        </p>
                        <Button
                          variant="link"
                          size="sm"
                          onClick={reinitialiserFiltres}
                          className="mt-1"
                        >
                          Réinitialiser les filtres
                        </Button>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>

            {!isLoading && commandes && commandes.length > 0 && (
              <div className="border-t border-border/50 px-4 py-2 text-xs text-muted-foreground">
                {commandesFiltrees.length === commandes.length
                  ? `${commandes.length} commande${commandes.length > 1 ? "s" : ""}`
                  : `${commandesFiltrees.length} sur ${commandes.length} commandes`}{" "}
                · triées par urgence
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}

function LigneCommande({
  commande,
  unite,
  atelier,
  onFiltrerAtelier,
}: {
  commande: StatutCommande;
  unite: UniteTemps;
  atelier: string;
  onFiltrerAtelier: () => void;
}) {
  const statut = statutCommande(commande);
  const refAncrage = ancrage(commande, unite);

  const debut =
    commande.planifiee && commande.operations.length > 0
      ? Math.min(...commande.operations.map((o) => o.debut))
      : null;

  const echeance =
    commande.date_limite !== null
      ? {
          texte: formatDateRelative(commande.date_limite, refAncrage, unite),
          delai: delaiRelatif(dateDepuisAncrage(commande.date_limite, refAncrage, unite)),
        }
      : null;

  // Marge = échéance − fin prévue, dans l'unité de l'atelier : positive = avance, négative =
  // retard. Donne l'ampleur du problème, là où le badge ne dit que oui/non.
  const marge =
    commande.date_limite !== null && commande.date_fin_prevue !== null
      ? commande.date_limite - commande.date_fin_prevue
      : null;

  // Pièces commandées (commande éclatée depuis le processus de l'atelier) — déjà appliquées aux
  // durées de ses tâches ; absent pour une commande sur tâches existantes.
  const pieces =
    commande.quantite !== null
      ? `${commande.quantite} pièce${commande.quantite > 1 ? "s" : ""}`
      : null;
  const client = commande.nom_client ?? commande.client_id;
  const nbTaches = commande.taches.length;
  const nbManquantes = commande.taches_manquantes.length;

  return (
    <TableRow className={`border-l-4 ${CONFIG_STATUT[statut].bordure}`}>
      <TableCell className="min-w-40">
        <div className="flex flex-wrap items-center gap-1.5">
          {/* Numéro métier en titre quand il existe ; sinon l'identifiant technique prend sa place
              plutôt qu'un « Sans numéro » répété sur chaque ligne. */}
          <span className={commande.numero ? "font-medium" : "font-mono text-sm"}>
            {commande.numero ?? commande.commande_id}
          </span>
          {commande.est_prospect && (
            <Badge variant="outline" className="h-5 px-1.5 text-[10px]">
              Prospect
            </Badge>
          )}
        </div>
        {commande.numero && (
          <div className="font-mono text-[11px] text-muted-foreground">{commande.commande_id}</div>
        )}
        {commande.description && (
          <div
            className="mt-0.5 max-w-56 truncate text-xs text-muted-foreground"
            title={commande.description}
          >
            {commande.description}
          </div>
        )}
      </TableCell>

      <TableCell className="min-w-28">
        <div className="text-sm">{client}</div>
        {commande.nom_client && commande.nom_client !== commande.client_id && (
          <div className="text-xs text-muted-foreground">{commande.client_id}</div>
        )}
      </TableCell>

      <TableCell>
        <button
          type="button"
          onClick={onFiltrerAtelier}
          title={`${commande.instance_id} — cliquer pour filtrer sur cet atelier`}
          className="inline-flex max-w-44 items-center gap-1.5 rounded-md border border-border/60 px-2 py-1 text-xs hover:border-primary/50 hover:text-primary"
        >
          <Factory className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{atelier}</span>
        </button>
      </TableCell>

      <TableCell className="min-w-40">
        {pieces && <div className="text-sm tabular-nums">{pieces}</div>}
        <div
          className={pieces ? "text-xs text-muted-foreground" : "text-sm"}
          title={commande.taches.join(", ")}
        >
          {nbTaches} tâche{nbTaches > 1 ? "s" : ""}
          {nbManquantes > 0 && (
            <span
              className="ml-1 inline-flex items-center gap-0.5 text-amber-600 dark:text-amber-400"
              title={`Absentes de l'atelier : ${commande.taches_manquantes.join(", ")}`}
            >
              <AlertTriangle className="h-3 w-3" />
              {nbManquantes} manquante{nbManquantes > 1 ? "s" : ""}
            </span>
          )}
        </div>
      </TableCell>

      <TableCell className="whitespace-nowrap text-sm">
        {debut !== null ? (
          formatDateRelative(debut, refAncrage, unite)
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>

      <TableCell className="whitespace-nowrap">
        {echeance ? (
          <>
            <div className="text-sm">{echeance.texte}</div>
            <div
              className={`text-xs ${
                echeance.delai.passe
                  ? "text-destructive"
                  : echeance.delai.proche
                    ? "text-amber-600 dark:text-amber-400"
                    : "text-muted-foreground"
              }`}
            >
              {echeance.delai.texte}
            </div>
          </>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>

      <TableCell className="whitespace-nowrap">
        <BadgeStatut statut={statut} />
        {marge !== null && marge !== 0 && (
          <div
            className={`mt-1 text-xs ${marge < 0 ? "text-destructive" : "text-muted-foreground"}`}
          >
            {marge < 0
              ? `Fin ${formatEcart(-marge, unite)} après l'échéance`
              : `Marge ${formatEcart(marge, unite)}`}
          </div>
        )}
      </TableCell>

      <TableCell>
        <SelecteurAvancement commande={commande} unite={unite} />
      </TableCell>
    </TableRow>
  );
}

import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowDown, Pencil, Plus, Workflow } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { EditeurProcessus } from "@/components/planning/editeur-processus";
import { AvertissementEnchainements } from "@/components/planning/avertissement-enchainements";
import { etapesDepuisTaches } from "@/components/planning/processus-utils";
import {
  prismeKeys,
  useAjouterCommande,
  useProcessus,
  PrismeAPIError,
  type EtapeProcessus,
  type InstanceDetail,
  type ResultatNouvelleCommande,
} from "@/integrations/prisme";
import {
  aujourdhui,
  formatEntreeDate,
  formatEntreeDateHeure,
  jourDepuisAncrage,
  parseEntreeDate,
  parseEntreeDateHeure,
  type UniteTemps,
} from "@/lib/dates-relatives";
import { formatDureeCourte } from "@/lib/unite-duree";

// Étapes dans l'ordre où elles s'enchaînent (tri topologique) plutôt que dans l'ordre de saisie :
// c'est ainsi qu'un chef d'atelier lit un processus. Le serveur refuse les cycles, donc toutes
// les étapes finissent par être placées ; l'ordre de saisie départage les étapes parallèles.
function ordonnerEtapes(etapes: EtapeProcessus[]): EtapeProcessus[] {
  const placees = new Set<string>();
  const ordre: EtapeProcessus[] = [];
  while (ordre.length < etapes.length) {
    const pretes = etapes.filter(
      (e) => !placees.has(e.id) && e.predecesseurs.every((p) => placees.has(p)),
    );
    if (pretes.length === 0) return etapes;
    for (const e of pretes) {
      placees.add(e.id);
      ordre.push(e);
    }
  }
  return ordre;
}

function ApercuProcessus({
  etapes,
  quantite,
  uniteTemps,
}: {
  etapes: EtapeProcessus[];
  quantite: number;
  uniteTemps: UniteTemps;
}) {
  const nomParId = new Map(etapes.map((e) => [e.id, e.nom ?? e.id]));
  const ordonnees = ordonnerEtapes(etapes);
  return (
    <ol className="space-y-0.5">
      {ordonnees.map((e, i) => {
        // Une étape qui attend plusieurs étapes (fusion), ou une autre que la précédente de la
        // liste, le dit explicitement : la liste seule ferait croire à une simple chaîne.
        const attend =
          e.predecesseurs.length > 1 ||
          (e.predecesseurs.length === 1 && e.predecesseurs[0] !== ordonnees[i - 1]?.id);
        return (
          <li key={e.id}>
            {i > 0 && <ArrowDown className="mx-auto my-0.5 h-3 w-3 text-muted-foreground" />}
            <div className="flex items-baseline justify-between gap-3 rounded-md border border-border/60 px-2.5 py-1.5 text-sm">
              <div className="min-w-0">
                <div className="truncate font-medium">{e.nom ?? e.id}</div>
                <div className="truncate font-mono text-[11px] text-muted-foreground">
                  {e.competences.join(", ")}
                  {attend &&
                    ` · après ${e.predecesseurs.map((p) => nomParId.get(p) ?? p).join(" et ")}`}
                </div>
              </div>
              <div className="shrink-0 text-right text-xs tabular-nums text-muted-foreground">
                {quantite > 1 ? (
                  <>
                    {formatDureeCourte(e.duree_par_piece, uniteTemps)} × {quantite} ={" "}
                    <span className="font-medium text-foreground">
                      {formatDureeCourte(e.duree_par_piece * quantite, uniteTemps)}
                    </span>
                  </>
                ) : (
                  <span className="font-medium text-foreground">
                    {formatDureeCourte(e.duree_par_piece, uniteTemps)}
                  </span>
                )}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * Formulaire d'ajout d'une commande à un atelier. L'atelier a **un seul processus** (ses étapes
 * et leur enchaînement), défini une fois : chaque commande en reçoit sa propre copie, pour la
 * quantité demandée, avec une durée par étape multipliée par cette quantité (voir
 * api/routes/ingestion.py::ajouter_commande). Le processus se définit ou se modifie d'ici même,
 * sans changer de page.
 *
 * Partagé entre l'onglet Flux d'une instance (`routes/_authenticated/instances.tsx`, `instance`
 * fixée par le contexte) et la page Commandes (`routes/_authenticated/commandes.tsx`, `instance`
 * choisie via un sélecteur d'atelier) — même formulaire, jamais dupliqué.
 */
export function FormulaireNouvelleCommande({
  instance,
  onCommandeAjoutee,
  onAnnuler,
  onEditionProcessus,
  integre = false,
}: {
  instance: InstanceDetail;
  /** Appelé en plus de l'invalidation déjà faite ici (instance, instances, commandes de
   * l'instance, commandes globales, exécutions) — ex. fermer un dialogue englobant. */
  onCommandeAjoutee?: (resultat: ResultatNouvelleCommande) => void;
  /** Mode `integre` : appelé par « Annuler » à la place de replier le formulaire. */
  onAnnuler?: () => void;
  /** Prévient le conteneur quand l'éditeur de processus s'ouvre ou se ferme — il a besoin de
   * bien plus de largeur que le formulaire (ex. élargir un dialogue). */
  onEditionProcessus?: (actif: boolean) => void;
  /** Formulaire déjà ouvert, sans titre ni bouton « Nouvelle commande » ni récapitulatif — pour
   * un conteneur (ex. dialogue de la page Commandes) qui porte déjà ces éléments lui-même. */
  integre?: boolean;
}) {
  const queryClient = useQueryClient();
  const ajouter = useAjouterCommande();
  const processus = useProcessus(instance.instance_id);
  const etapes = processus.data?.etapes ?? [];
  // Sans processus défini, les tâches déjà présentes dans l'atelier (ingérées) sont proposées comme
  // étapes : une tâche = une étape. Simple proposition, à vérifier puis enregistrer.
  const etapesProposees = useMemo(() => etapesDepuisTaches(instance), [instance]);

  const [ouvert, setOuvert] = useState(integre);
  const [editionProcessus, setEditionProcessus] = useState(false);
  const [quantite, setQuantite] = useState("1");
  const [dateLimite, setDateLimite] = useState("");
  const [dateDebutAuPlusTot, setDateDebutAuPlusTot] = useState("");
  const [numero, setNumero] = useState("");
  const [description, setDescription] = useState("");
  const [nomClient, setNomClient] = useState("");
  const uniteTemps: UniteTemps = instance.unite_temps === "heures" ? "heures" : "jours";
  const [dernierCommandeId, setDernierCommandeId] = useState<string | null>(null);
  // Résultat de l'exécution automatique déclenchée juste après l'ajout (best-effort, voir
  // api/routes/ingestion.py::ajouter_commande) — distinct de `erreur` ci-dessous, qui ne porte
  // que sur l'ajout de la commande lui-même (toujours un succès à ce stade).
  const [dernierResultatExecution, setDernierResultatExecution] = useState<{
    reussie: boolean | null;
    erreur: string | null;
  } | null>(null);
  // Avertissements d'éclatement (§FC4) — ex. étape ignorée parce qu'aucune ressource de l'atelier
  // ne sait la faire. Vide (jamais null) tant qu'aucune commande n'a été ajoutée.
  const [dernierAvertissements, setDernierAvertissements] = useState<string[]>([]);

  const erreur = ajouter.error as PrismeAPIError | null;
  const quantiteNombre = Number(quantite);
  const quantiteValide = Number.isInteger(quantiteNombre) && quantiteNombre >= 1;

  const competencesAtelier = useMemo(
    () => [...new Set(instance.ressources.flatMap((r) => r.competences ?? []))].sort(),
    [instance.ressources],
  );

  function basculerEdition(actif: boolean) {
    setEditionProcessus(actif);
    onEditionProcessus?.(actif);
  }

  function ouvrir() {
    setQuantite("1");
    setDateLimite("");
    setDateDebutAuPlusTot("");
    setNumero("");
    setDescription("");
    setNomClient("");
    setDernierCommandeId(null);
    setDernierResultatExecution(null);
    setDernierAvertissements([]);
    ajouter.reset();
    setOuvert(true);
  }

  function soumettre() {
    // "jours" ou "heures" selon instance.unite_temps — un input date perd toute précision
    // horaire pour une instance en mode heures (voir uniteTemps ci-dessus).
    const date =
      uniteTemps === "heures" ? parseEntreeDateHeure(dateLimite) : parseEntreeDate(dateLimite);
    const dateDebut =
      uniteTemps === "heures"
        ? parseEntreeDateHeure(dateDebutAuPlusTot)
        : parseEntreeDate(dateDebutAuPlusTot);
    ajouter.mutate(
      {
        instanceId: instance.instance_id,
        requete: {
          quantite: quantiteNombre,
          // Convertie en jours/heures relatifs à "aujourd'hui" — aucune exécution réelle n'existe
          // forcément encore pour ancrer sur autre chose au moment de la saisie (voir
          // src/lib/dates-relatives.ts). Le DSL/backend ne voit jamais que cet entier.
          date_limite: date ? jourDepuisAncrage(date, aujourdhui(), uniteTemps) : undefined,
          date_debut_au_plus_tot: dateDebut
            ? jourDepuisAncrage(dateDebut, aujourdhui(), uniteTemps)
            : undefined,
          numero: numero !== "" ? numero : undefined,
          description: description !== "" ? description : undefined,
          nom_client: nomClient !== "" ? nomClient : undefined,
        },
      },
      {
        onSuccess: (resultat) => {
          queryClient.invalidateQueries({ queryKey: prismeKeys.instance(instance.instance_id) });
          queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
          queryClient.invalidateQueries({
            queryKey: prismeKeys.commandesInstance(instance.instance_id),
          });
          queryClient.invalidateQueries({ queryKey: prismeKeys.commandes() });
          // L'ajout vient de déclencher une exécution automatique best-effort côté serveur —
          // rafraîchit les vues qui affichent des exécutions/plannings sans action séparée.
          queryClient.invalidateQueries({ queryKey: prismeKeys.executions() });
          setDernierCommandeId(resultat.commande_id);
          setDernierResultatExecution({
            reussie: resultat.execution_reussie,
            erreur: resultat.erreur_execution,
          });
          setDernierAvertissements(resultat.avertissements);
          setOuvert(false);
          onCommandeAjoutee?.(resultat);
        },
      },
    );
  }

  if (editionProcessus) {
    return (
      <div className="space-y-3">
        <div>
          <h4 className="text-sm font-semibold">
            {etapes.length > 0
              ? "Modifier le processus de l'atelier"
              : "Définir le processus de l'atelier"}
          </h4>
          <p className="text-xs text-muted-foreground">
            Toutes les commandes suivantes suivront ce processus. Les commandes déjà créées gardent
            le leur.
            {etapes.length === 0 &&
              etapesProposees.length > 0 &&
              " Les tâches de l'atelier sont proposées comme étapes : vérifiez-les, puis enregistrez."}
          </p>
        </div>
        <AvertissementEnchainements etapes={etapes.length > 0 ? etapes : etapesProposees} />
        <EditeurProcessus
          instanceId={instance.instance_id}
          etapes={etapes.length > 0 ? etapes : etapesProposees}
          uniteTemps={uniteTemps}
          competencesAtelier={competencesAtelier}
          tachesAtelier={etapesProposees}
          onEnregistre={() => basculerEdition(false)}
          onAnnuler={() => basculerEdition(false)}
        />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {!integre && (
        <div className="flex items-center justify-between">
          <h4 className="text-sm font-semibold">Commandes</h4>
          {!ouvert && (
            <Button size="sm" variant="outline" onClick={ouvrir}>
              <Plus className="mr-1.5 h-3.5 w-3.5" /> Nouvelle commande
            </Button>
          )}
        </div>
      )}

      {(ouvert || integre) && (
        <div className={integre ? "space-y-3" : "space-y-3 rounded-lg border border-border/50 p-3"}>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <Label>Processus de l'atelier</Label>
              {etapes.length > 0 && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7"
                  onClick={() => basculerEdition(true)}
                >
                  <Pencil className="mr-1.5 h-3.5 w-3.5" /> Modifier
                </Button>
              )}
            </div>
            {!processus.isLoading && (
              <AvertissementEnchainements etapes={etapes.length > 0 ? etapes : etapesProposees} />
            )}
            {processus.isLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : etapes.length > 0 ? (
              <ApercuProcessus
                etapes={etapes}
                quantite={quantiteValide ? quantiteNombre : 1}
                uniteTemps={uniteTemps}
              />
            ) : (
              <div className="space-y-2 rounded-lg border border-dashed border-border p-3 text-sm">
                <p className="text-muted-foreground">
                  Cet atelier n'a pas encore de processus.{" "}
                  {etapesProposees.length > 0
                    ? `Ses ${etapesProposees.length} étapes sont déjà proposées à partir de ses tâches (une tâche = une étape) : vérifiez-les et enregistrez, chaque commande les reprendra.`
                    : "Définissez une fois ses étapes et leur ordre : chaque commande les reprendra."}
                </p>
                <Button type="button" size="sm" onClick={() => basculerEdition(true)}>
                  <Workflow className="mr-1.5 h-3.5 w-3.5" />{" "}
                  {etapesProposees.length > 0
                    ? "Vérifier le processus proposé"
                    : "Définir le processus"}
                </Button>
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="space-y-1">
              <Label htmlFor="commande-quantite">Quantité *</Label>
              <Input
                id="commande-quantite"
                type="number"
                min={1}
                step={1}
                inputMode="numeric"
                aria-invalid={!quantiteValide}
                value={quantite}
                onChange={(e) => setQuantite(e.target.value)}
                className={quantiteValide ? "" : "border-destructive"}
              />
            </div>
            <div className="space-y-1 sm:col-span-2">
              <Label htmlFor="commande-numero">Numéro de commande</Label>
              <Input
                id="commande-numero"
                placeholder="Optionnel — libellé métier libre (ex. P1)"
                value={numero}
                onChange={(e) => setNumero(e.target.value)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="commande-debut">Date de début au plus tôt</Label>
              <Input
                id="commande-debut"
                type={uniteTemps === "heures" ? "datetime-local" : "date"}
                min={
                  uniteTemps === "heures"
                    ? formatEntreeDateHeure(aujourdhui())
                    : formatEntreeDate(aujourdhui())
                }
                value={dateDebutAuPlusTot}
                onChange={(e) => setDateDebutAuPlusTot(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="commande-echeance">Échéance *</Label>
              <Input
                id="commande-echeance"
                type={uniteTemps === "heures" ? "datetime-local" : "date"}
                min={
                  uniteTemps === "heures"
                    ? formatEntreeDateHeure(aujourdhui())
                    : formatEntreeDate(aujourdhui())
                }
                required
                value={dateLimite}
                onChange={(e) => setDateLimite(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="commande-client">Client</Label>
            <Input
              id="commande-client"
              placeholder="Optionnel"
              value={nomClient}
              onChange={(e) => setNomClient(e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <Label htmlFor="commande-description">Description</Label>
            <Textarea
              id="commande-description"
              placeholder="Optionnel"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
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
              onClick={() => (integre && onAnnuler ? onAnnuler() : setOuvert(false))}
              disabled={ajouter.isPending}
            >
              Annuler
            </Button>
            <Button
              size="sm"
              onClick={soumettre}
              disabled={etapes.length === 0 || !quantiteValide || !dateLimite || ajouter.isPending}
            >
              {ajouter.isPending ? "Ajout..." : "Ajouter la commande"}
            </Button>
          </div>
        </div>
      )}

      {!integre && dernierCommandeId && (
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Commande {dernierCommandeId} créée.</p>
          {dernierResultatExecution?.reussie === true && (
            <p className="text-xs text-muted-foreground">
              Exécution automatique déclenchée — planning mis à jour.
            </p>
          )}
          {dernierResultatExecution?.reussie === false && (
            <p className="text-xs text-amber-600">
              Exécution automatique déclenchée mais échouée : {dernierResultatExecution.erreur}
            </p>
          )}
          {dernierResultatExecution?.reussie === null && dernierResultatExecution.erreur && (
            <p className="text-xs text-amber-600">
              Exécution automatique non disponible : {dernierResultatExecution.erreur}
            </p>
          )}
          {dernierAvertissements.map((a, i) => (
            <p key={i} className="text-xs text-amber-600">
              {a}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

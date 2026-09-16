import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  prismeKeys,
  useAjouterCommande,
  PrismeAPIError,
  type CompatibiliteRessourceTache,
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

// Une tâche est compatible avec une ou plusieurs ressources, chacune avec sa propre durée (FJSP
// flexible, voir CLAUDE.md) — jamais une durée unique garantie par tâche. Renvoie `null` si la
// tâche n'a aucune compatibilité déclarée (ne devrait pas arriver, garde-fou §6.7 amont), sinon
// une durée unique ou un intervalle min–max selon que les ressources compatibles partagent la
// même durée ou non.
function libelleDureeTache(tacheId: string, instance: InstanceDetail): string | null {
  const durees = instance.contraintes
    .filter(
      (c): c is CompatibiliteRessourceTache =>
        c.type === "compatibilite_ressource_tache" && c.tache === tacheId,
    )
    .map((c) => c.duree);
  if (durees.length === 0) return null;
  const min = Math.min(...durees);
  const max = Math.max(...durees);
  const uniteTemps: UniteTemps = instance.unite_temps === "heures" ? "heures" : "jours";
  return min === max
    ? formatDureeCourte(min, uniteTemps)
    : `${formatDureeCourte(min, uniteTemps)}–${formatDureeCourte(max, uniteTemps)}`;
}

/**
 * Formulaire d'ajout d'une commande à une instance donnée — une commande relie des tâches déjà
 * présentes dans l'instance à une échéance client. Partagé entre l'onglet Flux d'une instance
 * (`routes/_authenticated/instances.tsx::SectionNouvelleCommande`, `instance` déjà fixée par le
 * contexte) et la page Commandes (`routes/_authenticated/commandes.tsx`, `instance` choisie via
 * un sélecteur d'atelier) — même formulaire, jamais dupliqué. Les gammes (produits → suite de
 * tâches) restent gérables depuis la page Gammes et consommables via l'API, mais volontairement
 * absentes de ce formulaire.
 */
export function FormulaireNouvelleCommande({
  instance,
  onCommandeAjoutee,
}: {
  instance: InstanceDetail;
  /** Appelé en plus de l'invalidation déjà faite ici (instance, instances, commandes de
   * l'instance, commandes globales, exécutions) — ex. fermer un dialogue englobant. */
  onCommandeAjoutee?: (resultat: ResultatNouvelleCommande) => void;
}) {
  const queryClient = useQueryClient();
  const ajouter = useAjouterCommande();
  const [ouvert, setOuvert] = useState(false);
  const [tachesChoisies, setTachesChoisies] = useState<string[]>([]);
  const [dateLimite, setDateLimite] = useState("");
  const [dateDebutAuPlusTot, setDateDebutAuPlusTot] = useState("");
  const [dureeHeures, setDureeHeures] = useState("");
  const [numero, setNumero] = useState("");
  const [estProspect, setEstProspect] = useState(false);
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
  // Avertissements de dérivation (§FC4) — ex. durée d'une étape de gamme comblée par
  // apprentissage automatique plutôt que déclarée. Vide (jamais null) tant qu'aucune commande
  // n'a encore été ajoutée dans cette ouverture du formulaire.
  const [dernierAvertissements, setDernierAvertissements] = useState<string[]>([]);

  const erreur = ajouter.error as PrismeAPIError | null;

  function ouvrir() {
    setTachesChoisies([]);
    setDateLimite("");
    setDateDebutAuPlusTot("");
    setDureeHeures("");
    setNumero("");
    setEstProspect(false);
    setDescription("");
    setNomClient("");
    setDernierCommandeId(null);
    setDernierResultatExecution(null);
    setDernierAvertissements([]);
    ajouter.reset();
    setOuvert(true);
  }

  function basculerTache(tacheId: string) {
    setTachesChoisies((prev) =>
      prev.includes(tacheId) ? prev.filter((id) => id !== tacheId) : [...prev, tacheId],
    );
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
          taches: tachesChoisies,
          // Convertie en jours/heures relatifs à "aujourd'hui" — aucune exécution réelle n'existe
          // forcément encore pour ancrer sur autre chose au moment de la saisie (voir
          // src/lib/dates-relatives.ts). Le DSL/backend ne voit jamais que cet entier.
          date_limite: date ? jourDepuisAncrage(date, aujourdhui(), uniteTemps) : undefined,
          date_debut_au_plus_tot: dateDebut
            ? jourDepuisAncrage(dateDebut, aujourdhui(), uniteTemps)
            : undefined,
          duree_heures: dureeHeures !== "" ? Number(dureeHeures) : undefined,
          numero: numero !== "" ? numero : undefined,
          est_prospect: estProspect,
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
          // L'ajout vient de déclencher une exécution automatique best-effort côté serveur (voir
          // api/routes/ingestion.py::ajouter_commande) — rafraîchit les vues qui affichent des
          // exécutions/plannings (Centre d'exécution, Plannings) pour qu'elles la montrent sans
          // attendre une action séparée.
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

      {ouvert && (
        <div className="space-y-3 rounded-lg border border-border/50 p-3">
          <div className="space-y-1">
            <Label>Numéro de commande</Label>
            <Input
              placeholder="Optionnel — libellé métier libre (ex. P1)"
              value={numero}
              onChange={(e) => setNumero(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div className="space-y-1">
              <Label>Date de début au plus tôt</Label>
              <Input
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
              <Label>Échéance *</Label>
              <Input
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

          <label className="flex items-center gap-2 text-sm">
            <Checkbox checked={estProspect} onCheckedChange={(v) => setEstProspect(v === true)} />
            Cette commande est-elle un prospect ?
          </label>

          <div className="space-y-1">
            <Label>Description</Label>
            <Textarea
              placeholder="Optionnel"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <Label>Client</Label>
            <Input
              placeholder="Optionnel"
              value={nomClient}
              onChange={(e) => setNomClient(e.target.value)}
            />
          </div>

          <div className="space-y-1">
            <Label>Tâches concernées</Label>
            <div className="max-h-40 space-y-1.5 overflow-y-auto rounded-md border border-border/50 p-2">
              {instance.taches.map((t) => {
                const duree = libelleDureeTache(t.id, instance);
                return (
                  <label key={t.id} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={tachesChoisies.includes(t.id)}
                      onCheckedChange={() => basculerTache(t.id)}
                    />
                    <span>{t.nom ? `${t.nom} (${t.id})` : t.id}</span>
                    {duree && <span className="text-xs text-muted-foreground">· {duree}</span>}
                  </label>
                );
              })}
            </div>
          </div>

          <div className="space-y-1">
            <Label>Durée globale prévue (heures)</Label>
            <Input
              type="number"
              min={0}
              step={1}
              placeholder="Optionnel — indicatif, sans effet sur la planification"
              value={dureeHeures}
              onChange={(e) => setDureeHeures(e.target.value)}
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
              disabled={tachesChoisies.length === 0 || !dateLimite || ajouter.isPending}
            >
              {ajouter.isPending ? "Ajout..." : "Ajouter la commande"}
            </Button>
          </div>
        </div>
      )}

      {dernierCommandeId && (
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

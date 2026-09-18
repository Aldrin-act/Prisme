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

// Durée actuelle d'une tâche quand toutes ses ressources compatibles la partagent — sert à
// préremplir le champ de durée de la tâche. `null` si elles diffèrent : le champ reste vide et
// les durées par ressource de l'atelier sont conservées tant que rien n'est saisi.
function dureeUniqueTache(tacheId: string, instance: InstanceDetail): number | null {
  const durees = new Set(
    instance.contraintes
      .filter(
        (c): c is CompatibiliteRessourceTache =>
          c.type === "compatibilite_ressource_tache" && c.tache === tacheId,
      )
      .map((c) => c.duree),
  );
  return durees.size === 1 ? [...durees][0] : null;
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
  onAnnuler,
  integre = false,
}: {
  instance: InstanceDetail;
  /** Appelé en plus de l'invalidation déjà faite ici (instance, instances, commandes de
   * l'instance, commandes globales, exécutions) — ex. fermer un dialogue englobant. */
  onCommandeAjoutee?: (resultat: ResultatNouvelleCommande) => void;
  /** Mode `integre` : appelé par « Annuler » à la place de replier le formulaire. */
  onAnnuler?: () => void;
  /** Formulaire déjà ouvert, sans titre ni bouton « Nouvelle commande » ni récapitulatif — pour
   * un conteneur (ex. dialogue de la page Commandes) qui porte déjà ces éléments lui-même. */
  integre?: boolean;
}) {
  const queryClient = useQueryClient();
  const ajouter = useAjouterCommande();
  const [ouvert, setOuvert] = useState(integre);
  const [tachesChoisies, setTachesChoisies] = useState<string[]>([]);
  const [dateLimite, setDateLimite] = useState("");
  const [dateDebutAuPlusTot, setDateDebutAuPlusTot] = useState("");
  // Durée saisie par tâche cochée (texte brut de l'input, unité de l'instance) — chaque tâche a la
  // sienne, jamais une durée globale partagée par toute la commande.
  const [dureesTaches, setDureesTaches] = useState<Record<string, string>>({});
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
    setDureesTaches({});
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
    const dejaChoisie = tachesChoisies.includes(tacheId);
    setTachesChoisies((prev) =>
      dejaChoisie ? prev.filter((id) => id !== tacheId) : [...prev, tacheId],
    );
    setDureesTaches((prev) => {
      const suivant = { ...prev };
      if (dejaChoisie) {
        delete suivant[tacheId];
      } else {
        const actuelle = dureeUniqueTache(tacheId, instance);
        suivant[tacheId] = actuelle !== null ? String(actuelle) : "";
      }
      return suivant;
    });
  }

  function dureeSaisieInvalide(valeur: string): boolean {
    const v = valeur.trim();
    return v !== "" && !(Number.isInteger(Number(v)) && Number(v) >= 1);
  }

  // Seules les durées réellement renseignées partent au serveur ; une durée identique à celle
  // déjà en place est omise aussi — rien à remplacer, et une tâche à durées différentes selon la
  // ressource n'est jamais uniformisée sans saisie explicite.
  const dureesAEnvoyer: Record<string, number> = Object.fromEntries(
    tachesChoisies
      .map((id) => [id, (dureesTaches[id] ?? "").trim()] as const)
      .filter(([id, v]) => v !== "" && Number(v) !== dureeUniqueTache(id, instance))
      .map(([id, v]) => [id, Number(v)]),
  );
  const dureeInvalide = tachesChoisies.some((id) => dureeSaisieInvalide(dureesTaches[id] ?? ""));
  const abreviationUnite = uniteTemps === "heures" ? "h" : "j";

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
          durees_taches: Object.keys(dureesAEnvoyer).length > 0 ? dureesAEnvoyer : undefined,
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
          // exécutions/plannings (Plannings) pour qu'elles la montrent sans
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
            <Label>Tâches concernées et durée de chacune</Label>
            <div className="max-h-56 space-y-1 overflow-y-auto rounded-md border border-border/50 p-2">
              {instance.taches.map((t) => {
                const duree = libelleDureeTache(t.id, instance);
                const choisie = tachesChoisies.includes(t.id);
                const valeur = dureesTaches[t.id] ?? "";
                const invalide = dureeSaisieInvalide(valeur);
                return (
                  <div
                    key={t.id}
                    className={`flex min-h-9 items-center gap-2 rounded px-1 text-sm ${
                      choisie ? "bg-primary/5" : ""
                    }`}
                  >
                    <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-2">
                      <Checkbox checked={choisie} onCheckedChange={() => basculerTache(t.id)} />
                      <span className="truncate">{t.nom ? `${t.nom} (${t.id})` : t.id}</span>
                      {!choisie && duree && (
                        <span className="shrink-0 text-xs text-muted-foreground">· {duree}</span>
                      )}
                    </label>
                    {choisie && (
                      <div className="flex shrink-0 items-center gap-1">
                        <Input
                          type="number"
                          min={1}
                          step={1}
                          inputMode="numeric"
                          aria-label={`Durée de ${t.id} (${uniteTemps})`}
                          aria-invalid={invalide}
                          placeholder={duree ?? "durée"}
                          value={valeur}
                          onChange={(e) =>
                            setDureesTaches((prev) => ({ ...prev, [t.id]: e.target.value }))
                          }
                          className={`h-8 w-24 text-right ${invalide ? "border-destructive" : ""}`}
                        />
                        <span className="w-3 text-xs text-muted-foreground">
                          {abreviationUnite}
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-muted-foreground">
              Chaque tâche cochée a sa propre durée, en {uniteTemps}. Elle remplace la durée de la
              tâche dans l'atelier et le planning en tient compte. Laisser vide pour garder la durée
              actuelle.
            </p>
            {dureeInvalide && (
              <p className="text-xs text-destructive">
                Une durée doit être un nombre entier supérieur ou égal à 1.
              </p>
            )}
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
              disabled={
                tachesChoisies.length === 0 || !dateLimite || dureeInvalide || ajouter.isPending
              }
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

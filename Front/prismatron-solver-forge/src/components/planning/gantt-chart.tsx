import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AlertCircle, RotateCcw, Save, Search, Tag, ZoomIn, ZoomOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  prismeKeys,
  useAjusterPlanning,
  useDeclarerRetardTache,
  useDeclencherExecution,
  PrismeAPIError,
  type Contrainte,
  type OperationPlanifiee,
  type PlanningAvecDurees,
  type StatutCommande,
  type Tache,
} from "@/integrations/prisme";
import { tachesEnRetard, tauxUtilisationRessource } from "@/lib/charge-ressources";
import {
  dateDepuisAncrage,
  debutJour,
  formatDateRelative,
  formatEntreeDate,
  formatEntreeDateHeure,
  formatHeure,
  formatJour,
  jourDepuisAncrage,
  parseEntreeDate,
  parseEntreeDateHeure,
  type UniteTemps,
} from "@/lib/dates-relatives";
import { HEURE_FERMETURE, HEURE_OUVERTURE, estInstantOuvre } from "@/lib/calendrier-ouvre";
import { finCalendaire, segmentsTravailles } from "@/lib/calendrier-ouvre";
import { finRepetitionParTache, segmentsRepetition } from "@/lib/repetition-commande";

function cle(op: { tache: string; ressource: string }): string {
  return `${op.tache}|${op.ressource}`;
}

// Plages non ouvrées marquées sur le Gantt (voir estInstantOuvre) ; segments consécutifs fusionnés
// en un seul, pour un rendu propre sans trait de jointure.
function segmentsNonOuvres(
  makespan: number,
  ancrage: Date,
  unite: UniteTemps,
): { debut: number; fin: number }[] {
  const segments: { debut: number; fin: number }[] = [];
  let debutCourant: number | null = null;
  for (let instant = 0; instant < makespan; instant++) {
    const nonOuvre = !estInstantOuvre(instant, ancrage, unite);
    if (nonOuvre && debutCourant === null) {
      debutCourant = instant;
    } else if (!nonOuvre && debutCourant !== null) {
      segments.push({ debut: debutCourant, fin: instant });
      debutCourant = null;
    }
  }
  if (debutCourant !== null) segments.push({ debut: debutCourant, fin: makespan });
  return segments;
}

// Ni `fin` ni `makespan` n'existent sur le fil (`dsl/schema/planning.py` est
// volontairement permissif) — `fin` se déduit de `debut + durees["tache|ressource"]`.
// `duree` = heures travaillées ; `fin` = fin réelle, pauses (nuit, week-end) comprises en mode heures
// (voir `lib/calendrier-ouvre.ts`) — égale à `debut + duree` en mode jours.
function operationsAvecFin(
  operations: OperationPlanifiee[],
  durees: Record<string, number>,
  ancrage: Date,
  unite: UniteTemps,
) {
  return operations.map((op) => {
    const duree = durees[cle(op)] ?? 0;
    return { ...op, duree, fin: finCalendaire(op.debut, duree, ancrage, unite) };
  });
}

interface EtatDrag {
  cle: string;
  xDepart: number;
  debutDepart: number;
}

// Échelle fixe en pixels/unité (plutôt qu'un % de la durée totale) — une unité vaut un jour ou
// une heure selon `InstanceTRCO.unite_temps` (voir `uniteDuree` ci-dessous) : le DSL ne connaît
// que des entiers dans l'unité déclarée, jamais une précision plus fine. Constantes plus
// resserrées en mode heures : un planning de même durée réelle y compte ~24x plus d'unités.
const ECHELLE_PAR_UNITE: Record<
  UniteTemps,
  { defaut: number; min: number; max: number; pas: number }
> = {
  jours: { defaut: 48, min: 16, max: 160, pas: 16 },
  heures: { defaut: 8, min: 2, max: 48, pas: 2 },
};
const LARGEUR_COL_RESSOURCE = 144; // == w-36, dupliqué en px pour aligner l'offset de l'en-tête
// Largeur réservée hors de la piste, sur une ligne de ressource : colonne du taux d'utilisation
// (w-24 = 96) + gouttières.
const LARGEUR_HORS_PISTE = LARGEUR_COL_RESSOURCE + 12 + 96 + 24;
// Échelle maximale de l'ajustement automatique en mode jours — au-delà, un planning de quelques
// jours donnerait des barres démesurées. En mode heures, le plafond est celui du zoom manuel.
const AJUSTEMENT_MAX_JOURS = 96;

export function GanttChart({
  planning,
  contraintes,
  taches,
  commandes,
  uniteDuree,
  editable = false,
  executionId,
  onAjustementReussi,
  instanceId,
}: {
  planning: PlanningAvecDurees;
  // Optionnelle : sans elle, la colonne taux d'utilisation ne s'affiche
  // simplement pas plutôt que d'afficher un chiffre faux.
  contraintes?: Contrainte[];
  // Optionnelle : sans elle, les barres n'affichent que l'identifiant de tâche (pas de produit).
  taches?: Tache[];
  // Optionnelle : sans elle, aucune commande n'est affichée sur les barres ni d'échéance
  // marquée sur l'axe (voir GET /ingestion/{instance_id}/commandes). `date_limite` est sur le
  // même référentiel que `op.debut`/`op.fin` — comparable et positionnable directement sur cet
  // axe, aucune conversion nécessaire.
  commandes?: StatutCommande[];
  // "heures" bascule l'ancrage/l'échelle/le libellé des barres sur une précision horaire —
  // toute autre valeur (dont absente/null, l'instance n'a jamais été en mode heures) reste
  // "jours", comportement historique inchangé.
  uniteDuree?: string | null;
  // Gantt interactif (Phase 3) : glisser une barre change son instant de début (jamais sa
  // ressource — contraint à l'axe horizontal de sa propre ligne). `executionId` requis pour
  // pouvoir soumettre l'ajustement ; sans lui, `editable` reste sans effet.
  editable?: boolean;
  executionId?: string;
  onAjustementReussi?: (planning: PlanningAvecDurees) => void;
  // Requis pour "Déclarer un retard" dans le panneau de détail d'une opération — corrige la
  // durée réellement constatée sur une tâche/ressource, jamais détecté automatiquement (PRISME
  // n'a aucun capteur d'atelier en direct, voir api/routes/ingestion.py::declarer_retard_tache).
  // Sans cette prop, le panneau de détail reste en lecture seule comme avant.
  instanceId?: string;
}) {
  const queryClient = useQueryClient();
  const ajuster = useAjusterPlanning();
  const declarerRetard = useDeclarerRetardTache();
  const executerApresRetard = useDeclencherExecution();
  const [dureeCorrigee, setDureeCorrigee] = useState("");
  const unite: UniteTemps = uniteDuree === "heures" ? "heures" : "jours";
  const echelle = ECHELLE_PAR_UNITE[unite];
  // Instant 0 ancré sur la date réelle de l'exécution. Normalisé à minuit local en mode jours
  // (l'arithmétique "+N jours" reste exacte quelle que soit l'heure à laquelle le solveur a
  // tourné) ; gardé à sa précision complète en mode heures (l'heure exacte de l'exécution EST
  // l'ancrage, la tronquer perdrait l'information que l'unité existe justement pour capturer).
  const ancrage =
    unite === "heures"
      ? new Date(planning.date_execution)
      : debutJour(new Date(planning.date_execution));
  const formatAxe = (instant: number) => formatDateRelative(instant, ancrage, unite);
  const [operationsLocales, setOperationsLocales] = useState(planning.operations);
  const [drag, setDrag] = useState<EtatDrag | null>(null);
  const [pxParJour, setPxParJour] = useState(echelle.defaut);
  // Filtre d'affichage "du ... au ..." (Phase 3bis) — ne restreint jamais les données, seulement
  // la fenêtre visible du Gantt : les mêmes chaînes de saisie que les champs Échéance ailleurs
  // (`formatEntreeDate`/`formatEntreeDateHeure`), vides par défaut (aucun filtre, vue complète).
  const [filtreDebut, setFiltreDebut] = useState("");
  const [filtreFin, setFiltreFin] = useState("");
  // Recherche (tâche/produit/commande) : atténue les barres non correspondantes plutôt que de les
  // masquer — garde le contexte (charge de la ressource, opérations voisines) visible.
  const [recherche, setRecherche] = useState("");
  // Opération choisie pour le panneau de détail (clic sur une barre) — identifiée par sa clé
  // (tâche|ressource) plutôt que copiée en state, pour toujours refléter operationsLocales à
  // jour (ex. après un glissement en mode éditable).
  const [operationDetailCle, setOperationDetailCle] = useState<string | null>(null);
  const conteneurScrollRef = useRef<HTMLDivElement>(null);
  // Largeur disponible pour le Gantt, et zoom choisi à la main : tant que l'utilisateur n'a pas
  // touché au zoom, l'échelle s'ajuste pour que tout le planning tienne à l'écran — un planning de
  // quelques heures n'est plus réduit à une bande de 90 px sur une page vide.
  const [largeurDisponible, setLargeurDisponible] = useState(0);
  const zoomManuel = useRef(false);

  // Toute nouvelle version du planning affiché (nouvelle exécution, bascule
  // original/ajusté...) réinitialise l'édition en cours et le zoom — jamais un mélange
  // entre deux plannings différents. `ajuster` exclu volontairement : son
  // identité change à chaque mutation, la réintégrer redéclencherait cet
  // effet et effacerait l'édition en cours pile au moment d'afficher un
  // refus (violations).
  useEffect(() => {
    setOperationsLocales(planning.operations);
    setPxParJour(echelle.defaut);
    zoomManuel.current = false;
    setFiltreDebut("");
    setFiltreFin("");
    setRecherche("");
    setOperationDetailCle(null);
    ajuster.reset();
    declarerRetard.reset();
    executerApresRetard.reset();
    setDureeCorrigee("");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [planning]);

  const peutEditer = editable && !!executionId;
  const operations = operationsAvecFin(operationsLocales, planning.durees, ancrage, unite);
  const makespan = operations.length > 0 ? Math.max(...operations.map((op) => op.fin)) : 0;
  // Recalculé sur `operationsLocales` (pas `planning.operations`) : glisser une barre au-delà de
  // son échéance la fait passer au rouge immédiatement, avant même d'enregistrer l'ajustement —
  // "voir tout de suite l'effet d'un changement".
  const tachesEnRetardIds = new Set(
    (contraintes ? tachesEnRetard(operations, contraintes) : []).map((r) => r.tache),
  );
  const estModifie = JSON.stringify(operationsLocales) !== JSON.stringify(planning.operations);
  const clesModifiees = new Set(
    operationsLocales
      .filter((op, i) => op.debut !== planning.operations[i]?.debut)
      .map((op) => cle(op)),
  );
  const produitParTache = new Map((taches ?? []).map((t) => [t.id, t.produit]));

  const commandesParTache = new Map<string, StatutCommande[]>();
  const commandesParEcheance = new Map<number, StatutCommande[]>();
  for (const commande of commandes ?? []) {
    for (const tache of commande.taches) {
      commandesParTache.set(tache, [...(commandesParTache.get(tache) ?? []), commande]);
    }
    if (commande.date_limite !== null) {
      commandesParEcheance.set(commande.date_limite, [
        ...(commandesParEcheance.get(commande.date_limite) ?? []),
        commande,
      ]);
    }
  }

  // Jusqu'où chaque tâche de commande se répète (voir finRepetitionParTache) — calculé sur
  // `operations`, donc à jour après un glissement.
  const finRepetition = finRepetitionParTache(commandes ?? [], operations);

  // Horizon servant à l'ajustement : celui du planning d'origine (pas de `operationsLocales`), pour
  // que glisser une barre ne fasse jamais sauter l'échelle.
  const operationsOrigine = operationsAvecFin(planning.operations, planning.durees, ancrage, unite);
  const horizonAjustement = Math.max(
    1,
    ...operationsOrigine.map((op) => op.fin),
    ...finRepetitionParTache(commandes ?? [], operationsOrigine).values(),
  );
  const aDesOperations = operations.length > 0 && makespan > 0;
  const echelleAjustee =
    largeurDisponible > 0
      ? Math.min(
          unite === "heures" ? echelle.max : AJUSTEMENT_MAX_JOURS,
          Math.max(
            echelle.min,
            Math.floor((largeurDisponible - LARGEUR_HORS_PISTE) / horizonAjustement),
          ),
        )
      : echelle.defaut;

  // Mesure la largeur du conteneur (monté seulement quand il y a des opérations à afficher).
  useEffect(() => {
    const conteneur = conteneurScrollRef.current;
    if (!conteneur) return;
    const mesurer = () => setLargeurDisponible(conteneur.clientWidth);
    mesurer();
    const observateur = new ResizeObserver(mesurer);
    observateur.observe(conteneur);
    return () => observateur.disconnect();
  }, [aDesOperations]);

  // Déclaré après l'effet de réinitialisation ci-dessus : à chaque nouveau planning, celui-ci
  // l'emporte sur `echelle.defaut`.
  useEffect(() => {
    if (!zoomManuel.current) setPxParJour(echelleAjustee);
  }, [echelleAjustee, planning]);

  function reinitialiser() {
    setOperationsLocales(planning.operations);
    ajuster.reset();
  }

  function enregistrer() {
    if (!executionId) return;
    ajuster.mutate(
      { executionId, planning: { operations: operationsLocales } },
      {
        onSuccess: (reponse) => {
          if (reponse.legal && reponse.planning) {
            queryClient.invalidateQueries({ queryKey: prismeKeys.planningAjuste(executionId) });
            onAjustementReussi?.(reponse.planning);
          }
        },
      },
    );
  }

  // Suivi du pointeur pour toute barre, éditable ou non — seule la réécriture réelle de
  // `operationsLocales` (dans onPointerMoveBarre) reste conditionnée à `peutEditer` ; ce suivi
  // sert aussi à distinguer un clic (ouvre le panneau de détail) d'un glissement, voir
  // onPointerUpBarre ci-dessous.
  function onPointerDownBarre(
    e: React.PointerEvent<HTMLDivElement>,
    cleOp: string,
    debutActuel: number,
  ) {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDrag({ cle: cleOp, xDepart: e.clientX, debutDepart: debutActuel });
  }

  // Échelle fixe (pxParJour) : le delta en jours ne dépend plus de la largeur de la piste, une
  // simple division par l'échelle courante suffit (et reste correcte si le zoom change en cours
  // de glissement, relu à chaque évènement plutôt que figé au pointerdown).
  function onPointerMoveBarre(e: React.PointerEvent<HTMLDivElement>) {
    if (!drag || !peutEditer) return;
    const deltaJours = Math.round((e.clientX - drag.xDepart) / pxParJour);
    const nouveauDebut = Math.max(0, drag.debutDepart + deltaJours);
    setOperationsLocales((ops) =>
      ops.map((op) => (cle(op) === drag.cle ? { ...op, debut: nouveauDebut } : op)),
    );
  }

  // Un relâchement quasi sur place (jamais de vrai glissement, ou `editable` désactivé) ouvre le
  // panneau de détail plutôt que de valider un déplacement — seuil de quelques pixels pour
  // absorber le tremblement naturel d'un clic.
  function onPointerUpBarre(e: React.PointerEvent<HTMLDivElement>, cleOp: string) {
    const aReellementGlisse = drag !== null && Math.abs(e.clientX - drag.xDepart) > 3;
    if (!aReellementGlisse) {
      setOperationDetailCle(cleOp);
      declarerRetard.reset();
      executerApresRetard.reset();
      setDureeCorrigee("");
    }
    setDrag(null);
  }

  function ajusterALaFenetre() {
    zoomManuel.current = false;
    setPxParJour(echelleAjustee);
  }

  function zoomer(sens: 1 | -1) {
    zoomManuel.current = true;
    setPxParJour((p) => Math.min(echelle.max, Math.max(echelle.min, p + sens * echelle.pas)));
  }

  if (operations.length === 0 || makespan === 0) {
    return <p className="text-sm text-muted-foreground">Aucune opération planifiée.</p>;
  }

  const parRessource = new Map<string, typeof operations>();
  for (const op of operations) {
    const liste = parRessource.get(op.ressource) ?? [];
    liste.push(op);
    parRessource.set(op.ressource, liste);
  }
  for (const liste of parRessource.values()) {
    liste.sort((a, b) => a.debut - b.debut);
  }
  const ressources = [...parRessource.keys()].sort();

  // Horizon de l'axe : le makespan, étendu jusqu'à la fin de répétition des tâches de commande
  // (échéance parfois bien après la dernière opération planifiée) pour que les blocs répétés soient
  // visibles. `makespan` reste la vraie fin du planning, seule base du taux d'utilisation.
  const horizon = Math.max(makespan, ...finRepetition.values());
  const jours = Array.from({ length: horizon }, (_, i) => i);
  const nonOuvres = segmentsNonOuvres(horizon, ancrage, unite);
  const violations = ajuster.data && !ajuster.data.legal ? ajuster.data.violations : [];

  // Fenêtre visible (bornes en instants, jamais négatives ni au-delà de l'horizon) — un filtre
  // vide de chaque côté retombe sur la vue complète, comportement historique inchangé.
  const parseEntree = unite === "heures" ? parseEntreeDateHeure : parseEntreeDate;
  const instantFiltreDebut = filtreDebut
    ? jourDepuisAncrage(parseEntree(filtreDebut)!, ancrage, unite)
    : null;
  const instantFiltreFin = filtreFin
    ? jourDepuisAncrage(parseEntree(filtreFin)!, ancrage, unite)
    : null;
  const bornDebut = Math.min(Math.max(instantFiltreDebut ?? 0, 0), horizon);
  const bornFin = Math.max(Math.min(instantFiltreFin ?? horizon, horizon), bornDebut + 1);
  const periodeFiltree = bornDebut > 0 || bornFin < horizon;
  const joursAffiches = jours.filter((j) => j >= bornDebut && j < bornFin);
  const largeurPisteAffichee = (bornFin - bornDebut) * pxParJour;
  // Décale toute position absolue (en instants) vers l'origine de la fenêtre visible — la piste
  // (déjà `overflow-hidden`) tronque le reste, aucune barre/marqueur hors fenêtre ne dépasse.
  const decale = (instant: number) => (instant - bornDebut) * pxParJour;

  // En mode heures, l'axe se lit sur deux lignes (comme un planificateur classique) — une ligne
  // "jour" qui regroupe ses heures plutôt que de répéter la date entière sur chaque colonne, et
  // une ligne "heure" en dessous. En mode jours, une colonne == un jour : une seule ligne suffit,
  // ce regroupement n'est simplement pas rendu (voir plus bas).
  const joursGroupesBruts: { debut: number; fin: number; cle: string }[] = [];
  for (const j of joursAffiches) {
    const cleJour = dateDepuisAncrage(j, ancrage, unite).toDateString();
    const dernier = joursGroupesBruts[joursGroupesBruts.length - 1];
    if (dernier && dernier.cle === cleJour) {
      dernier.fin = j + 1;
    } else {
      joursGroupesBruts.push({ debut: j, fin: j + 1, cle: cleJour });
    }
  }
  const joursGroupes = joursGroupesBruts.map((g) => ({
    debut: g.debut,
    fin: g.fin,
    label: formatJour(dateDepuisAncrage(g.debut, ancrage, unite)),
  }));

  // Espace les étiquettes d'heure pour qu'elles ne se chevauchent jamais au zoom courant (un pas
  // de 1h à 48px/h reste lisible, un pas de 1h à 8px/h ne le serait plus) — mêmes paliers qu'un
  // planificateur classique (1/2/3/4/6/8/12/24h).
  const PAS_HEURE_CANDIDATS = [1, 2, 3, 4, 6, 8, 12, 24];
  const LARGEUR_MIN_ETIQUETTE_HEURE = 40;
  const pasHeureEtiquette =
    PAS_HEURE_CANDIDATS.find((p) => p * pxParJour >= LARGEUR_MIN_ETIQUETTE_HEURE) ?? 24;

  // Position (généralement fractionnaire) de l'instant présent sur l'axe du planning — masquée
  // si "maintenant" tombe hors de la plage affichée (planning entièrement passé, ou futur
  // au-delà de son propre horizon).
  const msParUnite = unite === "heures" ? 3_600_000 : 86_400_000;
  const joursDepuisAncrage = (Date.now() - ancrage.getTime()) / msParUnite;
  // Indépendante de la période filtrée (contrairement à `afficherMaintenant` ci-dessous, qui ne
  // pilote que le rendu du trait dans la fenêtre courante) — sert à activer/désactiver le bouton
  // "Aujourd'hui" et à savoir s'il y a quelque chose vers quoi défiler.
  const maintenantDansPortee = joursDepuisAncrage >= 0 && joursDepuisAncrage <= horizon;
  const afficherMaintenant = joursDepuisAncrage >= bornDebut && joursDepuisAncrage <= bornFin;

  // Réinitialise le filtre de période (sinon "aujourd'hui" pourrait rester hors de la fenêtre
  // filtrée) puis centre le scroll horizontal sur l'instant présent.
  function allerAJourdhui() {
    setFiltreDebut("");
    setFiltreFin("");
    requestAnimationFrame(() => {
      const conteneur = conteneurScrollRef.current;
      if (!conteneur || !maintenantDansPortee) return;
      const cible =
        joursDepuisAncrage * pxParJour - conteneur.clientWidth / 2 + LARGEUR_COL_RESSOURCE + 12;
      conteneur.scrollTo({ left: Math.max(0, cible), behavior: "smooth" });
    });
  }

  const rechercheNormalisee = recherche.trim().toLowerCase();
  function correspondRecherche(op: { tache: string }): boolean {
    if (!rechercheNormalisee) return true;
    const produit = produitParTache.get(op.tache);
    const commandesTache = commandesParTache.get(op.tache) ?? [];
    const hay = [op.tache, produit ?? "", ...commandesTache.map((c) => c.commande_id)]
      .join(" ")
      .toLowerCase();
    return hay.includes(rechercheNormalisee);
  }

  const operationDetail = operationDetailCle
    ? (operations.find((op) => cle(op) === operationDetailCle) ?? null)
    : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
            placeholder="Rechercher (tâche, produit, commande)"
            className="h-8 w-64 pl-7 text-xs"
            aria-label="Rechercher une opération"
          />
        </div>
        <Button
          size="sm"
          variant="outline"
          className="h-8"
          onClick={allerAJourdhui}
          disabled={!maintenantDansPortee}
        >
          Aujourd'hui
        </Button>
        <div className="ml-auto flex items-center gap-1">
          <Button
            size="icon"
            variant="outline"
            className="h-7 w-7"
            onClick={() => zoomer(-1)}
            disabled={pxParJour <= echelle.min}
            aria-label="Réduire le zoom"
          >
            <ZoomOut className="h-3.5 w-3.5" />
          </Button>
          <span className="w-12 text-center font-mono text-xs">
            {pxParJour}px/{unite === "heures" ? "h" : "j"}
          </span>
          <Button
            size="icon"
            variant="outline"
            className="h-7 w-7"
            onClick={() => zoomer(1)}
            disabled={pxParJour >= echelle.max}
            aria-label="Augmenter le zoom"
          >
            <ZoomIn className="h-3.5 w-3.5" />
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={ajusterALaFenetre}
            title="Ajuster l'échelle pour que tout le planning tienne à l'écran"
          >
            Ajuster
          </Button>
        </div>
      </div>

      {peutEditer && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            Glisse une barre pour changer son instant de début — proposition revalidée avant tout
            enregistrement, jamais appliquée silencieusement.
          </p>
          {estModifie && (
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={reinitialiser}
                disabled={ajuster.isPending}
              >
                <RotateCcw className="mr-1.5 h-3.5 w-3.5" /> Réinitialiser
              </Button>
              <Button size="sm" onClick={enregistrer} disabled={ajuster.isPending}>
                <Save className="mr-1.5 h-3.5 w-3.5" />
                {ajuster.isPending ? "Validation..." : "Enregistrer l'ajustement"}
              </Button>
            </div>
          )}
        </div>
      )}

      {violations.length > 0 && (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
          <div className="flex items-center gap-2 font-medium">
            <AlertCircle className="h-4 w-4" /> Ajustement illégal — rien n'a été enregistré
          </div>
          <ul className="mt-1.5 list-disc space-y-1 pl-5">
            {violations.map((v, i) => (
              <li key={i}>{v.message}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted-foreground">Période affichée :</span>
        <Input
          type={unite === "heures" ? "datetime-local" : "date"}
          className="h-7 w-auto text-xs"
          value={filtreDebut}
          min={unite === "heures" ? formatEntreeDateHeure(ancrage) : formatEntreeDate(ancrage)}
          max={filtreFin || undefined}
          onChange={(e) => setFiltreDebut(e.target.value)}
          aria-label="Début de la période affichée"
        />
        <span className="text-muted-foreground">→</span>
        <Input
          type={unite === "heures" ? "datetime-local" : "date"}
          className="h-7 w-auto text-xs"
          value={filtreFin}
          min={filtreDebut || undefined}
          onChange={(e) => setFiltreFin(e.target.value)}
          aria-label="Fin de la période affichée"
        />
        {periodeFiltree && (
          <Button
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={() => {
              setFiltreDebut("");
              setFiltreFin("");
            }}
          >
            Réinitialiser
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-[10px] text-muted-foreground">
        {nonOuvres.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-sm bg-foreground/10" />
            {unite === "heures"
              ? `Heures non ouvrées (avant ${HEURE_OUVERTURE}h, après ${HEURE_FERMETURE}h, week-end)`
              : "Jours non ouvrés (samedi, dimanche)"}
          </div>
        )}
        {afficherMaintenant && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-0.5 bg-blue-500" />
            Aujourd'hui
          </div>
        )}
        {commandesParEcheance.size > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-0.5 border-l-2 border-dashed border-amber-500" />
            Échéance commande
          </div>
        )}
        {commandesParTache.size > 0 && (
          <div className="flex items-center gap-1.5">
            <Tag className="h-3 w-3" />
            Tâche associée à une commande
          </div>
        )}
        {commandesParTache.size > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-4 rounded-sm border border-dashed border-primary/60 bg-primary/25" />
            Projection : tâche répétée chaque jour ouvré jusqu'à la réalisation de la commande —
            visuel seulement, aucune capacité réservée
          </div>
        )}
      </div>

      {(commandes ?? []).length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted-foreground">Commandes :</span>
          {(commandes ?? []).map((c) => (
            <span
              key={c.commande_id}
              className="rounded-md border border-border/50 bg-muted/30 px-1.5 py-0.5 font-mono text-[10px]"
              title={`${c.taches.length} tâche${c.taches.length > 1 ? "s" : ""} : ${c.taches.join(", ")}`}
            >
              {c.commande_id}
            </span>
          ))}
        </div>
      )}

      <div className="overflow-x-auto" ref={conteneurScrollRef}>
        <div>
          {unite === "heures" ? (
            <div className="mb-1" style={{ paddingLeft: LARGEUR_COL_RESSOURCE + 12 }}>
              <div className="flex text-xs text-muted-foreground">
                {joursGroupes.map((g) => (
                  <div
                    key={g.debut}
                    className="shrink-0 truncate border-r border-border/40 px-1 text-center first:border-l"
                    style={{ width: (g.fin - g.debut) * pxParJour }}
                  >
                    {g.label}
                  </div>
                ))}
              </div>
              <div className="flex text-[10px] text-muted-foreground">
                {joursAffiches.map((j) => {
                  const dateJ = dateDepuisAncrage(j, ancrage, unite);
                  const etiquette =
                    dateJ.getHours() % pasHeureEtiquette === 0 ? formatHeure(dateJ) : "";
                  return (
                    <div
                      key={j}
                      className="shrink-0 truncate border-r border-border/20 text-center first:border-l"
                      style={{ width: pxParJour }}
                    >
                      {etiquette}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div
              className="mb-1 flex text-xs text-muted-foreground"
              style={{ paddingLeft: LARGEUR_COL_RESSOURCE + 12 }}
            >
              {joursAffiches.map((j) => (
                <div
                  key={j}
                  className="shrink-0 truncate border-r border-border/40 px-1 text-center first:border-l"
                  style={{ width: pxParJour }}
                >
                  {formatAxe(j)}
                </div>
              ))}
            </div>
          )}
          <div className="max-h-104 space-y-2.5 overflow-y-auto pr-1">
            {ressources.map((ressource) => {
              const operationsRessourceToutes = parRessource.get(ressource) ?? [];
              const taux = contraintes
                ? tauxUtilisationRessource(
                    ressource,
                    // Charge = heures travaillées, pas le temps écoulé (les pauses ne comptent pas).
                    operationsRessourceToutes.map((op) => ({
                      debut: op.debut,
                      fin: op.debut + op.duree,
                    })),
                    makespan,
                    contraintes,
                  )
                : null;
              // N'affiche que les opérations qui chevauchent la fenêtre visible — le reste
              // resterait de toute façon masqué par `overflow-hidden`, filtrer évite juste des
              // éléments DOM inutiles.
              const operationsRessource = operationsRessourceToutes.filter(
                (op) => op.fin > bornDebut && op.debut < bornFin,
              );
              return (
                <div key={ressource} className="flex items-center gap-3">
                  <div
                    className="shrink-0 truncate font-mono text-xs text-muted-foreground"
                    style={{ width: LARGEUR_COL_RESSOURCE }}
                    title={ressource}
                  >
                    {ressource}
                  </div>
                  <div
                    className="relative h-10 shrink-0 overflow-hidden rounded bg-muted/30"
                    style={{ width: largeurPisteAffichee }}
                  >
                    {joursAffiches.map((j) => (
                      <div
                        key={j}
                        className="absolute top-0 h-full w-px bg-border/40"
                        style={{ left: decale(j) }}
                      />
                    ))}
                    {nonOuvres
                      .filter((s) => s.fin > bornDebut && s.debut < bornFin)
                      .map((s, i) => (
                        <div
                          key={i}
                          className="absolute top-0 h-full bg-foreground/10"
                          style={{
                            left: decale(Math.max(s.debut, bornDebut)),
                            width:
                              (Math.min(s.fin, bornFin) - Math.max(s.debut, bornDebut)) * pxParJour,
                          }}
                          title="Non ouvré"
                        />
                      ))}
                    {afficherMaintenant && (
                      <div
                        className="absolute top-0 z-10 h-full w-0.5 bg-blue-500"
                        style={{ left: decale(joursDepuisAncrage) }}
                        title="Aujourd'hui"
                      />
                    )}
                    {[...commandesParEcheance.entries()]
                      .filter(
                        ([jourEcheance]) => jourEcheance >= bornDebut && jourEcheance <= bornFin,
                      )
                      .map(([jourEcheance, cmds]) => (
                        <div
                          key={jourEcheance}
                          className="absolute top-0 z-10 h-full w-0.5 border-l-2 border-dashed border-amber-500"
                          style={{ left: decale(jourEcheance) }}
                          title={`Échéance (${formatAxe(jourEcheance)}) : ${cmds
                            .map((c) => c.commande_id)
                            .join(", ")}`}
                        />
                      ))}
                    {operationsRessource.flatMap((op) => {
                      const commandesTache = commandesParTache.get(op.tache) ?? [];
                      if (commandesTache.length === 0) return [];
                      return segmentsRepetition(
                        op.fin,
                        finRepetition.get(op.tache) ?? op.fin,
                        ancrage,
                        unite,
                      )
                        .filter((s) => s.fin > bornDebut && s.debut < bornFin)
                        .map((s) => (
                          <div
                            key={`${cle(op)}|rep|${s.debut}`}
                            title={`Projection (rien n'est réservé dans le planning) : ${op.tache} répétée chaque jour ouvré jusqu'à la réalisation de ${commandesTache
                              .map((c) => c.commande_id)
                              .join(", ")}`}
                            className={`pointer-events-none absolute top-1.5 flex h-7 items-center gap-1 overflow-hidden rounded border border-dashed border-primary/60 bg-primary/25 px-1 text-[10px] text-primary transition-opacity ${
                              correspondRecherche(op) ? "" : "opacity-25"
                            }`}
                            style={{
                              left: decale(s.debut) + 1,
                              width: (s.fin - s.debut) * pxParJour - 2,
                            }}
                          >
                            <Tag className="h-2.5 w-2.5 shrink-0" />
                            <span className="truncate">Projection · {op.tache}</span>
                          </div>
                        ));
                    })}
                    {operationsRessource.map((op) => {
                      const cleOp = cle(op);
                      const enRetard = tachesEnRetardIds.has(op.tache);
                      const duree = op.duree;
                      const produit = produitParTache.get(op.tache);
                      const commandesTache = commandesParTache.get(op.tache) ?? [];
                      // La première commande est déjà en tête du libellé (voir plus bas) — ce
                      // suffixe ne signale que les suivantes, pour ne jamais la compter deux fois.
                      const libelleCommandesSupplementaires =
                        commandesTache.length > 1 ? ` +${commandesTache.length - 1}` : "";
                      // Une plage par jour ouvré traversé (19h-22h puis 8h-10h) : jamais de barre
                      // qui recouvre la nuit ou le week-end. Le libellé n'est écrit que sur la première.
                      const segmentsBarre = segmentsTravailles(
                        op.debut,
                        op.duree,
                        ancrage,
                        unite,
                      ).filter((seg) => seg.fin > bornDebut && seg.debut < bornFin);
                      return segmentsBarre.map((seg, indexSegment) => (
                        <div
                          key={`${cleOp}|${seg.debut}`}
                          title={`${op.tache} : ${formatAxe(op.debut)} → ${formatAxe(op.fin)}${
                            enRetard ? " (en retard)" : ""
                          }${
                            commandesTache.length > 0
                              ? ` — commande(s) : ${commandesTache.map((c) => c.commande_id).join(", ")}`
                              : ""
                          }`}
                          onPointerDown={(e) => onPointerDownBarre(e, cleOp, op.debut)}
                          onPointerMove={onPointerMoveBarre}
                          onPointerUp={(e) => onPointerUpBarre(e, cleOp)}
                          className={`absolute top-0 flex h-full items-center gap-1 overflow-hidden rounded px-1.5 text-xs font-medium text-primary-foreground transition-opacity ${
                            enRetard ? "bg-destructive" : "bg-gradient-to-r from-primary to-accent"
                          } ${peutEditer ? "cursor-grab touch-none active:cursor-grabbing" : "cursor-pointer touch-none"} ${
                            clesModifiees.has(cleOp) ? "ring-2 ring-yellow-400" : ""
                          } ${correspondRecherche(op) ? "" : "opacity-25"}`}
                          style={{
                            left: decale(seg.debut),
                            width: (seg.fin - seg.debut) * pxParJour,
                          }}
                        >
                          {indexSegment === 0 && commandesTache.length > 0 && (
                            <Tag
                              className="h-3 w-3 shrink-0"
                              aria-label="Associée à une commande"
                            />
                          )}
                          {indexSegment === 0 && (
                            <span className="truncate">
                              {commandesTache.length > 0
                                ? `${commandesTache[0].commande_id} · `
                                : ""}
                              {produit ? `${produit} · ` : ""}
                              {op.tache} ({duree}
                              {unite === "heures" ? "h" : "j"}){libelleCommandesSupplementaires}
                            </span>
                          )}
                        </div>
                      ));
                    })}
                  </div>
                  {taux !== null && (
                    <div className="flex w-24 shrink-0 items-center gap-1.5">
                      <div className="h-1.5 flex-1 rounded bg-muted/30">
                        <div
                          className="h-full rounded bg-gradient-to-r from-primary to-accent"
                          style={{ width: `${taux}%` }}
                        />
                      </div>
                      <span className="w-8 shrink-0 text-right text-[10px] text-muted-foreground">
                        {taux.toFixed(0)}%
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <Sheet
        open={operationDetail !== null}
        onOpenChange={(open) => !open && setOperationDetailCle(null)}
      >
        <SheetContent>
          {operationDetail && (
            <>
              <SheetHeader>
                <SheetTitle>{operationDetail.tache}</SheetTitle>
                <SheetDescription>Ressource : {operationDetail.ressource}</SheetDescription>
              </SheetHeader>
              <div className="mt-4 space-y-3 text-sm">
                {(() => {
                  const produitDetail = produitParTache.get(operationDetail.tache);
                  const commandesDetail = commandesParTache.get(operationDetail.tache) ?? [];
                  const dureeDetail = operationDetail.duree;
                  const enRetardDetail = tachesEnRetardIds.has(operationDetail.tache);
                  return (
                    <>
                      {produitDetail && (
                        <div>
                          <span className="text-xs text-muted-foreground">Produit</span>
                          <p>{produitDetail}</p>
                        </div>
                      )}
                      <div>
                        <span className="text-xs text-muted-foreground">Début → fin</span>
                        <p>
                          {formatAxe(operationDetail.debut)} → {formatAxe(operationDetail.fin)}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground">Durée</span>
                        <p>
                          {dureeDetail} {unite === "heures" ? "heure(s)" : "jour(s)"}
                        </p>
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground">Statut</span>
                        <p>{enRetardDetail ? "En retard" : "À temps"}</p>
                      </div>
                      {commandesDetail.length > 0 && (
                        <div>
                          <span className="text-xs text-muted-foreground">
                            Commande{commandesDetail.length > 1 ? "s" : ""}
                          </span>
                          <div className="mt-1 flex flex-wrap gap-1.5">
                            {commandesDetail.map((c) => (
                              <span
                                key={c.commande_id}
                                className="rounded-md border border-border/50 bg-muted/30 px-1.5 py-0.5 font-mono text-xs"
                              >
                                {c.commande_id}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      {instanceId && (
                        <div className="border-t border-border/50 pt-3">
                          <span className="text-xs text-muted-foreground">
                            Déclarer un retard réel
                          </span>
                          <p className="mt-0.5 text-xs text-muted-foreground">
                            PRISME ne détecte rien tout seul — corrigez la durée réellement
                            constatée sur {operationDetail.ressource}, puis relancez l'exécution
                            pour un planning qui en tient compte.
                          </p>
                          <div className="mt-2 flex items-center gap-2">
                            <Input
                              type="number"
                              min={1}
                              placeholder={`nouvelle durée (${unite === "heures" ? "h" : "j"})`}
                              value={dureeCorrigee}
                              onChange={(e) => setDureeCorrigee(e.target.value)}
                              className="w-40"
                            />
                            <Button
                              size="sm"
                              variant="outline"
                              disabled={
                                !dureeCorrigee ||
                                Number(dureeCorrigee) < 1 ||
                                declarerRetard.isPending
                              }
                              onClick={() =>
                                declarerRetard.mutate({
                                  instanceId,
                                  tacheId: operationDetail.tache,
                                  requete: {
                                    ressource: operationDetail.ressource,
                                    nouvelle_duree: Number(dureeCorrigee),
                                  },
                                })
                              }
                            >
                              {declarerRetard.isPending ? "Correction..." : "Corriger la durée"}
                            </Button>
                          </div>
                          {declarerRetard.isError && (
                            <p className="mt-1.5 text-xs text-destructive">
                              {(declarerRetard.error as PrismeAPIError).message}
                            </p>
                          )}
                          {declarerRetard.isSuccess && !executerApresRetard.isSuccess && (
                            <div className="mt-1.5 flex items-center gap-2 text-xs">
                              <span className="text-primary">Durée corrigée.</span>
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={executerApresRetard.isPending}
                                onClick={() =>
                                  executerApresRetard.mutate(
                                    { instanceId },
                                    {
                                      onSuccess: () =>
                                        queryClient.invalidateQueries({
                                          queryKey: prismeKeys.executions(),
                                        }),
                                    },
                                  )
                                }
                              >
                                {executerApresRetard.isPending
                                  ? "Exécution..."
                                  : "Relancer l'exécution"}
                              </Button>
                            </div>
                          )}
                          {executerApresRetard.isSuccess && (
                            <p className="mt-1.5 text-xs text-muted-foreground">
                              {executerApresRetard.data.reussi
                                ? "Nouvelle exécution réussie — ferme puis rouvre ce planning pour la voir."
                                : "Exécution en échec."}
                            </p>
                          )}
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

import { useRef, useState } from "react";
import { Link } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import {
  Plus,
  Trash2,
  Upload,
  FileJson,
  FileSpreadsheet,
  Files,
  Braces,
  CheckCircle2,
  AlertCircle,
  FolderOpen,
  CalendarOff,
  Scale,
  ChevronDown,
  ChevronRight,
  X,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  prismeKeys,
  useIngererInstance,
  useModifierInstance,
  useCreerScenario,
  useImporterViaAdaptateur,
  useImporterFichierTableur,
  useImporterFichiersCsv,
  useImporterJsonAvecCompetences,
  useImporterCsvLocal,
  useDeclencherExecution,
  useEvaluerSolveurSupervision,
  PrismeAPIError,
  type Contrainte,
  type InstanceDetail,
  type InstanceTRCO,
  type Objectif,
  type Ressource,
  type Tache,
  type TypeContrainte,
  type TypeObjectif,
} from "@/integrations/prisme";
import { useAuth } from "@/integrations/prisme/auth";
import { VerdictSolveur } from "@/components/supervision/verdict-solveur";
import {
  aujourdhui,
  dateDepuisAncrage,
  formatEntreeDate,
  formatEntreeDateHeure,
  jourDepuisAncrage,
  parseEntreeDate,
  parseEntreeDateHeure,
  type UniteTemps,
} from "@/lib/dates-relatives";
import {
  convertirDateSaisie,
  convertirDatesIndisponibles,
  convertirDureeSaisie,
  convertirMotifHebdomadaire,
  hrefGabaritCsv,
  hrefGabaritJson,
  libelleUnite,
  nomGabaritCsv,
  nomGabaritJson,
} from "@/lib/unite-ingestion";

// Adaptateurs ERP réellement branchés côté backend (POST /adapters/{id}/ingerer).
// Ajouter un adaptateur = ajouter une entrée ici, aucun autre changement de composant.
const SOURCES_IMPORT = [{ id: "greensig", label: "GreenSIG" }] as const;

// Indexé par Date.getDay() (0 = dimanche) — pour le sélecteur de motif hebdomadaire récurrent de
// disponibilite_ressource, converti en position dans le cycle DSL à la soumission (voir
// construireInstance).
const NOMS_JOURS_SEMAINE_COURTS = ["Dim", "Lun", "Mar", "Mer", "Jeu", "Ven", "Sam"];

let compteurId = 0;
function idLocal() {
  compteurId += 1;
  return `local-${compteurId}`;
}

interface TacheLigne extends Tache {
  clef: string;
}
interface RessourceLigne extends Ressource {
  clef: string;
  competencesTexte: string;
  // Texte brut de l'input — vide = ressource disponible en continu.
  heuresParJourTexte: string;
}
interface ContrainteLigne {
  clef: string;
  type: TypeContrainte;
  avant: string;
  apres: string;
  tache: string;
  ressource: string;
  duree: string;
  // Date calendaire "YYYY-MM-DD" (<input type="date">), pas le jour relatif brut — convertie à
  // la soumission via jourDepuisAncrage(_, aujourdhui()) (voir construireInstance ci-dessous et
  // src/lib/dates-relatives.ts). Le DSL ne voit jamais que l'entier de jours qui en ressort.
  echeance: string;
  competence: string;
  // disponibilite_ressource : dates calendaires individuelles ("YYYY-MM-DD") et jours de semaine
  // sélectionnés (0-6, convention JS Date.getDay() — pas la position DSL dans le cycle de 7
  // jours) — convertis en jours/positions relatifs à la soumission, ancrés sur "aujourd'hui".
  joursIndisponibles: string[];
  joursSemaineIndisponibles: number[];
}

export interface ObjectifLigne {
  clef: string;
  type: TypeObjectif;
  poids: string;
  makespanCible: string;
  methode: "ecart_max" | "variance" | "gini";
  ressourcesCibles: string;
  fonctionPenalite: "lineaire" | "quadratique" | "exponentielle";
  seuilGrace: string;
  ressourcesPrioritaires: string;
}

export const LABELS_OBJECTIF: Record<TypeObjectif, string> = {
  minimiser_makespan: "Minimiser le makespan",
  equilibrer_charge: "Équilibrer la charge",
  minimiser_retards: "Minimiser les retards",
  maximiser_utilisation: "Maximiser l'utilisation",
  minimiser_changements: "Minimiser les changements",
};

// Types d'objectif portant des réglages au-delà de type/poids (méthode, seuil, ressources
// ciblées...) — repliés par défaut sous "Options avancées" : un utilisateur ordinaire n'a besoin
// que d'indiquer le poids, les valeurs par défaut de `nouvelObjectif()` (linéaire, écart max...)
// couvrent le cas courant. `minimiser_changements` n'a aucun réglage propre, jamais de bouton.
const TYPES_AVEC_OPTIONS_AVANCEES = new Set<TypeObjectif>([
  "minimiser_makespan",
  "equilibrer_charge",
  "minimiser_retards",
  "maximiser_utilisation",
]);

function nouvelleTache(): TacheLigne {
  return { clef: idLocal(), id: "", nom: "" };
}
function nouvelleRessource(): RessourceLigne {
  return {
    clef: idLocal(),
    id: "",
    nom: "",
    competences: [],
    competencesTexte: "",
    heuresParJourTexte: "",
  };
}
function nouvelleContrainte(): ContrainteLigne {
  return {
    clef: idLocal(),
    type: "compatibilite_ressource_tache",
    avant: "",
    apres: "",
    tache: "",
    ressource: "",
    duree: "",
    echeance: "",
    competence: "",
    joursIndisponibles: [],
    joursSemaineIndisponibles: [],
  };
}
export function nouvelObjectif(): ObjectifLigne {
  return {
    clef: idLocal(),
    type: "minimiser_makespan",
    poids: "1",
    makespanCible: "",
    methode: "ecart_max",
    ressourcesCibles: "",
    fonctionPenalite: "lineaire",
    seuilGrace: "",
    ressourcesPrioritaires: "",
  };
}

export function construireObjectifs(objectifs: ObjectifLigne[]): Objectif[] {
  return objectifs.map((o): Objectif => {
    const poids = o.poids.trim() ? Number(o.poids) : undefined;
    switch (o.type) {
      case "minimiser_makespan":
        return {
          type: "minimiser_makespan",
          ...(poids !== undefined ? { poids } : {}),
          ...(o.makespanCible.trim() ? { makespan_cible: Number(o.makespanCible) } : {}),
        };
      case "equilibrer_charge":
        return {
          type: "equilibrer_charge",
          ...(poids !== undefined ? { poids } : {}),
          methode: o.methode,
          ...(o.ressourcesCibles.trim()
            ? {
                ressources_cibles: o.ressourcesCibles
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              }
            : {}),
        };
      case "minimiser_retards":
        return {
          type: "minimiser_retards",
          ...(poids !== undefined ? { poids } : {}),
          fonction_penalite: o.fonctionPenalite,
          ...(o.seuilGrace.trim() ? { seuil_grace: Number(o.seuilGrace) } : {}),
        };
      case "maximiser_utilisation":
        return {
          type: "maximiser_utilisation",
          ...(poids !== undefined ? { poids } : {}),
          ...(o.ressourcesPrioritaires.trim()
            ? {
                ressources_prioritaires: o.ressourcesPrioritaires
                  .split(",")
                  .map((s) => s.trim())
                  .filter(Boolean),
              }
            : {}),
        };
      case "minimiser_changements":
        return {
          type: "minimiser_changements",
          ...(poids !== undefined ? { poids } : {}),
        };
    }
  });
}

// Longueur du cycle du motif hebdomadaire récurrent — 7 en mode jours, 168 en mode heures (voir
// dsl/schema/instance.py::InstanceTRCO._disponibilite_dans_le_cycle, même constante côté serveur).
function longueurCycle(unite: UniteTemps): number {
  return unite === "heures" ? 168 : 7;
}

// Réexprime une contrainte déjà saisie dans l'autre unité quand l'utilisateur change d'unité en
// cours de route — sans ça, "3" saisi en jours devenait silencieusement "3 heures", et les champs
// date/datetime-local perdaient leur valeur au changement de type d'input. Règles de conversion
// détaillées (arrondis, dépliage jour ↔ 24 créneaux) dans src/lib/unite-ingestion.ts.
function convertirLigneContrainte(
  c: ContrainteLigne,
  de: UniteTemps,
  vers: UniteTemps,
): ContrainteLigne {
  return {
    ...c,
    duree: convertirDureeSaisie(c.duree, de, vers),
    echeance: convertirDateSaisie(c.echeance, de, vers),
    joursIndisponibles: convertirDatesIndisponibles(c.joursIndisponibles, de, vers),
    joursSemaineIndisponibles: convertirMotifHebdomadaire(c.joursSemaineIndisponibles, de, vers),
  };
}

function construireInstance(
  taches: TacheLigne[],
  ressources: RessourceLigne[],
  contraintes: ContrainteLigne[],
  objectifs: ObjectifLigne[],
  // Contraintes d'un type que ce formulaire ne sait pas éditer, à réinjecter
  // telles quelles (voir contraintesNonEditables) — jamais perdues au
  // réenregistrement d'une instance qui en avait.
  contraintesNonEditables: Contrainte[] = [],
  uniteTemps: UniteTemps = "jours",
  joursFermes: number[] = [0, 6],
): InstanceTRCO {
  const ancrage = aujourdhui();
  // Point de référence unique pour le motif hebdomadaire, dans le même référentiel que
  // `longueurCycle` : position 0 du cycle en mode heures = (jour de semaine × 24 + heure) de
  // `ancrage` — pas seulement son jour de semaine, contrairement au mode jours.
  const referenceCycle =
    uniteTemps === "heures" ? ancrage.getDay() * 24 + ancrage.getHours() : ancrage.getDay();
  return {
    taches: taches.map(({ id, nom, priorite }) => ({
      id,
      ...(nom ? { nom } : {}),
      ...(priorite ? { priorite } : {}),
    })),
    ressources: ressources.map(({ id, nom, competencesTexte, heuresParJourTexte }) => ({
      id,
      ...(nom ? { nom } : {}),
      competences: competencesTexte
        .split(",")
        .map((c) => c.trim())
        .filter(Boolean),
      ...(heuresParJourTexte.trim() ? { heures_par_jour: Number(heuresParJourTexte) } : {}),
    })),
    contraintes: contraintes
      .map((c): Contrainte => {
        switch (c.type) {
          case "precedence":
            return { type: "precedence", avant: c.avant, apres: c.apres };
          case "compatibilite_ressource_tache":
            return {
              type: "compatibilite_ressource_tache",
              tache: c.tache,
              ressource: c.ressource,
              duree: Number(c.duree),
            };
          case "echeance": {
            const date =
              uniteTemps === "heures"
                ? parseEntreeDateHeure(c.echeance)
                : parseEntreeDate(c.echeance);
            return {
              type: "echeance",
              tache: c.tache,
              echeance: date ? jourDepuisAncrage(date, ancrage, uniteTemps) : 0,
            };
          }
          case "competence_requise":
            return { type: "competence_requise", tache: c.tache, competence: c.competence };
          case "changement_serie":
            return {
              type: "changement_serie",
              ressource: c.ressource,
              tache_avant: c.avant,
              tache_apres: c.apres,
              duree_setup: Number(c.duree),
            };
          case "disponibilite_ressource": {
            const joursIndisponibles = c.joursIndisponibles
              .map((v) => (uniteTemps === "heures" ? parseEntreeDateHeure(v) : parseEntreeDate(v)))
              .filter((d): d is Date => d !== null)
              .map((d) => jourDepuisAncrage(d, ancrage, uniteTemps));
            // Position dans le cycle DSL (0 = position de `referenceCycle`), pas la valeur brute
            // choisie dans l'UI (jour de semaine JS, ou index plat jour×24+heure — voir
            // contrainteVersLigne pour l'inverse).
            const cycle = longueurCycle(uniteTemps);
            const joursSemaine = c.joursSemaineIndisponibles.map(
              (valeurBrute) => (valeurBrute - referenceCycle + cycle) % cycle,
            );
            return {
              type: "disponibilite_ressource",
              ressource: c.ressource,
              jours_indisponibles: joursIndisponibles,
              ...(joursSemaine.length > 0 ? { jours_semaine_indisponibles: joursSemaine } : {}),
            };
          }
        }
      })
      // Une disponibilité sans aucun jour ni motif n'indique aucune indisponibilité — sans effet,
      // et refusée par le DSL (« au moins un jour »). On l'écarte plutôt que de bloquer tout
      // l'enregistrement sur une ligne laissée vide.
      .filter(
        (c) =>
          c.type !== "disponibilite_ressource" ||
          c.jours_indisponibles.length > 0 ||
          (c.jours_semaine_indisponibles?.length ?? 0) > 0,
      )
      .concat(contraintesNonEditables),
    objectifs: construireObjectifs(objectifs),
    unite_temps: uniteTemps,
    jours_fermes: joursFermes,
  };
}

export function ErreursAPI({ erreur }: { erreur: PrismeAPIError }) {
  const champs = erreur.champs;
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
      <div className="flex items-center gap-2 font-medium">
        <AlertCircle className="h-4 w-4" /> Échec de la validation
      </div>
      {champs.length > 0 ? (
        <ul className="mt-2 list-disc space-y-1 pl-5">
          {champs.map((c, i) => (
            <li key={i}>
              <span className="font-mono text-xs">{c.loc.join(".")}</span> — {c.msg}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1">{erreur.message}</p>
      )}
    </div>
  );
}

export function IngestionDialog({
  open,
  onOpenChange,
  instanceAEditer,
  scenarioDeBase,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  // Instance existante à éditer en place (bouton "Modifier", page
  // Instances) — la soumission remplace son contenu T-R-C-O directement
  // (même instance_id, historique d'exécutions intact), rien n'est dupliqué.
  // Absent = formulaire vierge pour une nouvelle instance, comportement
  // inchangé.
  instanceAEditer?: InstanceDetail;
  // Instance servant de point de départ pour créer un scénario comparatif
  // (bouton "Créer un scénario", onglet Scénarios) — préremplit le
  // formulaire exactement comme instanceAEditer, mais la soumission crée une
  // NOUVELLE instance rattachée au même groupe, jamais une modification en
  // place. Mutuellement exclusif avec instanceAEditer en pratique.
  scenarioDeBase?: InstanceDetail;
}) {
  const queryClient = useQueryClient();
  const ingerer = useIngererInstance();
  const modifier = useModifierInstance();
  const creerScenario = useCreerScenario();
  const importer = useImporterViaAdaptateur();
  const importerFichier = useImporterFichierTableur();
  const importerCsv = useImporterFichiersCsv();
  const importerJson = useImporterJsonAvecCompetences();
  const importerCsvLocal = useImporterCsvLocal();
  const executer = useDeclencherExecution();
  // Verdict « le solveur de la base peut-il répondre à ce scénario ? » — proposé seulement quand
  // l'exécution automatique échoue faute de solveur (voir bloc executer.isError plus bas). Coûte
  // un vrai appel LLM (Benchmarker rejoué), donc jamais déclenché sans un clic explicite.
  const evaluer = useEvaluerSolveurSupervision();
  const { utilisateur } = useAuth();
  const estAdmin = utilisateur?.role === "admin";

  // Même préremplissage pour "Modifier" et "Créer un scénario" — seul ce qui
  // se passe à la soumission diffère (voir soumettreTRCO).
  const instanceDepart = instanceAEditer ?? scenarioDeBase;

  const [clientId, setClientId] = useState(
    instanceDepart?.client_id ?? utilisateur?.client_id ?? "",
  );
  // "Unité de temps" (jours/heures) — un seul état partagé par tous les onglets qui produisent
  // une instance (Saisie T-R-C-O, Fichiers CSV, CSV Local, Fichier JSON — chacun transmet
  // unite_temps au backend) : changer d'onglet ne remet jamais l'unité à zéro. Toujours modifié
  // via changerUniteTemps ci-dessous, qui convertit les valeurs déjà saisies.
  const [uniteTemps, setUniteTemps] = useState<UniteTemps>(
    // Nouvelle instance : heures par défaut. Instance existante (modification, scénario) : on
    // garde son unité — une instance sans unite_temps est en jours (défaut historique du DSL).
    instanceDepart ? (instanceDepart.unite_temps === "heures" ? "heures" : "jours") : "heures",
  );
  // Jours fermés par défaut (correction post-solveur, dsl/schema/instance.py::jours_fermes) —
  // défaut serveur si l'instance de départ ne le précise pas (samedi+dimanche, 0=dimanche..6=samedi).
  const [joursFermes, setJoursFermes] = useState<number[]>(instanceDepart?.jours_fermes ?? [0, 6]);
  const [taches, setTaches] = useState<TacheLigne[]>(
    instanceDepart ? instanceDepart.taches.map(tacheVersLigne) : [nouvelleTache()],
  );
  const [ressources, setRessources] = useState<RessourceLigne[]>(
    instanceDepart ? instanceDepart.ressources.map(ressourceVersLigne) : [nouvelleRessource()],
  );
  const [contraintes, setContraintes] = useState<ContrainteLigne[]>(
    instanceDepart
      ? instanceDepart.contraintes
          .filter(estContrainteEditable)
          .map((c) => contrainteVersLigne(c, uniteTemps))
      : [],
  );
  // Contraintes présentes sur l'instance de départ mais que ce formulaire ne
  // sait pas éditer — conservées telles quelles et réinjectées à la
  // soumission, jamais perdues silencieusement.
  const [contraintesNonEditables] = useState<Contrainte[]>(
    instanceDepart ? instanceDepart.contraintes.filter((c) => !estContrainteEditable(c)) : [],
  );
  const [objectifs, setObjectifs] = useState<ObjectifLigne[]>(
    instanceDepart ? instanceDepart.objectifs.map(objectifVersLigne) : [nouvelObjectif()],
  );
  // Changer d'unité convertit les valeurs déjà saisies dans le formulaire T-R-C-O (durées,
  // échéances, indisponibilités) plutôt que de les réinterpréter telles quelles. Pour les onglets
  // fichier (CSV, JSON), rien n'est saisi ici : l'unité choisie dit seulement comment lire les
  // entiers du fichier, et quel gabarit télécharger.
  function changerUniteTemps(nouvelle: UniteTemps) {
    if (nouvelle === uniteTemps) return;
    const precedente = uniteTemps;
    setContraintes((arr) => arr.map((c) => convertirLigneContrainte(c, precedente, nouvelle)));
    setObjectifs((arr) =>
      arr.map((o) => ({
        ...o,
        seuilGrace: convertirDureeSaisie(o.seuilGrace, precedente, nouvelle),
      })),
    );
    setUniteTemps(nouvelle);
  }
  const [source, setSource] = useState<string>(SOURCES_IMPORT[0].id);
  const [fichier, setFichier] = useState<File | null>(null);
  const inputFichierRef = useRef<HTMLInputElement>(null);
  const [fichierJson, setFichierJson] = useState<File | null>(null);
  const inputJsonRef = useRef<HTMLInputElement>(null);
  const [erreurParseJson, setErreurParseJson] = useState<string | null>(null);
  const [fichierTachesCsv, setFichierTachesCsv] = useState<File | null>(null);
  const [fichierRessourcesCsv, setFichierRessourcesCsv] = useState<File | null>(null);
  const [fichierContraintesCsv, setFichierContraintesCsv] = useState<File | null>(null);
  const [fichierCommandesCsv, setFichierCommandesCsv] = useState<File | null>(null);
  // Description métier automatique (IA) sur l'atelier obtenu — coché par défaut (best-effort côté
  // serveur, voir api/routes/adapters.py::_description_metier_optionnelle) ; désactivable si
  // l'utilisateur préfère un import rapide sans appel IA.
  const [genererDescriptionCsv, setGenererDescriptionCsv] = useState(true);
  const inputTachesCsvRef = useRef<HTMLInputElement>(null);
  const inputRessourcesCsvRef = useRef<HTMLInputElement>(null);
  const inputContraintesCsvRef = useRef<HTMLInputElement>(null);
  const inputCommandesCsvRef = useRef<HTMLInputElement>(null);
  const [cheminDossierCsvLocal, setCheminDossierCsvLocal] = useState("");
  const [succes, setSucces] = useState<{
    instance_id: string;
    structure_contraintes: string;
  } | null>(null);

  function reinitialiser() {
    setClientId(utilisateur?.client_id ?? "");
    setUniteTemps("heures");
    setTaches([nouvelleTache()]);
    setRessources([nouvelleRessource()]);
    setContraintes([]);
    setObjectifs([nouvelObjectif()]);
    setFichier(null);
    if (inputFichierRef.current) inputFichierRef.current.value = "";
    setFichierJson(null);
    if (inputJsonRef.current) inputJsonRef.current.value = "";
    setErreurParseJson(null);
    setFichierTachesCsv(null);
    setFichierRessourcesCsv(null);
    setFichierContraintesCsv(null);
    setFichierCommandesCsv(null);
    if (inputTachesCsvRef.current) inputTachesCsvRef.current.value = "";
    if (inputRessourcesCsvRef.current) inputRessourcesCsvRef.current.value = "";
    if (inputContraintesCsvRef.current) inputContraintesCsvRef.current.value = "";
    if (inputCommandesCsvRef.current) inputCommandesCsvRef.current.value = "";
    setCheminDossierCsvLocal("");
    setSucces(null);
    ingerer.reset();
    modifier.reset();
    creerScenario.reset();
    importer.reset();
    importerFichier.reset();
    importerCsv.reset();
    importerJson.reset();
    importerCsvLocal.reset();
    executer.reset();
    evaluer.reset();
  }

  function fermer(open: boolean) {
    if (!open) reinitialiser();
    onOpenChange(open);
  }

  // Réexécute automatiquement dès qu'une instance est ingérée, quel que soit
  // le canal (T-R-C-O, ERP, fichier, CSV local...) — le principe fondateur
  // "generate once" reste respecté : /execution échoue proprement (409) si
  // aucun solveur validé n'existe encore pour cette structure, sans jamais
  // en générer un à la volée.
  function onIngestionReussie(data: { instance_id: string; structure_contraintes: string }) {
    setSucces(data);
    queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
    queryClient.invalidateQueries({ queryKey: prismeKeys.instance(data.instance_id) });
    if (scenarioDeBase) {
      queryClient.invalidateQueries({
        queryKey: prismeKeys.comparaisonScenarios(scenarioDeBase.instance_id),
      });
    }
    executer.mutate(
      { instanceId: data.instance_id },
      { onSuccess: () => queryClient.invalidateQueries({ queryKey: prismeKeys.executions() }) },
    );
  }

  function soumettreTRCO() {
    const instance = construireInstance(
      taches,
      ressources,
      contraintes,
      objectifs,
      contraintesNonEditables,
      uniteTemps,
      joursFermes,
    );
    if (scenarioDeBase) {
      creerScenario.mutate(
        { instanceId: scenarioDeBase.instance_id, instance },
        { onSuccess: onIngestionReussie },
      );
      return;
    }
    if (instanceAEditer) {
      modifier.mutate(
        { instanceId: instanceAEditer.instance_id, instance },
        { onSuccess: onIngestionReussie },
      );
      return;
    }
    ingerer.mutate({ clientId, instance }, { onSuccess: onIngestionReussie });
  }

  function soumettreImport() {
    importer.mutate({ nomAdaptateur: source }, { onSuccess: onIngestionReussie });
  }

  function soumettreFichier() {
    if (!fichier) return;
    importerFichier.mutate({ clientId, fichier }, { onSuccess: onIngestionReussie });
  }

  function soumettreCsv() {
    if (!fichierTachesCsv || !fichierRessourcesCsv || !fichierContraintesCsv) return;
    importerCsv.mutate(
      {
        clientId,
        fichiers: {
          taches: fichierTachesCsv,
          ressources: fichierRessourcesCsv,
          contraintes: fichierContraintesCsv,
          commandes: fichierCommandesCsv ?? undefined,
        },
        uniteTemps,
        genererDescription: genererDescriptionCsv,
      },
      { onSuccess: onIngestionReussie },
    );
  }

  async function soumettreJson() {
    if (!fichierJson) return;
    setErreurParseJson(null);
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(await fichierJson.text()) as Record<string, unknown>;
    } catch {
      setErreurParseJson("Le fichier n'est pas un JSON valide.");
      return;
    }
    importerJson.mutate({ clientId, payload, uniteTemps }, { onSuccess: onIngestionReussie });
  }

  function soumettreCsvLocal() {
    if (!cheminDossierCsvLocal.trim()) return;
    importerCsvLocal.mutate(
      { clientId, cheminDossier: cheminDossierCsvLocal, uniteTemps },
      { onSuccess: onIngestionReussie },
    );
  }

  const erreur = (ingerer.error ??
    modifier.error ??
    creerScenario.error ??
    importer.error ??
    importerFichier.error ??
    importerCsv.error ??
    importerJson.error ??
    importerCsvLocal.error) as PrismeAPIError | null;
  const enCours =
    ingerer.isPending ||
    modifier.isPending ||
    creerScenario.isPending ||
    importer.isPending ||
    importerFichier.isPending ||
    importerCsv.isPending ||
    importerJson.isPending ||
    importerCsvLocal.isPending;

  return (
    <Dialog open={open} onOpenChange={fermer}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>
            {scenarioDeBase
              ? "Créer un scénario"
              : instanceAEditer
                ? "Modifier l'instance"
                : "Nouvelle instance"}
          </DialogTitle>
          <DialogDescription>
            {scenarioDeBase ? (
              <>
                Formulaire prérempli à partir de{" "}
                <span className="font-mono text-xs">{scenarioDeBase.instance_id}</span>. La
                soumission crée une <strong>nouvelle</strong> instance, rattachée au même groupe de
                scénarios comparatifs — l'originale n'est jamais modifiée.
              </>
            ) : instanceAEditer ? (
              <>
                Formulaire prérempli à partir de{" "}
                <span className="font-mono text-xs">{instanceAEditer.instance_id}</span>. Les
                modifications sont appliquées directement à cette instance — son historique
                d'exécutions reste attaché, rien n'est dupliqué.
              </>
            ) : (
              "Ingérez une instance T-R-C-O directement, importez-la depuis un ERP connecté, ou depuis " +
              "un fichier Excel, des fichiers CSV, ou un fichier JSON rempli."
            )}
          </DialogDescription>
        </DialogHeader>

        {succes ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-primary/40 bg-primary/10 p-4 text-sm">
              <div className="flex items-center gap-2 font-medium text-primary">
                <CheckCircle2 className="h-4 w-4" />{" "}
                {instanceAEditer ? "Instance modifiée" : "Instance ingérée"}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">instance_id :</span>
                <Badge variant="secondary" className="font-mono">
                  {succes.instance_id}
                </Badge>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">structure_contraintes :</span>
                <Badge variant="outline" className="font-mono">
                  {succes.structure_contraintes}
                </Badge>
              </div>
            </div>

            {executer.isPending && (
              <p className="text-sm text-muted-foreground">Exécution automatique en cours...</p>
            )}
            {executer.isSuccess && (
              <div
                className={`rounded-lg border p-3 text-sm ${
                  executer.data.reussi
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-destructive/40 bg-destructive/10 text-destructive"
                }`}
              >
                <div className="flex items-center gap-2 font-medium">
                  {executer.data.reussi ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <AlertCircle className="h-4 w-4" />
                  )}
                  {executer.data.reussi ? "Planning généré automatiquement" : "Exécution en échec"}
                </div>
                {!executer.data.reussi && executer.data.erreur && (
                  <p className="mt-1 text-muted-foreground">{executer.data.erreur}</p>
                )}
              </div>
            )}
            {executer.isError && (
              <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
                <div className="flex items-center gap-2 font-medium text-amber-600 dark:text-amber-400">
                  <AlertCircle className="h-4 w-4" /> Instance ingérée, mais pas encore exécutée
                </div>
                <p className="mt-1 text-muted-foreground">
                  {(executer.error as PrismeAPIError).message}
                </p>
                {succes && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {scenarioDeBase && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={evaluer.isPending}
                        onClick={() => evaluer.mutate({ instanceId: succes.instance_id })}
                      >
                        {evaluer.isPending
                          ? "Vérification..."
                          : "Le solveur de la base répond-il encore ?"}
                      </Button>
                    )}
                    <Button asChild size="sm" variant="outline">
                      <Link to="/solver-generator" search={{ instanceId: succes.instance_id }}>
                        Générer un solveur pour cette instance
                      </Link>
                    </Button>
                  </div>
                )}
                {evaluer.isError && (
                  <p className="mt-2 text-xs text-destructive">
                    {(evaluer.error as PrismeAPIError).message}
                  </p>
                )}
                {evaluer.data && (
                  <div className="mt-3">
                    <VerdictSolveur
                      evaluation={evaluer.data}
                      indiceRegeneration="Aucun repli possible ici : cliquez « Générer un solveur pour cette instance » ci-dessus."
                    />
                  </div>
                )}
              </div>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={reinitialiser}>
                {instanceAEditer ? "Modifier une autre instance" : "Ingérer une autre instance"}
              </Button>
              <Button onClick={() => fermer(false)}>Fermer</Button>
            </DialogFooter>
          </div>
        ) : (
          <>
            {instanceAEditer || scenarioDeBase ? (
              <div className="space-y-5">
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Client :</span>
                  <span className="font-medium">{clientId}</span>
                </div>

                {contraintesNonEditables.length > 0 && (
                  <p className="rounded-lg border border-border/50 bg-muted/20 p-2 text-xs text-muted-foreground">
                    {contraintesNonEditables.length} contrainte(s) supplémentaire(s) ne sont pas
                    éditables dans ce formulaire — elles seront conservées telles quelles à
                    l'enregistrement.
                  </p>
                )}

                <SelecteurUniteTemps
                  valeur={uniteTemps}
                  onChange={changerUniteTemps}
                  contexte="saisie"
                />
                <SelecteurJoursFermes valeurs={joursFermes} onChange={setJoursFermes} />

                <OngletsTRCO
                  taches={taches}
                  setTaches={setTaches}
                  ressources={ressources}
                  setRessources={setRessources}
                  contraintes={contraintes}
                  setContraintes={setContraintes}
                  objectifs={objectifs}
                  setObjectifs={setObjectifs}
                  uniteTemps={uniteTemps}
                />

                {erreur && (modifier.error ?? creerScenario.error) && (
                  <ErreursAPI erreur={erreur} />
                )}

                <DialogFooter>
                  <Button variant="outline" onClick={() => fermer(false)}>
                    Annuler
                  </Button>
                  <Button onClick={soumettreTRCO} disabled={enCours}>
                    <FileJson className="mr-2 h-4 w-4" />
                    {scenarioDeBase
                      ? creerScenario.isPending
                        ? "Création..."
                        : "Créer le scénario"
                      : modifier.isPending
                        ? "Enregistrement..."
                        : "Enregistrer les modifications"}
                  </Button>
                </DialogFooter>
              </div>
            ) : (
              <Tabs defaultValue="trco">
                <TabsList>
                  <TabsTrigger value="trco">Saisie T-R-C-O</TabsTrigger>
                  <TabsTrigger value="import">Import ERP</TabsTrigger>
                  <TabsTrigger value="fichier">Fichier Excel</TabsTrigger>
                  <TabsTrigger value="csv">Fichiers CSV</TabsTrigger>
                  <TabsTrigger value="csvlocal">CSV Local</TabsTrigger>
                  <TabsTrigger value="json">Fichier JSON</TabsTrigger>
                </TabsList>

                <TabsContent value="trco" className="space-y-5">
                  <ChampClient
                    clientId={clientId}
                    setClientId={setClientId}
                    estAdmin={estAdmin}
                    idChamp="client_id"
                  />

                  <SelecteurUniteTemps
                    valeur={uniteTemps}
                    onChange={changerUniteTemps}
                    contexte="saisie"
                  />
                  <SelecteurJoursFermes valeurs={joursFermes} onChange={setJoursFermes} />

                  <OngletsTRCO
                    taches={taches}
                    setTaches={setTaches}
                    ressources={ressources}
                    setRessources={setRessources}
                    contraintes={contraintes}
                    setContraintes={setContraintes}
                    objectifs={objectifs}
                    setObjectifs={setObjectifs}
                    uniteTemps={uniteTemps}
                  />

                  {erreur && ingerer.error && <ErreursAPI erreur={erreur} />}

                  <DialogFooter>
                    <Button variant="outline" onClick={() => fermer(false)}>
                      Annuler
                    </Button>
                    <Button onClick={soumettreTRCO} disabled={enCours}>
                      <FileJson className="mr-2 h-4 w-4" />
                      {ingerer.isPending ? "Ingestion..." : "Ingérer"}
                    </Button>
                  </DialogFooter>
                </TabsContent>

                <TabsContent value="import" className="space-y-4">
                  <div className="space-y-1.5">
                    <Label>Source</Label>
                    <Select value={source} onValueChange={setSource}>
                      <SelectTrigger className="w-64">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {SOURCES_IMPORT.map((s) => (
                          <SelectItem key={s.id} value={s.id}>
                            {s.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      L'instance est lue directement depuis la source ERP côté serveur, sans saisie
                      manuelle.
                    </p>
                  </div>

                  {erreur && importer.error && <ErreursAPI erreur={erreur} />}

                  <DialogFooter>
                    <Button variant="outline" onClick={() => fermer(false)}>
                      Annuler
                    </Button>
                    <Button onClick={soumettreImport} disabled={enCours}>
                      <Upload className="mr-2 h-4 w-4" />
                      {importer.isPending
                        ? "Import..."
                        : `Importer depuis ${SOURCES_IMPORT.find((s) => s.id === source)?.label}`}
                    </Button>
                  </DialogFooter>
                </TabsContent>

                <TabsContent value="fichier" className="space-y-4">
                  <ChampClient
                    clientId={clientId}
                    setClientId={setClientId}
                    estAdmin={estAdmin}
                    idChamp="client_id_fichier"
                  />

                  <div className="space-y-1.5">
                    <Label htmlFor="fichier_xlsx">Fichier Excel (.xlsx)</Label>
                    <Input
                      id="fichier_xlsx"
                      ref={inputFichierRef}
                      type="file"
                      accept=".xlsx"
                      onChange={(e) => setFichier(e.target.files?.[0] ?? null)}
                    />
                    <p className="text-xs text-muted-foreground">
                      Utilisez le gabarit fourni (onglets Tâches, Ressources, Précédences,
                      Compétences requises, Compatibilités), remplissez-le, puis déposez-le ici tel
                      quel. Comme pour le CSV, une tâche peut être rendue compatible avec une
                      ressource soit directement (onglet Compatibilités), soit via une compétence
                      requise couverte par cette ressource (onglet Compétences requises).
                    </p>
                    <p className="text-xs">
                      Gabarit d'exemple :{" "}
                      <a
                        href="/gabarits/gabarit_ingestion_trco.xlsx"
                        download
                        className="text-primary underline-offset-2 hover:underline"
                      >
                        gabarit_ingestion_trco.xlsx
                      </a>
                    </p>
                  </div>

                  {erreur && importerFichier.error && <ErreursAPI erreur={erreur} />}

                  <DialogFooter>
                    <Button variant="outline" onClick={() => fermer(false)}>
                      Annuler
                    </Button>
                    <Button onClick={soumettreFichier} disabled={enCours || !fichier}>
                      <FileSpreadsheet className="mr-2 h-4 w-4" />
                      {importerFichier.isPending ? "Import..." : "Importer le fichier"}
                    </Button>
                  </DialogFooter>
                </TabsContent>

                <TabsContent value="csv" className="space-y-4">
                  <ChampClient
                    clientId={clientId}
                    setClientId={setClientId}
                    estAdmin={estAdmin}
                    idChamp="client_id_csv"
                  />

                  <SelecteurUniteTemps
                    valeur={uniteTemps}
                    onChange={changerUniteTemps}
                    contexte="fichier"
                  />

                  <div className="space-y-1.5">
                    <Label htmlFor="fichier_csv_taches">Tâches (.csv)</Label>
                    <Input
                      id="fichier_csv_taches"
                      ref={inputTachesCsvRef}
                      type="file"
                      accept=".csv,text/csv"
                      onChange={(e) => setFichierTachesCsv(e.target.files?.[0] ?? null)}
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="fichier_csv_ressources">Ressources (.csv)</Label>
                    <Input
                      id="fichier_csv_ressources"
                      ref={inputRessourcesCsvRef}
                      type="file"
                      accept=".csv,text/csv"
                      onChange={(e) => setFichierRessourcesCsv(e.target.files?.[0] ?? null)}
                    />
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="fichier_csv_contraintes">Contraintes (.csv)</Label>
                    <Input
                      id="fichier_csv_contraintes"
                      ref={inputContraintesCsvRef}
                      type="file"
                      accept=".csv,text/csv"
                      onChange={(e) => setFichierContraintesCsv(e.target.files?.[0] ?? null)}
                    />
                    <p className="text-xs text-muted-foreground">
                      Trois fichiers séparés, un par axe — colonnes attendues :{" "}
                      <code className="font-mono">id,nom</code> pour Tâches,{" "}
                      <code className="font-mono">id,nom,competences,heures_par_jour</code> (
                      compétences séparées par <code className="font-mono">;</code> ;{" "}
                      <code className="font-mono">heures_par_jour</code> = durée de travail
                      quotidienne, optionnelle) pour Ressources,{" "}
                      <code className="font-mono">
                        type,tache_avant,tache_apres,tache,ressource,competence
                      </code>{" "}
                      pour Contraintes (<code className="font-mono">type</code> vaut{" "}
                      <code className="font-mono">precedence</code>,{" "}
                      <code className="font-mono">compatibilite_ressource_tache</code> ou{" "}
                      <code className="font-mono">competence_requise</code>). Aucun fichier ne porte
                      de durée : elle se fixe à la commande, tâche par tâche. En attendant, une
                      tâche sans durée vaut 1 {libelleUnite(uniteTemps)}, signalé à l'import.
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Plutôt que de saisir chaque compatibilité à la main, déclarez qu'une ressource
                      possède une compétence et qu'une tâche l'exige (
                      <code className="font-mono">competence_requise</code>) — la compatibilité est
                      calculée automatiquement pour chaque ressource qualifiée, à la durée déjà
                      déclarée pour cette tâche. Une tâche sans aucune durée déclarée est refusée :
                      aucune durée n'est devinée.
                    </p>
                    <p className="text-xs">
                      Gabarits d'exemple :{" "}
                      {(["taches", "ressources", "contraintes", "commandes"] as const)
                        .map((entite) => ({
                          nom: nomGabaritCsv(entite, uniteTemps),
                          href: hrefGabaritCsv(entite, uniteTemps),
                        }))
                        .map((gabarit, i) => (
                          <span key={gabarit.href}>
                            {i > 0 && ", "}
                            <a
                              href={gabarit.href}
                              download
                              className="text-primary underline-offset-2 hover:underline"
                            >
                              {gabarit.nom}
                            </a>
                          </span>
                        ))}
                    </p>
                  </div>

                  <div className="space-y-1.5">
                    <Label htmlFor="fichier_csv_commandes">Commandes (.csv, optionnel)</Label>
                    <Input
                      id="fichier_csv_commandes"
                      ref={inputCommandesCsvRef}
                      type="file"
                      accept=".csv,text/csv"
                      onChange={(e) => setFichierCommandesCsv(e.target.files?.[0] ?? null)}
                    />
                    <p className="text-xs text-muted-foreground">
                      Quatrième fichier optionnel — colonnes requises :{" "}
                      <code className="font-mono">id,taches</code> (
                      <code className="font-mono">taches</code> séparées par{" "}
                      <code className="font-mono">;</code>), optionnelles :{" "}
                      <code className="font-mono">client,date_limite</code> (
                      <code className="font-mono">date_limite</code> en {libelleUnite(uniteTemps)}{" "}
                      relatifs). Dérive une échéance par tâche liée (la plus contraignante si une
                      tâche appartient à plusieurs commandes) — une échéance déjà déclarée dans le
                      fichier Contraintes l'emporte toujours.
                    </p>
                  </div>

                  <label className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={genererDescriptionCsv}
                      onCheckedChange={(v) => setGenererDescriptionCsv(v === true)}
                    />
                    Générer une description métier de l'atelier (IA)
                  </label>
                  <p className="text-xs text-muted-foreground">
                    Résumé en langage naturel de l'atelier obtenu (nature du processus, étapes,
                    ressources) — n'affecte jamais les tâches/ressources/contraintes importées,
                    best-effort (aucun échec de l'import si indisponible).
                  </p>

                  {erreur && importerCsv.error && <ErreursAPI erreur={erreur} />}

                  <DialogFooter>
                    <Button variant="outline" onClick={() => fermer(false)}>
                      Annuler
                    </Button>
                    <Button
                      onClick={soumettreCsv}
                      disabled={
                        enCours ||
                        !fichierTachesCsv ||
                        !fichierRessourcesCsv ||
                        !fichierContraintesCsv
                      }
                    >
                      <Files className="mr-2 h-4 w-4" />
                      {importerCsv.isPending ? "Import..." : "Importer les fichiers"}
                    </Button>
                  </DialogFooter>
                </TabsContent>

                <TabsContent value="csvlocal" className="space-y-4">
                  <ChampClient
                    clientId={clientId}
                    setClientId={setClientId}
                    estAdmin={estAdmin}
                    idChamp="client_id_csvlocal"
                  />

                  <SelecteurUniteTemps
                    valeur={uniteTemps}
                    onChange={changerUniteTemps}
                    contexte="fichier"
                  />

                  <div className="space-y-1.5">
                    <Label htmlFor="chemin_dossier_csv">Chemin du dossier CSV (côté serveur)</Label>
                    <Input
                      id="chemin_dossier_csv"
                      value={cheminDossierCsvLocal}
                      onChange={(e) => setCheminDossierCsvLocal(e.target.value)}
                      placeholder="data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique"
                      className="font-mono text-sm"
                    />
                    <p className="text-xs text-muted-foreground">
                      Spécifiez le chemin d'un dossier présent sur le serveur contenant les trois
                      fichiers CSV requis (taches.csv, ressources.csv, contraintes.csv). Utile pour
                      imports en masse, tests avec données de référence, ou intégrations
                      automatisées.
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Exemples de dossiers disponibles :
                    </p>
                    <ul className="text-xs text-muted-foreground space-y-0.5">
                      <li className="font-mono ml-4">
                        data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique
                      </li>
                      <li className="font-mono ml-4">
                        data/donnees_brutes/csv/industrie_manufacturiere/atelier_mecanique
                      </li>
                      <li className="font-mono ml-4">
                        data/donnees_brutes/csv/services/centre_appels
                      </li>
                    </ul>
                  </div>

                  {erreur && importerCsvLocal.error && <ErreursAPI erreur={erreur} />}

                  <DialogFooter>
                    <Button variant="outline" onClick={() => fermer(false)}>
                      Annuler
                    </Button>
                    <Button
                      onClick={soumettreCsvLocal}
                      disabled={enCours || !cheminDossierCsvLocal.trim()}
                    >
                      <FolderOpen className="mr-2 h-4 w-4" />
                      {importerCsvLocal.isPending ? "Import..." : "Importer depuis le serveur"}
                    </Button>
                  </DialogFooter>
                </TabsContent>

                <TabsContent value="json" className="space-y-4">
                  <ChampClient
                    clientId={clientId}
                    setClientId={setClientId}
                    estAdmin={estAdmin}
                    idChamp="client_id_json"
                  />

                  <SelecteurUniteTemps
                    valeur={uniteTemps}
                    onChange={changerUniteTemps}
                    contexte="fichier"
                  />

                  <div className="space-y-1.5">
                    <Label htmlFor="fichier_json">Fichier JSON (.json)</Label>
                    <Input
                      id="fichier_json"
                      ref={inputJsonRef}
                      type="file"
                      accept=".json,application/json"
                      onChange={(e) => {
                        setFichierJson(e.target.files?.[0] ?? null);
                        setErreurParseJson(null);
                      }}
                    />
                    <p className="text-xs text-muted-foreground">
                      Déposez un fichier JSON au format T-R-C-O (mêmes champs que la saisie manuelle
                      : taches, ressources, contraintes, objectifs) — ingéré tel quel si déjà
                      complet. Plutôt que de déclarer chaque compatibilité à la main, une tâche peut
                      exiger une compétence (<code className="font-mono">competence_requise</code>)
                      : sa compatibilité avec toute ressource dont les{" "}
                      <code className="font-mono">competences</code> la couvrent est alors calculée
                      automatiquement, à la durée déjà déclarée pour cette tâche — aucune durée
                      n'est devinée. Les champs <code className="font-mono">duree</code> et
                      échéances sont lus en {libelleUnite(uniteTemps)} : l'unité choisie ci-dessus
                      remplace le champ <code className="font-mono">unite_temps</code> du fichier
                      s'il en contient un.
                    </p>
                    <p className="text-xs">
                      Gabarit d'exemple :{" "}
                      <a
                        href={hrefGabaritJson(uniteTemps)}
                        download
                        className="text-primary underline-offset-2 hover:underline"
                      >
                        {nomGabaritJson(uniteTemps)}
                      </a>
                    </p>
                  </div>

                  {erreurParseJson && (
                    <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                      <div className="flex items-center gap-2 font-medium">
                        <AlertCircle className="h-4 w-4" /> {erreurParseJson}
                      </div>
                    </div>
                  )}
                  {erreur && importerJson.error && <ErreursAPI erreur={erreur} />}

                  <DialogFooter>
                    <Button variant="outline" onClick={() => fermer(false)}>
                      Annuler
                    </Button>
                    <Button onClick={soumettreJson} disabled={enCours || !fichierJson}>
                      <Braces className="mr-2 h-4 w-4" />
                      {importerJson.isPending ? "Import..." : "Importer le fichier"}
                    </Button>
                  </DialogFooter>
                </TabsContent>
              </Tabs>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

// Les quatre sections T-R-C-O sous onglets plutôt qu'empilées verticalement —
// une instance avec plusieurs dizaines de tâches rendait Ressources/
// Contraintes/Objectifs inatteignables sans défiler toute la liste des
// tâches d'abord. Un seul onglet visible à la fois, changer d'onglet ne
// perd aucune saisie (tout reste dans le state du parent, pas démonté).
function OngletsTRCO({
  taches,
  setTaches,
  ressources,
  setRessources,
  contraintes,
  setContraintes,
  objectifs,
  setObjectifs,
  uniteTemps,
}: {
  taches: TacheLigne[];
  setTaches: React.Dispatch<React.SetStateAction<TacheLigne[]>>;
  ressources: RessourceLigne[];
  setRessources: React.Dispatch<React.SetStateAction<RessourceLigne[]>>;
  contraintes: ContrainteLigne[];
  setContraintes: React.Dispatch<React.SetStateAction<ContrainteLigne[]>>;
  objectifs: ObjectifLigne[];
  setObjectifs: React.Dispatch<React.SetStateAction<ObjectifLigne[]>>;
  uniteTemps: UniteTemps;
}) {
  return (
    <Tabs defaultValue="taches">
      <TabsList>
        <TabsTrigger value="taches">Tâches ({taches.length})</TabsTrigger>
        <TabsTrigger value="ressources">Ressources ({ressources.length})</TabsTrigger>
        <TabsTrigger value="contraintes">Contraintes ({contraintes.length})</TabsTrigger>
        <TabsTrigger value="objectifs">Objectifs ({objectifs.length})</TabsTrigger>
      </TabsList>
      <TabsContent value="taches" className="pt-3">
        <SectionTaches taches={taches} setTaches={setTaches} />
      </TabsContent>
      <TabsContent value="ressources" className="pt-3">
        <SectionRessources
          ressources={ressources}
          setRessources={setRessources}
          setContraintes={setContraintes}
        />
      </TabsContent>
      <TabsContent value="contraintes" className="pt-3">
        <SectionContraintes
          contraintes={contraintes}
          setContraintes={setContraintes}
          taches={taches}
          ressources={ressources}
          uniteTemps={uniteTemps}
        />
      </TabsContent>
      <TabsContent value="objectifs" className="pt-3">
        <SectionObjectifs
          objectifs={objectifs}
          setObjectifs={setObjectifs}
          uniteTemps={uniteTemps}
        />
      </TabsContent>
    </Tabs>
  );
}

function SectionTaches({
  taches,
  setTaches,
}: {
  taches: TacheLigne[];
  setTaches: React.Dispatch<React.SetStateAction<TacheLigne[]>>;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Tâches</Label>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setTaches((t) => [...t, nouvelleTache()])}
        >
          <Plus className="mr-1 h-3.5 w-3.5" /> Ajouter
        </Button>
      </div>
      <div className="space-y-2">
        {taches.map((t, i) => (
          <div key={t.clef} className="flex flex-wrap gap-2">
            <Input
              placeholder="id (ex: T1)"
              value={t.id}
              title={t.id}
              onChange={(e) =>
                setTaches((arr) => arr.map((x, j) => (j === i ? { ...x, id: e.target.value } : x)))
              }
              className="w-48 font-mono text-xs"
            />
            <Input
              placeholder="nom (optionnel)"
              value={t.nom ?? ""}
              onChange={(e) =>
                setTaches((arr) => arr.map((x, j) => (j === i ? { ...x, nom: e.target.value } : x)))
              }
              className="min-w-32 flex-1"
            />
            {/* Pas de champ "priorité" ici : c'est un simple départage entre plannings sinon
                équivalents (jamais lu comme contrainte ni comme poids d'objectif, voir
                generation_solveur.md), rarement utile en pratique et retiré de ce formulaire pour
                ne pas laisser croire qu'il faut le remplir. `t.priorite` reste porté tel quel s'il
                était déjà présent sur l'instance chargée (jamais effacé silencieusement) — modifiable
                uniquement via l'inspecteur de tâche du graphe de flux, si jamais nécessaire. */}
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={() => setTaches((arr) => arr.filter((_, j) => j !== i))}
              disabled={taches.length === 1}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

function SectionRessources({
  ressources,
  setRessources,
  setContraintes,
}: {
  ressources: RessourceLigne[];
  setRessources: React.Dispatch<React.SetStateAction<RessourceLigne[]>>;
  // Optionnel : présent seulement là où le formulaire édite aussi les contraintes
  // (les deux call sites actuels de ce composant le passent toujours) — permet le
  // bouton "Marquer indisponible" ci-dessous sans dupliquer SectionContraintes.
  setContraintes?: React.Dispatch<React.SetStateAction<ContrainteLigne[]>>;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Ressources</Label>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setRessources((r) => [...r, nouvelleRessource()])}
        >
          <Plus className="mr-1 h-3.5 w-3.5" /> Ajouter
        </Button>
      </div>
      <div className="space-y-2">
        {ressources.map((r, i) => (
          <div key={r.clef} className="flex flex-wrap gap-2">
            <Input
              placeholder="id (ex: R1)"
              value={r.id}
              title={r.id}
              onChange={(e) =>
                setRessources((arr) =>
                  arr.map((x, j) => (j === i ? { ...x, id: e.target.value } : x)),
                )
              }
              className="w-48 font-mono text-xs"
            />
            <Input
              placeholder="nom (optionnel)"
              value={r.nom ?? ""}
              onChange={(e) =>
                setRessources((arr) =>
                  arr.map((x, j) => (j === i ? { ...x, nom: e.target.value } : x)),
                )
              }
              className="min-w-32 flex-1"
            />
            <Input
              placeholder="compétences (séparées par des virgules)"
              value={r.competencesTexte}
              onChange={(e) =>
                setRessources((arr) =>
                  arr.map((x, j) => (j === i ? { ...x, competencesTexte: e.target.value } : x)),
                )
              }
              className="min-w-40 flex-1"
            />
            <Input
              placeholder="h. travaillées / jour"
              title="Durée de travail quotidienne (1 à 24 h) — vide : disponible en continu. Prise en compte pour un atelier en heures."
              type="number"
              min={1}
              max={24}
              value={r.heuresParJourTexte}
              onChange={(e) =>
                setRessources((arr) =>
                  arr.map((x, j) => (j === i ? { ...x, heuresParJourTexte: e.target.value } : x)),
                )
              }
              className="w-36"
            />
            {setContraintes && (
              <Button
                type="button"
                size="icon"
                variant="ghost"
                title="Marquer indisponible (panne, congé...) — sans supprimer la ressource ni ses compatibilités"
                onClick={() =>
                  setContraintes((c) => [
                    ...c,
                    { ...nouvelleContrainte(), type: "disponibilite_ressource", ressource: r.id },
                  ])
                }
                disabled={!r.id.trim()}
              >
                <CalendarOff className="h-4 w-4" />
              </Button>
            )}
            <Button
              type="button"
              size="icon"
              variant="ghost"
              onClick={() => setRessources((arr) => arr.filter((_, j) => j !== i))}
              disabled={ressources.length === 1}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}

function SectionContraintes({
  contraintes,
  setContraintes,
  taches,
  ressources,
  uniteTemps,
}: {
  contraintes: ContrainteLigne[];
  setContraintes: React.Dispatch<React.SetStateAction<ContrainteLigne[]>>;
  taches: TacheLigne[];
  ressources: RessourceLigne[];
  uniteTemps: UniteTemps;
}) {
  function majLigne(i: number, patch: Partial<ContrainteLigne>) {
    setContraintes((arr) => arr.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Contraintes</Label>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => setContraintes((c) => [...c, nouvelleContrainte()])}
        >
          <Plus className="mr-1 h-3.5 w-3.5" /> Ajouter
        </Button>
      </div>
      <div className="space-y-2">
        {contraintes.map((c, i) => (
          <div
            key={c.clef}
            className="flex flex-wrap items-center gap-2 rounded-lg border border-border/50 p-2"
          >
            <Select
              value={c.type}
              onValueChange={(v) => majLigne(i, { type: v as TypeContrainte })}
            >
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="precedence">Précédence</SelectItem>
                <SelectItem value="compatibilite_ressource_tache">
                  Compatibilité ressource ↔ tâche
                </SelectItem>
                <SelectItem value="echeance">Échéance</SelectItem>
                <SelectItem value="competence_requise">Compétence requise</SelectItem>
                <SelectItem value="changement_serie">Changement de série</SelectItem>
                <SelectItem value="disponibilite_ressource">Disponibilité ressource</SelectItem>
              </SelectContent>
            </Select>

            {c.type === "precedence" && (
              <>
                <ChampSelectId
                  placeholder="avant"
                  value={c.avant}
                  options={taches}
                  onChange={(v) => majLigne(i, { avant: v })}
                />
                <ChampSelectId
                  placeholder="après"
                  value={c.apres}
                  options={taches}
                  onChange={(v) => majLigne(i, { apres: v })}
                />
              </>
            )}
            {c.type === "compatibilite_ressource_tache" && (
              <>
                <ChampSelectId
                  placeholder="tâche"
                  value={c.tache}
                  options={taches}
                  onChange={(v) => majLigne(i, { tache: v })}
                />
                <ChampSelectId
                  placeholder="ressource"
                  value={c.ressource}
                  options={ressources}
                  onChange={(v) => majLigne(i, { ressource: v })}
                />
                <Input
                  placeholder={`durée (${libelleUnite(uniteTemps)})`}
                  type="number"
                  min={1}
                  value={c.duree}
                  onChange={(e) => majLigne(i, { duree: e.target.value })}
                  className="w-32"
                />
              </>
            )}
            {c.type === "echeance" && (
              <>
                <ChampSelectId
                  placeholder="tâche"
                  value={c.tache}
                  options={taches}
                  onChange={(v) => majLigne(i, { tache: v })}
                />
                <Input
                  type={uniteTemps === "heures" ? "datetime-local" : "date"}
                  min={
                    uniteTemps === "heures"
                      ? formatEntreeDateHeure(aujourdhui())
                      : formatEntreeDate(aujourdhui())
                  }
                  value={c.echeance}
                  onChange={(e) => majLigne(i, { echeance: e.target.value })}
                  className="w-40"
                />
              </>
            )}
            {c.type === "competence_requise" && (
              <>
                <ChampSelectId
                  placeholder="tâche"
                  value={c.tache}
                  options={taches}
                  onChange={(v) => majLigne(i, { tache: v })}
                />
                <Input
                  placeholder="compétence"
                  value={c.competence}
                  onChange={(e) => majLigne(i, { competence: e.target.value })}
                  className="w-40"
                />
              </>
            )}
            {c.type === "changement_serie" && (
              <>
                <ChampSelectId
                  placeholder="ressource"
                  value={c.ressource}
                  options={ressources}
                  onChange={(v) => majLigne(i, { ressource: v })}
                />
                <ChampSelectId
                  placeholder="avant"
                  value={c.avant}
                  options={taches}
                  onChange={(v) => majLigne(i, { avant: v })}
                />
                <ChampSelectId
                  placeholder="après"
                  value={c.apres}
                  options={taches}
                  onChange={(v) => majLigne(i, { apres: v })}
                />
                <Input
                  placeholder={`durée setup (${libelleUnite(uniteTemps)})`}
                  type="number"
                  min={0}
                  value={c.duree}
                  onChange={(e) => majLigne(i, { duree: e.target.value })}
                  className="w-36"
                />
              </>
            )}
            {c.type === "disponibilite_ressource" && (
              <>
                <ChampSelectId
                  placeholder="ressource"
                  value={c.ressource}
                  options={ressources}
                  onChange={(v) => majLigne(i, { ressource: v })}
                />
                <Input
                  type={uniteTemps === "heures" ? "datetime-local" : "date"}
                  min={
                    uniteTemps === "heures"
                      ? formatEntreeDateHeure(aujourdhui())
                      : formatEntreeDate(aujourdhui())
                  }
                  value=""
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v && !c.joursIndisponibles.includes(v)) {
                      majLigne(i, { joursIndisponibles: [...c.joursIndisponibles, v].sort() });
                    }
                  }}
                  className="w-40"
                  title={
                    uniteTemps === "heures"
                      ? "Ajouter un instant d'indisponibilité"
                      : "Ajouter une date d'indisponibilité"
                  }
                />
                {c.joursIndisponibles.map((jour) => (
                  <Badge key={jour} variant="secondary" className="gap-1 font-normal">
                    {uniteTemps === "heures"
                      ? new Date(jour).toLocaleString("fr-FR")
                      : new Date(jour).toLocaleDateString("fr-FR")}
                    <button
                      type="button"
                      onClick={() =>
                        majLigne(i, {
                          joursIndisponibles: c.joursIndisponibles.filter((j) => j !== jour),
                        })
                      }
                      aria-label={`Retirer le ${jour}`}
                    >
                      <X className="h-3 w-3" />
                    </button>
                  </Badge>
                ))}
                {uniteTemps === "heures" ? (
                  <GrilleMotifHebdomadaireHeures
                    valeurs={c.joursSemaineIndisponibles}
                    onChange={(v) => majLigne(i, { joursSemaineIndisponibles: v })}
                  />
                ) : (
                  <div className="flex items-center gap-1" title="Motif hebdomadaire récurrent">
                    {NOMS_JOURS_SEMAINE_COURTS.map((nom, jourSemaine) => {
                      const actif = c.joursSemaineIndisponibles.includes(jourSemaine);
                      return (
                        <button
                          key={jourSemaine}
                          type="button"
                          onClick={() =>
                            majLigne(i, {
                              joursSemaineIndisponibles: actif
                                ? c.joursSemaineIndisponibles.filter((j) => j !== jourSemaine)
                                : [...c.joursSemaineIndisponibles, jourSemaine],
                            })
                          }
                          className={`rounded px-1.5 py-1 text-xs ${
                            actif
                              ? "bg-primary text-primary-foreground"
                              : "bg-muted text-muted-foreground"
                          }`}
                        >
                          {nom}
                        </button>
                      );
                    })}
                  </div>
                )}
              </>
            )}

            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="ml-auto"
              onClick={() => setContraintes((arr) => arr.filter((_, j) => j !== i))}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        ))}
        {contraintes.length === 0 && (
          <p className="text-xs text-muted-foreground">
            Aucune contrainte — chaque tâche doit avoir au moins une compatibilité ressource-tâche
            pour être ingérée.
          </p>
        )}
      </div>
    </div>
  );
}

// Motif hebdomadaire récurrent en mode heures : une grille 7 jours × 24 heures plutôt que 7
// boutons — chaque cellule (jourSemaine, heure) bascule l'index plat `jourSemaine * 24 + heure`
// dans `valeurs` (même convention JS Date.getDay() que le mode jours, converti en position dans
// le cycle DSL de 168 à la soumission — voir construireInstance/contrainteVersLigne). Compacte
// (cellules 20px) : 168 cases restent lisibles à cette taille, une grille par bouton comme en
// mode jours serait illisible à cette densité.
function GrilleMotifHebdomadaireHeures({
  valeurs,
  onChange,
}: {
  valeurs: number[];
  onChange: (v: number[]) => void;
}) {
  const heures = Array.from({ length: 24 }, (_, h) => h);
  function bascule(index: number) {
    onChange(valeurs.includes(index) ? valeurs.filter((v) => v !== index) : [...valeurs, index]);
  }
  return (
    <div
      className="space-y-0.5 rounded-md border border-border/50 p-1.5"
      title="Motif hebdomadaire récurrent"
    >
      {NOMS_JOURS_SEMAINE_COURTS.map((nom, jourSemaine) => (
        <div key={jourSemaine} className="flex items-center gap-1">
          <span className="w-7 shrink-0 text-[10px] text-muted-foreground">{nom}</span>
          <div className="flex gap-px">
            {heures.map((h) => {
              const index = jourSemaine * 24 + h;
              const actif = valeurs.includes(index);
              return (
                <button
                  key={h}
                  type="button"
                  onClick={() => bascule(index)}
                  title={`${nom} ${h}h-${h + 1}h`}
                  className={`h-4 w-3 rounded-[2px] ${actif ? "bg-primary" : "bg-muted"}`}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// Inverses de construireInstance — pour préremplir le formulaire "Saisie
// T-R-C-O" à partir d'une instance existante (bouton "Dupliquer et
// modifier", page Instances).
function tacheVersLigne(t: Tache): TacheLigne {
  return { clef: idLocal(), id: t.id, nom: t.nom, priorite: t.priorite };
}

function ressourceVersLigne(r: Ressource): RessourceLigne {
  return {
    clef: idLocal(),
    id: r.id,
    nom: r.nom,
    competences: r.competences,
    competencesTexte: r.competences.join(", "),
    heuresParJourTexte: r.heures_par_jour !== undefined ? String(r.heures_par_jour) : "",
  };
}

// Le formulaire T-R-C-O ne sait éditer que ces 4 types (voir TypeContrainte
// et le <Select> de SectionContraintes) — `capacite`/`disponibilite_ressource`
// existent côté DSL mais n'ont pas de champs dédiés ici. Sans ce filtre, les
// convertir via contrainteVersLigne serait non exhaustif ; les ignorer sans
// les préserver ailleurs les supprimerait silencieusement à l'enregistrement
// d'une instance qui en a déjà — voir contraintesNonEditables plus bas.
const TYPES_CONTRAINTE_EDITABLES = [
  "precedence",
  "compatibilite_ressource_tache",
  "echeance",
  "competence_requise",
  "changement_serie",
  "disponibilite_ressource",
] as const;

function estContrainteEditable(
  c: Contrainte,
): c is Extract<Contrainte, { type: (typeof TYPES_CONTRAINTE_EDITABLES)[number] }> {
  return (TYPES_CONTRAINTE_EDITABLES as readonly string[]).includes(c.type);
}

function contrainteVersLigne(
  c: Extract<Contrainte, { type: (typeof TYPES_CONTRAINTE_EDITABLES)[number] }>,
  uniteTemps: UniteTemps = "jours",
): ContrainteLigne {
  const base = nouvelleContrainte();
  switch (c.type) {
    case "precedence":
      return { ...base, clef: idLocal(), type: "precedence", avant: c.avant, apres: c.apres };
    case "compatibilite_ressource_tache":
      return {
        ...base,
        clef: idLocal(),
        type: "compatibilite_ressource_tache",
        tache: c.tache,
        ressource: c.ressource,
        duree: c.duree.toString(),
      };
    case "echeance": {
      const ancrage = aujourdhui();
      const date = dateDepuisAncrage(c.echeance, ancrage, uniteTemps);
      return {
        ...base,
        clef: idLocal(),
        type: "echeance",
        tache: c.tache,
        echeance: uniteTemps === "heures" ? formatEntreeDateHeure(date) : formatEntreeDate(date),
      };
    }
    case "competence_requise":
      return {
        ...base,
        clef: idLocal(),
        type: "competence_requise",
        tache: c.tache,
        competence: c.competence,
      };
    case "changement_serie":
      return {
        ...base,
        clef: idLocal(),
        type: "changement_serie",
        ressource: c.ressource,
        avant: c.tache_avant,
        apres: c.tache_apres,
        duree: c.duree_setup.toString(),
      };
    case "disponibilite_ressource": {
      const ancrage = aujourdhui();
      const referenceCycle =
        uniteTemps === "heures" ? ancrage.getDay() * 24 + ancrage.getHours() : ancrage.getDay();
      const cycle = longueurCycle(uniteTemps);
      return {
        ...base,
        clef: idLocal(),
        type: "disponibilite_ressource",
        ressource: c.ressource,
        joursIndisponibles: c.jours_indisponibles.map((j) => {
          const date = dateDepuisAncrage(j, ancrage, uniteTemps);
          return uniteTemps === "heures" ? formatEntreeDateHeure(date) : formatEntreeDate(date);
        }),
        joursSemaineIndisponibles: (c.jours_semaine_indisponibles ?? []).map(
          (p) => (referenceCycle + p) % cycle,
        ),
      };
    }
  }
}

// Inverse de construireObjectifs — pour préremplir le formulaire d'édition
// à partir des objectifs déjà stockés d'une instance existante.
export function objectifVersLigne(o: Objectif): ObjectifLigne {
  const base = nouvelObjectif();
  const ligne: ObjectifLigne = {
    ...base,
    clef: idLocal(),
    type: o.type,
    poids: o.poids?.toString() ?? "1",
  };
  switch (o.type) {
    case "minimiser_makespan":
      return { ...ligne, makespanCible: o.makespan_cible?.toString() ?? "" };
    case "equilibrer_charge":
      return {
        ...ligne,
        methode: o.methode ?? "ecart_max",
        ressourcesCibles: o.ressources_cibles?.join(", ") ?? "",
      };
    case "minimiser_retards":
      return {
        ...ligne,
        fonctionPenalite: o.fonction_penalite ?? "lineaire",
        seuilGrace: o.seuil_grace?.toString() ?? "",
      };
    case "maximiser_utilisation":
      return { ...ligne, ressourcesPrioritaires: o.ressources_prioritaires?.join(", ") ?? "" };
    case "minimiser_changements":
      return ligne;
  }
}

export function SectionObjectifs({
  objectifs,
  setObjectifs,
  uniteTemps = "jours",
}: {
  objectifs: ObjectifLigne[];
  setObjectifs: React.Dispatch<React.SetStateAction<ObjectifLigne[]>>;
  // Unité de l'instance, pour le libellé du seuil de grâce (minimiser_retards) — optionnelle,
  // "jours" par défaut comme InstanceTRCO.unite_temps.
  uniteTemps?: UniteTemps;
}) {
  function majLigne(i: number, patch: Partial<ObjectifLigne>) {
    setObjectifs((arr) => arr.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  }

  // Replié par défaut sur chaque ligne — un utilisateur ordinaire n'a besoin que du poids, jamais
  // de choisir une "fonction de pénalité" ou une "méthode" pour comprendre ce qu'il fait.
  const [avancesOuverts, setAvancesOuverts] = useState<Set<string>>(new Set());
  function basculerAvance(clef: string) {
    setAvancesOuverts((s) => {
      const suivant = new Set(s);
      if (suivant.has(clef)) suivant.delete(clef);
      else suivant.add(clef);
      return suivant;
    });
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Objectifs</Label>
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            // Remet chaque poids à 1 (la valeur par défaut d'un objectif) — pur confort de saisie,
            // aucun changement de comportement du solveur : les poids n'ont jamais eu besoin de
            // sommer à 1 ni d'être dans une plage donnée (voir generation_solveur.md, "Objectifs").
            // Sans effet à un seul objectif (déjà expliqué à l'utilisateur), donc désactivé alors.
            onClick={() => setObjectifs((o) => o.map((x) => ({ ...x, poids: "1" })))}
            disabled={objectifs.length < 2}
            title="Remet chaque poids à 1 — n'a d'effet qu'avec plusieurs objectifs"
          >
            <Scale className="mr-1 h-3.5 w-3.5" /> Égaliser les poids
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setObjectifs((o) => [...o, nouvelObjectif()])}
          >
            <Plus className="mr-1 h-3.5 w-3.5" /> Ajouter
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        {objectifs.map((o, i) => {
          const aOptions = TYPES_AVEC_OPTIONS_AVANCEES.has(o.type);
          const ouvert = aOptions && avancesOuverts.has(o.clef);
          return (
            <div key={o.clef} className="rounded-lg border border-border/50 p-2">
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={o.type}
                  onValueChange={(v) => majLigne(i, { type: v as TypeObjectif })}
                >
                  <SelectTrigger className="w-56">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(LABELS_OBJECTIF) as TypeObjectif[]).map((t) => (
                      <SelectItem key={t} value={t}>
                        {LABELS_OBJECTIF[t]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Input
                  placeholder="poids"
                  type="number"
                  min={0}
                  step="0.1"
                  value={o.poids}
                  onChange={(e) => majLigne(i, { poids: e.target.value })}
                  className="w-24"
                />

                {aOptions && (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="text-xs text-muted-foreground"
                    onClick={() => basculerAvance(o.clef)}
                  >
                    {ouvert ? (
                      <ChevronDown className="mr-1 h-3.5 w-3.5" />
                    ) : (
                      <ChevronRight className="mr-1 h-3.5 w-3.5" />
                    )}
                    Options avancées
                  </Button>
                )}

                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="ml-auto"
                  onClick={() => setObjectifs((arr) => arr.filter((_, j) => j !== i))}
                  disabled={objectifs.length === 1}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>

              {ouvert && (
                <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-border/50 pt-2">
                  {o.type === "minimiser_makespan" && (
                    <Input
                      placeholder={`makespan cible (${libelleUnite(uniteTemps)}, optionnel)`}
                      type="number"
                      min={0}
                      value={o.makespanCible}
                      onChange={(e) => majLigne(i, { makespanCible: e.target.value })}
                      className="w-56"
                    />
                  )}
                  {o.type === "equilibrer_charge" && (
                    <>
                      <Select
                        value={o.methode}
                        onValueChange={(v) =>
                          majLigne(i, { methode: v as ObjectifLigne["methode"] })
                        }
                      >
                        <SelectTrigger className="w-36">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="ecart_max">Écart max</SelectItem>
                          <SelectItem value="variance">Variance</SelectItem>
                          <SelectItem value="gini">Gini</SelectItem>
                        </SelectContent>
                      </Select>
                      <Input
                        placeholder="ressources ciblées (optionnel)"
                        value={o.ressourcesCibles}
                        onChange={(e) => majLigne(i, { ressourcesCibles: e.target.value })}
                        className="w-56"
                      />
                    </>
                  )}
                  {o.type === "minimiser_retards" && (
                    <>
                      <Select
                        value={o.fonctionPenalite}
                        onValueChange={(v) =>
                          majLigne(i, { fonctionPenalite: v as ObjectifLigne["fonctionPenalite"] })
                        }
                      >
                        <SelectTrigger className="w-40">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="lineaire">Linéaire</SelectItem>
                          <SelectItem value="quadratique">Quadratique</SelectItem>
                          <SelectItem value="exponentielle">Exponentielle</SelectItem>
                        </SelectContent>
                      </Select>
                      <Input
                        placeholder={`seuil de grâce (${libelleUnite(uniteTemps)})`}
                        type="number"
                        min={0}
                        value={o.seuilGrace}
                        onChange={(e) => majLigne(i, { seuilGrace: e.target.value })}
                        className="w-40"
                      />
                    </>
                  )}
                  {o.type === "maximiser_utilisation" && (
                    <Input
                      placeholder="ressources prioritaires (optionnel)"
                      value={o.ressourcesPrioritaires}
                      onChange={(e) => majLigne(i, { ressourcesPrioritaires: e.target.value })}
                      className="w-56"
                    />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        Plusieurs objectifs sont combinés selon leur poids relatif (ex. 0.7 équilibrage + 0.3
        makespan). Les listes "ressources" acceptent des ids séparés par des virgules ; laissez vide
        pour "toutes".
      </p>
    </div>
  );
}

function ChampClient({
  clientId,
  setClientId,
  estAdmin,
  idChamp,
}: {
  clientId: string;
  setClientId: (v: string) => void;
  estAdmin: boolean;
  idChamp: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label htmlFor={idChamp}>Client</Label>
      <Input
        id={idChamp}
        value={clientId}
        onChange={(e) => setClientId(e.target.value)}
        disabled={!estAdmin}
      />
      {!estAdmin && (
        <p className="text-xs text-muted-foreground">Associé automatiquement à votre compte.</p>
      )}
    </div>
  );
}

// Réutilisé par les onglets Saisie T-R-C-O et Fichiers CSV (voir soumettreTRCO/soumettreCsv) —
// bascule l'unité de tous les entiers duree/echeance/debut de l'instance à ingérer. Changer
// cette valeur en cours d'édition ne rééchelonne jamais les nombres déjà saisis (un "5" reste un
// "5") — seule sa signification (jours vs heures) change, à l'utilisateur de le savoir.
function SelecteurUniteTemps({
  valeur,
  onChange,
  contexte,
}: {
  valeur: UniteTemps;
  onChange: (v: UniteTemps) => void;
  // "saisie" : le formulaire T-R-C-O, dont les valeurs déjà tapées sont converties au changement.
  // "fichier" : un import (CSV, JSON) — l'unité dit comment lire les entiers du fichier, rien n'est
  // converti, et le gabarit proposé suit ce choix.
  contexte: "saisie" | "fichier";
}) {
  return (
    <div className="space-y-1.5">
      <Label>Unité de temps</Label>
      <Select value={valeur} onValueChange={(v) => onChange(v as UniteTemps)}>
        <SelectTrigger className="w-48">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="heures">Heures</SelectItem>
          <SelectItem value="jours">Jours</SelectItem>
        </SelectContent>
      </Select>
      <p className="text-xs text-muted-foreground">
        {contexte === "saisie"
          ? "Unité des durées/échéances de cette instance — jamais un mélange des deux. Changer " +
            "d'unité convertit les valeurs déjà saisies (1 jour = 24 heures ; en repassant en " +
            "jours, une durée est arrondie au jour supérieur)."
          : "Unité dans laquelle les durées et échéances du fichier sont écrites — elles sont " +
            "lues telles quelles, sans conversion. Le gabarit proposé suit ce choix."}
      </p>
    </div>
  );
}

// Jours de la semaine fermés par défaut (dsl/schema/instance.py::InstanceTRCO.jours_fermes) —
// consommé uniquement par la correction post-solveur (validation_engine/jours_non_ouvres.py),
// jamais par le solveur généré ni par ContrainteDisponibiliteRessource (mécanisme séparé, opt-in,
// propre à chaque ressource, réglé plus bas dans le formulaire). Même patron de boutons que le
// motif hebdomadaire par ressource ci-dessus, mais un seul réglage partagé par toute l'instance.
function SelecteurJoursFermes({
  valeurs,
  onChange,
}: {
  valeurs: number[];
  onChange: (v: number[]) => void;
}) {
  return (
    <div className="space-y-1.5">
      <Label>Jours fermés par défaut</Label>
      <div
        className="flex items-center gap-1"
        title="Jours fermés par défaut pour toutes les ressources"
      >
        {NOMS_JOURS_SEMAINE_COURTS.map((nom, jourSemaine) => {
          const actif = valeurs.includes(jourSemaine);
          return (
            <button
              key={jourSemaine}
              type="button"
              onClick={() =>
                onChange(
                  actif ? valeurs.filter((j) => j !== jourSemaine) : [...valeurs, jourSemaine],
                )
              }
              className={`rounded px-1.5 py-1 text-xs ${
                actif ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"
              }`}
            >
              {nom}
            </button>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">
        Une tâche que le solveur placerait sur un de ces jours est décalée après coup au prochain
        jour ouvert — n'affecte jamais le solveur généré lui-même, seul le planning final en tient
        compte.
      </p>
    </div>
  );
}

function ChampSelectId({
  placeholder,
  value,
  options,
  onChange,
}: {
  placeholder: string;
  value: string;
  options: { id: string }[];
  onChange: (v: string) => void;
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger className="w-32">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {options
          .filter((o) => o.id)
          .map((o) => (
            <SelectItem key={o.id} value={o.id}>
              {o.id}
            </SelectItem>
          ))}
      </SelectContent>
    </Select>
  );
}

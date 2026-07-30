import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Upload, FileJson, FileSpreadsheet, Files, Braces, CheckCircle2, AlertCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
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
  useImporterViaAdaptateur,
  useImporterFichierTableur,
  useImporterFichiersCsv,
  useImporterJsonAvecCompetences,
  PrismeAPIError,
  type Contrainte,
  type InstanceTRCO,
  type Objectif,
  type Ressource,
  type Tache,
  type TypeContrainte,
  type TypeObjectif,
} from "@/integrations/prisme";
import { useAuth } from "@/integrations/prisme/auth";

// Adaptateurs ERP réellement branchés côté backend (POST /adapters/{id}/ingerer).
// Ajouter un adaptateur = ajouter une entrée ici, aucun autre changement de composant.
const SOURCES_IMPORT = [{ id: "greensig", label: "GreenSIG" }] as const;

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
}
interface ContrainteLigne {
  clef: string;
  type: TypeContrainte;
  avant: string;
  apres: string;
  tache: string;
  ressource: string;
  duree: string;
  echeance: string;
  competence: string;
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

function nouvelleTache(): TacheLigne {
  return { clef: idLocal(), id: "", nom: "" };
}
function nouvelleRessource(): RessourceLigne {
  return { clef: idLocal(), id: "", nom: "", competences: [], competencesTexte: "" };
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
            ? { ressources_cibles: o.ressourcesCibles.split(",").map((s) => s.trim()).filter(Boolean) }
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
            ? { ressources_prioritaires: o.ressourcesPrioritaires.split(",").map((s) => s.trim()).filter(Boolean) }
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

function construireInstance(
  taches: TacheLigne[],
  ressources: RessourceLigne[],
  contraintes: ContrainteLigne[],
  objectifs: ObjectifLigne[],
): InstanceTRCO {
  return {
    taches: taches.map(({ id, nom, priorite }) => ({
      id,
      ...(nom ? { nom } : {}),
      ...(priorite ? { priorite } : {}),
    })),
    ressources: ressources.map(({ id, nom, competencesTexte }) => ({
      id,
      ...(nom ? { nom } : {}),
      competences: competencesTexte
        .split(",")
        .map((c) => c.trim())
        .filter(Boolean),
    })),
    contraintes: contraintes.map((c): Contrainte => {
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
        case "echeance":
          return { type: "echeance", tache: c.tache, echeance: Number(c.echeance) };
        case "competence_requise":
          return { type: "competence_requise", tache: c.tache, competence: c.competence };
      }
    }),
    objectifs: construireObjectifs(objectifs),
  };
}

function ErreursAPI({ erreur }: { erreur: PrismeAPIError }) {
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
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const queryClient = useQueryClient();
  const ingerer = useIngererInstance();
  const importer = useImporterViaAdaptateur();
  const importerFichier = useImporterFichierTableur();
  const importerCsv = useImporterFichiersCsv();
  const importerJson = useImporterJsonAvecCompetences();
  const { utilisateur } = useAuth();
  const estAdmin = utilisateur?.role === "admin";

  const [clientId, setClientId] = useState(utilisateur?.client_id ?? "");
  const [taches, setTaches] = useState<TacheLigne[]>([nouvelleTache()]);
  const [ressources, setRessources] = useState<RessourceLigne[]>([nouvelleRessource()]);
  const [contraintes, setContraintes] = useState<ContrainteLigne[]>([]);
  const [objectifs, setObjectifs] = useState<ObjectifLigne[]>([nouvelObjectif()]);
  const [source, setSource] = useState<string>(SOURCES_IMPORT[0].id);
  const [fichier, setFichier] = useState<File | null>(null);
  const inputFichierRef = useRef<HTMLInputElement>(null);
  const [fichierJson, setFichierJson] = useState<File | null>(null);
  const inputJsonRef = useRef<HTMLInputElement>(null);
  const [erreurParseJson, setErreurParseJson] = useState<string | null>(null);
  const [fichierTachesCsv, setFichierTachesCsv] = useState<File | null>(null);
  const [fichierRessourcesCsv, setFichierRessourcesCsv] = useState<File | null>(null);
  const [fichierContraintesCsv, setFichierContraintesCsv] = useState<File | null>(null);
  const inputTachesCsvRef = useRef<HTMLInputElement>(null);
  const inputRessourcesCsvRef = useRef<HTMLInputElement>(null);
  const inputContraintesCsvRef = useRef<HTMLInputElement>(null);
  const [succes, setSucces] = useState<{ instance_id: string; structure_contraintes: string } | null>(null);

  function reinitialiser() {
    setClientId(utilisateur?.client_id ?? "");
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
    if (inputTachesCsvRef.current) inputTachesCsvRef.current.value = "";
    if (inputRessourcesCsvRef.current) inputRessourcesCsvRef.current.value = "";
    if (inputContraintesCsvRef.current) inputContraintesCsvRef.current.value = "";
    setSucces(null);
    ingerer.reset();
    importer.reset();
    importerFichier.reset();
    importerCsv.reset();
    importerJson.reset();
  }

  function fermer(open: boolean) {
    if (!open) reinitialiser();
    onOpenChange(open);
  }

  function onIngestionReussie(data: { instance_id: string; structure_contraintes: string }) {
    setSucces(data);
    queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
  }

  function soumettreTRCO() {
    const instance = construireInstance(taches, ressources, contraintes, objectifs);
    ingerer.mutate({ clientId, instance }, { onSuccess: onIngestionReussie });
  }

  function soumettreImport() {
    importer.mutate(source, { onSuccess: onIngestionReussie });
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
        },
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
    importerJson.mutate({ clientId, payload }, { onSuccess: onIngestionReussie });
  }

  const erreur = (ingerer.error ?? importer.error ?? importerFichier.error ?? importerCsv.error ?? importerJson.error) as
    | PrismeAPIError
    | null;
  const enCours =
    ingerer.isPending || importer.isPending || importerFichier.isPending || importerCsv.isPending || importerJson.isPending;

  return (
    <Dialog open={open} onOpenChange={fermer}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouvelle instance</DialogTitle>
          <DialogDescription>
            Ingérez une instance T-R-C-O directement, importez-la depuis un ERP connecté, ou depuis un fichier Excel,
            des fichiers CSV, ou un fichier JSON rempli.
          </DialogDescription>
        </DialogHeader>

        {succes ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-primary/40 bg-primary/10 p-4 text-sm">
              <div className="flex items-center gap-2 font-medium text-primary">
                <CheckCircle2 className="h-4 w-4" /> Instance ingérée
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">instance_id :</span>
                <Badge variant="secondary" className="font-mono">{succes.instance_id}</Badge>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <span className="text-muted-foreground">structure_contraintes :</span>
                <Badge variant="outline" className="font-mono">{succes.structure_contraintes}</Badge>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={reinitialiser}>Ingérer une autre instance</Button>
              <Button onClick={() => fermer(false)}>Fermer</Button>
            </DialogFooter>
          </div>
        ) : (
          <Tabs defaultValue="trco">
            <TabsList>
              <TabsTrigger value="trco">Saisie T-R-C-O</TabsTrigger>
              <TabsTrigger value="import">Import ERP</TabsTrigger>
              <TabsTrigger value="fichier">Fichier Excel</TabsTrigger>
              <TabsTrigger value="csv">Fichiers CSV</TabsTrigger>
              <TabsTrigger value="json">Fichier JSON</TabsTrigger>
            </TabsList>

            <TabsContent value="trco" className="space-y-5">
              <ChampClient clientId={clientId} setClientId={setClientId} estAdmin={estAdmin} idChamp="client_id" />

              <SectionTaches taches={taches} setTaches={setTaches} />
              <SectionRessources ressources={ressources} setRessources={setRessources} />
              <SectionContraintes
                contraintes={contraintes}
                setContraintes={setContraintes}
                taches={taches}
                ressources={ressources}
              />

              <SectionObjectifs objectifs={objectifs} setObjectifs={setObjectifs} />

              {erreur && ingerer.error && <ErreursAPI erreur={erreur} />}

              <DialogFooter>
                <Button variant="outline" onClick={() => fermer(false)}>Annuler</Button>
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
                      <SelectItem key={s.id} value={s.id}>{s.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  L'instance est lue directement depuis la source ERP côté serveur, sans saisie manuelle.
                </p>
              </div>

              {erreur && importer.error && <ErreursAPI erreur={erreur} />}

              <DialogFooter>
                <Button variant="outline" onClick={() => fermer(false)}>Annuler</Button>
                <Button onClick={soumettreImport} disabled={enCours}>
                  <Upload className="mr-2 h-4 w-4" />
                  {importer.isPending ? "Import..." : `Importer depuis ${SOURCES_IMPORT.find((s) => s.id === source)?.label}`}
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
                  Utilisez le gabarit fourni (onglets Tâches, Ressources, Précédences, Compatibilités) —
                  téléchargez-le via <code className="font-mono">docs/dsl/gabarit_ingestion_trco.xlsx</code>, remplissez-le,
                  puis déposez-le ici tel quel.
                </p>
              </div>

              {erreur && importerFichier.error && <ErreursAPI erreur={erreur} />}

              <DialogFooter>
                <Button variant="outline" onClick={() => fermer(false)}>Annuler</Button>
                <Button onClick={soumettreFichier} disabled={enCours || !fichier}>
                  <FileSpreadsheet className="mr-2 h-4 w-4" />
                  {importerFichier.isPending ? "Import..." : "Importer le fichier"}
                </Button>
              </DialogFooter>
            </TabsContent>

            <TabsContent value="csv" className="space-y-4">
              <ChampClient clientId={clientId} setClientId={setClientId} estAdmin={estAdmin} idChamp="client_id_csv" />

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
                  <code className="font-mono">id,nom,duree_estimee_jours</code> pour Tâches,{" "}
                  <code className="font-mono">id,nom,competences</code> (séparées par{" "}
                  <code className="font-mono">;</code>) pour Ressources,{" "}
                  <code className="font-mono">
                    type,tache_avant,tache_apres,tache,ressource,duree_jours,competence
                  </code>{" "}
                  pour Contraintes (<code className="font-mono">type</code> vaut{" "}
                  <code className="font-mono">precedence</code>,{" "}
                  <code className="font-mono">compatibilite_ressource_tache</code> ou{" "}
                  <code className="font-mono">competence_requise</code>).
                </p>
                <p className="text-xs text-muted-foreground">
                  Plutôt que de saisir chaque compatibilité à la main, déclarez qu'une ressource possède une
                  compétence et qu'une tâche l'exige (<code className="font-mono">competence_requise</code>) —
                  la compatibilité et sa durée (<code className="font-mono">duree_estimee_jours</code> de la
                  tâche) sont calculées automatiquement pour chaque ressource qualifiée.
                </p>
                <p className="text-xs">
                  Gabarits d'exemple :{" "}
                  {[
                    { nom: "taches.csv", href: "/gabarits/taches.csv" },
                    { nom: "ressources.csv", href: "/gabarits/ressources.csv" },
                    { nom: "contraintes.csv", href: "/gabarits/contraintes.csv" },
                  ].map((gabarit, i) => (
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

              {erreur && importerCsv.error && <ErreursAPI erreur={erreur} />}

              <DialogFooter>
                <Button variant="outline" onClick={() => fermer(false)}>Annuler</Button>
                <Button
                  onClick={soumettreCsv}
                  disabled={enCours || !fichierTachesCsv || !fichierRessourcesCsv || !fichierContraintesCsv}
                >
                  <Files className="mr-2 h-4 w-4" />
                  {importerCsv.isPending ? "Import..." : "Importer les fichiers"}
                </Button>
              </DialogFooter>
            </TabsContent>

            <TabsContent value="json" className="space-y-4">
              <ChampClient clientId={clientId} setClientId={setClientId} estAdmin={estAdmin} idChamp="client_id_json" />

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
                  Déposez un fichier JSON au format T-R-C-O (mêmes champs que la saisie manuelle : taches,
                  ressources, contraintes, objectifs) — ingéré tel quel si déjà complet. Plutôt que de
                  déclarer chaque compatibilité à la main, une tâche peut aussi porter une durée estimée
                  (<code className="font-mono">duree_estimee_jours</code>) : sa compatibilité avec toute
                  ressource dont les <code className="font-mono">competences</code> couvrent ses{" "}
                  <code className="font-mono">competence_requise</code> est alors calculée automatiquement.
                </p>
                <p className="text-xs">
                  Gabarit d'exemple :{" "}
                  <a
                    href="/gabarits/instance_exemple.json"
                    download
                    className="text-primary underline-offset-2 hover:underline"
                  >
                    instance_exemple.json
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
                <Button variant="outline" onClick={() => fermer(false)}>Annuler</Button>
                <Button onClick={soumettreJson} disabled={enCours || !fichierJson}>
                  <Braces className="mr-2 h-4 w-4" />
                  {importerJson.isPending ? "Import..." : "Importer le fichier"}
                </Button>
              </DialogFooter>
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
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
        <Button type="button" size="sm" variant="outline" onClick={() => setTaches((t) => [...t, nouvelleTache()])}>
          <Plus className="mr-1 h-3.5 w-3.5" /> Ajouter
        </Button>
      </div>
      <div className="space-y-2">
        {taches.map((t, i) => (
          <div key={t.clef} className="flex gap-2">
            <Input
              placeholder="id (ex: T1)"
              value={t.id}
              onChange={(e) =>
                setTaches((arr) => arr.map((x, j) => (j === i ? { ...x, id: e.target.value } : x)))
              }
              className="w-32 font-mono text-xs"
            />
            <Input
              placeholder="nom (optionnel)"
              value={t.nom ?? ""}
              onChange={(e) =>
                setTaches((arr) => arr.map((x, j) => (j === i ? { ...x, nom: e.target.value } : x)))
              }
            />
            <Input
              placeholder="priorité 1-5"
              type="number"
              min={1}
              max={5}
              value={t.priorite ?? ""}
              onChange={(e) =>
                setTaches((arr) =>
                  arr.map((x, j) => (j === i ? { ...x, priorite: Number(e.target.value) || undefined } : x))
                )
              }
              className="w-28"
            />
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
}: {
  ressources: RessourceLigne[];
  setRessources: React.Dispatch<React.SetStateAction<RessourceLigne[]>>;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Ressources</Label>
        <Button type="button" size="sm" variant="outline" onClick={() => setRessources((r) => [...r, nouvelleRessource()])}>
          <Plus className="mr-1 h-3.5 w-3.5" /> Ajouter
        </Button>
      </div>
      <div className="space-y-2">
        {ressources.map((r, i) => (
          <div key={r.clef} className="flex gap-2">
            <Input
              placeholder="id (ex: R1)"
              value={r.id}
              onChange={(e) =>
                setRessources((arr) => arr.map((x, j) => (j === i ? { ...x, id: e.target.value } : x)))
              }
              className="w-32 font-mono text-xs"
            />
            <Input
              placeholder="nom (optionnel)"
              value={r.nom ?? ""}
              onChange={(e) =>
                setRessources((arr) => arr.map((x, j) => (j === i ? { ...x, nom: e.target.value } : x)))
              }
            />
            <Input
              placeholder="compétences (séparées par des virgules)"
              value={r.competencesTexte}
              onChange={(e) =>
                setRessources((arr) =>
                  arr.map((x, j) => (j === i ? { ...x, competencesTexte: e.target.value } : x))
                )
              }
            />
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
}: {
  contraintes: ContrainteLigne[];
  setContraintes: React.Dispatch<React.SetStateAction<ContrainteLigne[]>>;
  taches: TacheLigne[];
  ressources: RessourceLigne[];
}) {
  function majLigne(i: number, patch: Partial<ContrainteLigne>) {
    setContraintes((arr) => arr.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Contraintes</Label>
        <Button type="button" size="sm" variant="outline" onClick={() => setContraintes((c) => [...c, nouvelleContrainte()])}>
          <Plus className="mr-1 h-3.5 w-3.5" /> Ajouter
        </Button>
      </div>
      <div className="space-y-2">
        {contraintes.map((c, i) => (
          <div key={c.clef} className="flex flex-wrap items-center gap-2 rounded-lg border border-border/50 p-2">
            <Select value={c.type} onValueChange={(v) => majLigne(i, { type: v as TypeContrainte })}>
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="precedence">Précédence</SelectItem>
                <SelectItem value="compatibilite_ressource_tache">Compatibilité ressource ↔ tâche</SelectItem>
                <SelectItem value="echeance">Échéance</SelectItem>
                <SelectItem value="competence_requise">Compétence requise</SelectItem>
              </SelectContent>
            </Select>

            {c.type === "precedence" && (
              <>
                <ChampSelectId placeholder="avant" value={c.avant} options={taches} onChange={(v) => majLigne(i, { avant: v })} />
                <ChampSelectId placeholder="après" value={c.apres} options={taches} onChange={(v) => majLigne(i, { apres: v })} />
              </>
            )}
            {c.type === "compatibilite_ressource_tache" && (
              <>
                <ChampSelectId placeholder="tâche" value={c.tache} options={taches} onChange={(v) => majLigne(i, { tache: v })} />
                <ChampSelectId placeholder="ressource" value={c.ressource} options={ressources} onChange={(v) => majLigne(i, { ressource: v })} />
                <Input
                  placeholder="durée (jours)"
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
                <ChampSelectId placeholder="tâche" value={c.tache} options={taches} onChange={(v) => majLigne(i, { tache: v })} />
                <Input
                  placeholder="échéance"
                  type="number"
                  min={0}
                  value={c.echeance}
                  onChange={(e) => majLigne(i, { echeance: e.target.value })}
                  className="w-32"
                />
              </>
            )}
            {c.type === "competence_requise" && (
              <>
                <ChampSelectId placeholder="tâche" value={c.tache} options={taches} onChange={(v) => majLigne(i, { tache: v })} />
                <Input
                  placeholder="compétence"
                  value={c.competence}
                  onChange={(e) => majLigne(i, { competence: e.target.value })}
                  className="w-40"
                />
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
            Aucune contrainte — chaque tâche doit avoir au moins une compatibilité ressource-tâche pour être ingérée.
          </p>
        )}
      </div>
    </div>
  );
}

// Inverse de construireObjectifs — pour préremplir le formulaire d'édition
// à partir des objectifs déjà stockés d'une instance existante.
export function objectifVersLigne(o: Objectif): ObjectifLigne {
  const base = nouvelObjectif();
  const ligne: ObjectifLigne = { ...base, clef: idLocal(), type: o.type, poids: o.poids?.toString() ?? "1" };
  switch (o.type) {
    case "minimiser_makespan":
      return { ...ligne, makespanCible: o.makespan_cible?.toString() ?? "" };
    case "equilibrer_charge":
      return { ...ligne, methode: o.methode ?? "ecart_max", ressourcesCibles: o.ressources_cibles?.join(", ") ?? "" };
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
}: {
  objectifs: ObjectifLigne[];
  setObjectifs: React.Dispatch<React.SetStateAction<ObjectifLigne[]>>;
}) {
  function majLigne(i: number, patch: Partial<ObjectifLigne>) {
    setObjectifs((arr) => arr.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <Label>Objectifs</Label>
        <Button type="button" size="sm" variant="outline" onClick={() => setObjectifs((o) => [...o, nouvelObjectif()])}>
          <Plus className="mr-1 h-3.5 w-3.5" /> Ajouter
        </Button>
      </div>
      <div className="space-y-2">
        {objectifs.map((o, i) => (
          <div key={o.clef} className="flex flex-wrap items-center gap-2 rounded-lg border border-border/50 p-2">
            <Select value={o.type} onValueChange={(v) => majLigne(i, { type: v as TypeObjectif })}>
              <SelectTrigger className="w-56">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(LABELS_OBJECTIF) as TypeObjectif[]).map((t) => (
                  <SelectItem key={t} value={t}>{LABELS_OBJECTIF[t]}</SelectItem>
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

            {o.type === "minimiser_makespan" && (
              <Input
                placeholder="makespan cible (min, optionnel)"
                type="number"
                min={0}
                value={o.makespanCible}
                onChange={(e) => majLigne(i, { makespanCible: e.target.value })}
                className="w-56"
              />
            )}
            {o.type === "equilibrer_charge" && (
              <>
                <Select value={o.methode} onValueChange={(v) => majLigne(i, { methode: v as ObjectifLigne["methode"] })}>
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
                  onValueChange={(v) => majLigne(i, { fonctionPenalite: v as ObjectifLigne["fonctionPenalite"] })}
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
                  placeholder="seuil de grâce (jours)"
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
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Plusieurs objectifs sont combinés selon leur poids relatif (ex. 0.7 équilibrage + 0.3 makespan).
        Les listes "ressources" acceptent des ids séparés par des virgules ; laissez vide pour "toutes".
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
            <SelectItem key={o.id} value={o.id}>{o.id}</SelectItem>
          ))}
      </SelectContent>
    </Select>
  );
}

import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Upload, FileJson, FileSpreadsheet, CheckCircle2, AlertCircle } from "lucide-react";

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
  PrismeAPIError,
  type Contrainte,
  type InstanceTRCO,
  type Ressource,
  type Tache,
  type TypeContrainte,
} from "@/integrations/prisme";

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

function construireInstance(taches: TacheLigne[], ressources: RessourceLigne[], contraintes: ContrainteLigne[]): InstanceTRCO {
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
    objectifs: [{ type: "minimiser_makespan" }],
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

  const [clientId, setClientId] = useState("client-001");
  const [taches, setTaches] = useState<TacheLigne[]>([nouvelleTache()]);
  const [ressources, setRessources] = useState<RessourceLigne[]>([nouvelleRessource()]);
  const [contraintes, setContraintes] = useState<ContrainteLigne[]>([]);
  const [source, setSource] = useState<string>(SOURCES_IMPORT[0].id);
  const [fichier, setFichier] = useState<File | null>(null);
  const inputFichierRef = useRef<HTMLInputElement>(null);
  const [succes, setSucces] = useState<{ instance_id: string; structure_contraintes: string } | null>(null);

  function reinitialiser() {
    setClientId("client-001");
    setTaches([nouvelleTache()]);
    setRessources([nouvelleRessource()]);
    setContraintes([]);
    setFichier(null);
    if (inputFichierRef.current) inputFichierRef.current.value = "";
    setSucces(null);
    ingerer.reset();
    importer.reset();
    importerFichier.reset();
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
    const instance = construireInstance(taches, ressources, contraintes);
    ingerer.mutate({ clientId, instance }, { onSuccess: onIngestionReussie });
  }

  function soumettreImport() {
    importer.mutate(source, { onSuccess: onIngestionReussie });
  }

  function soumettreFichier() {
    if (!fichier) return;
    importerFichier.mutate({ clientId, fichier }, { onSuccess: onIngestionReussie });
  }

  const erreur = (ingerer.error ?? importer.error ?? importerFichier.error) as PrismeAPIError | null;
  const enCours = ingerer.isPending || importer.isPending || importerFichier.isPending;

  return (
    <Dialog open={open} onOpenChange={fermer}>
      <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Nouvelle instance</DialogTitle>
          <DialogDescription>
            Ingérez une instance T-R-C-O directement, importez-la depuis un ERP connecté, ou depuis un fichier Excel rempli.
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
            </TabsList>

            <TabsContent value="trco" className="space-y-5">
              <div className="space-y-1.5">
                <Label htmlFor="client_id">Client</Label>
                <Input id="client_id" value={clientId} onChange={(e) => setClientId(e.target.value)} />
              </div>

              <SectionTaches taches={taches} setTaches={setTaches} />
              <SectionRessources ressources={ressources} setRessources={setRessources} />
              <SectionContraintes
                contraintes={contraintes}
                setContraintes={setContraintes}
                taches={taches}
                ressources={ressources}
              />

              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <span>Objectif :</span>
                <Badge variant="secondary">Minimiser le makespan</Badge>
              </div>

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
              <div className="space-y-1.5">
                <Label htmlFor="client_id_fichier">Client</Label>
                <Input id="client_id_fichier" value={clientId} onChange={(e) => setClientId(e.target.value)} />
              </div>

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
                  placeholder="durée (min)"
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

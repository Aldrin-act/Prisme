import { Plus, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Ressource } from "@/integrations/prisme";
import type { DonneesNoeudEdition } from "./flow-graph-editor";

// Panneau d'inspection d'une tâche sélectionnée — une simple `<div>` ancrée,
// pas un `Sheet`/`Dialog` Radix : ce composant vit à l'intérieur du `Dialog`
// « Détail de l'instance » (instances.tsx), et `Sheet` n'est qu'un
// `@radix-ui/react-dialog` sous un autre nom (components/ui/sheet.tsx) — deux
// `Dialog.Root` imbriqués posent les mêmes soucis (aria-hidden, fermeture en
// cascade) qu'un `Dialog` dans un `Dialog`.
export function InspecteurTache({
  donnees,
  ressourcesDisponibles,
  idInvalide,
  onPatch,
  onSupprimer,
  onFermer,
}: {
  donnees: DonneesNoeudEdition;
  ressourcesDisponibles: Ressource[];
  /** Message d'erreur sur l'id (motif/unicité), ou `null` si valide. */
  idInvalide: string | null;
  onPatch: (patch: Partial<DonneesNoeudEdition>) => void;
  onSupprimer: () => void;
  onFermer: () => void;
}) {
  function majCompat(i: number, patch: Partial<DonneesNoeudEdition["compatibilites"][number]>) {
    onPatch({
      compatibilites: donnees.compatibilites.map((c, j) => (j === i ? { ...c, ...patch } : c)),
    });
  }

  return (
    <div className="flex w-full shrink-0 flex-col gap-3 overflow-y-auto rounded-lg border border-border bg-card p-3 sm:w-80">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-semibold">Tâche</Label>
        <Button type="button" size="icon" variant="ghost" className="h-7 w-7" onClick={onFermer}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="space-y-1">
        <Label>Id</Label>
        <Input
          value={donnees.dslId}
          disabled={!donnees.estNouveau}
          placeholder="ex: T1"
          className="font-mono text-xs"
          onChange={(e) => onPatch({ dslId: e.target.value })}
        />
        {idInvalide && <p className="text-xs text-destructive">{idInvalide}</p>}
      </div>

      <div className="space-y-1">
        <Label>Nom</Label>
        <Input
          value={donnees.nom ?? ""}
          placeholder="optionnel"
          onChange={(e) => onPatch({ nom: e.target.value || undefined })}
        />
      </div>

      <div className="space-y-1">
        <Label>Produit</Label>
        <Input
          value={donnees.produit ?? ""}
          placeholder="optionnel — regroupement visuel"
          onChange={(e) => onPatch({ produit: e.target.value || undefined })}
        />
      </div>

      <div className="space-y-1">
        <Label>Priorité (1-5)</Label>
        <Input
          type="number"
          min={1}
          max={5}
          value={donnees.priorite ?? ""}
          onChange={(e) => onPatch({ priorite: Number(e.target.value) || undefined })}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Ressources compatibles</Label>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() =>
              onPatch({
                compatibilites: [
                  ...donnees.compatibilites,
                  { clef: crypto.randomUUID(), ressource: "", duree: "" },
                ],
              })
            }
          >
            <Plus className="mr-1 h-3.5 w-3.5" /> Ajouter
          </Button>
        </div>
        {donnees.compatibilites.length === 0 && (
          <p className="text-xs text-muted-foreground">
            Aucune ressource compatible — au moins une est requise pour enregistrer.
          </p>
        )}
        {donnees.compatibilites.map((c, i) => (
          <div key={c.clef} className="flex items-center gap-1.5">
            <Select value={c.ressource} onValueChange={(v) => majCompat(i, { ressource: v })}>
              <SelectTrigger className="h-8 flex-1 text-xs">
                <SelectValue placeholder="ressource" />
              </SelectTrigger>
              <SelectContent>
                {ressourcesDisponibles.map((r) => (
                  <SelectItem key={r.id} value={r.id}>
                    {r.id}
                    {r.nom ? ` — ${r.nom}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input
              type="number"
              min={1}
              placeholder="jours"
              value={c.duree}
              onChange={(e) => majCompat(i, { duree: e.target.value })}
              className="h-8 w-20 text-xs"
            />
            <Button
              type="button"
              size="icon"
              variant="ghost"
              className="h-8 w-8 flex-shrink-0"
              onClick={() =>
                onPatch({ compatibilites: donnees.compatibilites.filter((_, j) => j !== i) })
              }
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>
        ))}
      </div>

      <Button
        type="button"
        variant="destructive"
        size="sm"
        onClick={onSupprimer}
        className="mt-auto"
      >
        <Trash2 className="mr-1.5 h-3.5 w-3.5" /> Supprimer cette tâche
      </Button>
    </div>
  );
}

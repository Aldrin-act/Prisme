import { Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DonneesNoeudEtape } from "./gamme-editor";

// Panneau d'inspection d'une étape sélectionnée — même choix de "div ancrée"
// que inspecteur-tache.tsx (voir sa docstring pour la justification : éviter
// deux Dialog/Sheet Radix imbriqués).
export function InspecteurEtapeGamme({
  donnees,
  idInvalide,
  onPatch,
  onSupprimer,
  onFermer,
}: {
  donnees: DonneesNoeudEtape;
  /** Message d'erreur sur l'id (motif/unicité), ou `null` si valide. */
  idInvalide: string | null;
  onPatch: (patch: Partial<DonneesNoeudEtape>) => void;
  onSupprimer: () => void;
  onFermer: () => void;
}) {
  return (
    <div className="flex w-80 flex-shrink-0 flex-col gap-3 overflow-y-auto rounded-lg border border-border bg-card p-3">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-semibold">Étape</Label>
        <Button type="button" size="icon" variant="ghost" className="h-7 w-7" onClick={onFermer}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="space-y-1">
        <Label>Id</Label>
        <Input
          value={donnees.id}
          placeholder="ex: soudure"
          className="font-mono text-xs"
          onChange={(e) => onPatch({ id: e.target.value })}
        />
        {idInvalide && <p className="text-xs text-destructive">{idInvalide}</p>}
      </div>

      <div className="space-y-1">
        <Label>Compétences requises</Label>
        <Input
          value={donnees.competencesTexte}
          placeholder="ex: soudure, controle_qualite"
          onChange={(e) => onPatch({ competencesTexte: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          Séparées par des virgules — au moins une requise pour enregistrer.
        </p>
      </div>

      <div className="space-y-1">
        <Label>Durée nominale (jours)</Label>
        <Input
          type="number"
          min={1}
          value={donnees.dureeNominale}
          placeholder="optionnel si un estimateur ML est configuré"
          onChange={(e) => onPatch({ dureeNominale: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          Sans elle, une compétence non couverte par une estimation ML fera échouer l'explosion de
          la commande.
        </p>
      </div>

      <Button
        type="button"
        variant="destructive"
        size="sm"
        onClick={onSupprimer}
        className="mt-auto"
      >
        <Trash2 className="mr-1.5 h-3.5 w-3.5" /> Supprimer cette étape
      </Button>
    </div>
  );
}

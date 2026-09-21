import { Plus, Trash2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { DonneesNoeudEtape } from "./editeur-processus";
import { competencesDe, idDepuisNom } from "./processus-utils";

// Panneau d'inspection d'une étape sélectionnée — même choix de "div ancrée"
// que inspecteur-tache.tsx (voir sa docstring pour la justification : éviter
// deux Dialog/Sheet Radix imbriqués).
export function InspecteurEtapeProcessus({
  donnees,
  erreur,
  uniteTemps,
  competencesAtelier,
  onPatch,
  onSupprimer,
  onFermer,
}: {
  donnees: DonneesNoeudEtape;
  /** Défaut bloquant l'enregistrement pour cette étape, ou `null`. */
  erreur: string | null;
  uniteTemps: "jours" | "heures";
  /** Compétences que possède au moins une ressource de l'atelier — proposées en un clic. */
  competencesAtelier: string[];
  onPatch: (patch: Partial<DonneesNoeudEtape>) => void;
  onSupprimer: () => void;
  onFermer: () => void;
}) {
  const competences = competencesDe(donnees.competencesTexte);
  const proposables = competencesAtelier.filter((c) => !competences.includes(c));

  function changerNom(nom: string) {
    // L'id suit le nom tant que l'utilisateur ne l'a pas modifié lui-même.
    const idSuitLeNom = donnees.id === "" || donnees.id === idDepuisNom(donnees.nom);
    onPatch(idSuitLeNom ? { nom, id: idDepuisNom(nom) } : { nom });
  }

  function ajouterCompetence(competence: string) {
    onPatch({ competencesTexte: [...competences, competence].join(", ") });
  }

  return (
    <div className="flex w-80 shrink-0 flex-col gap-3 overflow-y-auto rounded-lg border border-border bg-card p-3">
      <div className="flex items-center justify-between">
        <Label className="text-sm font-semibold">Étape</Label>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={onFermer}
          aria-label="Fermer"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="space-y-1">
        <Label htmlFor="etape-nom">Nom</Label>
        <Input
          id="etape-nom"
          value={donnees.nom}
          placeholder="ex : Tournage"
          onChange={(e) => changerNom(e.target.value)}
        />
      </div>

      <div className="space-y-1">
        <Label htmlFor="etape-id">Code</Label>
        <Input
          id="etape-id"
          value={donnees.id}
          placeholder="ex : TOURNAGE"
          className="font-mono text-xs"
          onChange={(e) => onPatch({ id: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          Rempli depuis le nom. Lettres, chiffres, « _ » et « - » uniquement.
        </p>
      </div>

      <div className="space-y-1">
        <Label htmlFor="etape-competences">Compétences requises</Label>
        <Input
          id="etape-competences"
          value={donnees.competencesTexte}
          placeholder="ex : REGLAGE_TOUR_CN"
          onChange={(e) => onPatch({ competencesTexte: e.target.value })}
        />
        {proposables.length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1">
            {proposables.map((c) => (
              <button key={c} type="button" onClick={() => ajouterCompetence(c)}>
                <Badge variant="outline" className="cursor-pointer gap-1 font-mono text-[10px]">
                  <Plus className="h-2.5 w-2.5" /> {c}
                </Badge>
              </button>
            ))}
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          Compétences de l'atelier en un clic. Une étape qu'aucune ressource ne sait faire sera
          ignorée dans les commandes, avec un avertissement.
        </p>
      </div>

      <div className="space-y-1">
        <Label htmlFor="etape-duree">Durée par pièce ({uniteTemps})</Label>
        <Input
          id="etape-duree"
          type="number"
          min={1}
          step={1}
          value={donnees.dureeParPiece}
          placeholder="ex : 2"
          onChange={(e) => onPatch({ dureeParPiece: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          Multipliée par la quantité de chaque commande.
        </p>
      </div>

      {erreur && <p className="text-xs text-destructive">{erreur}</p>}

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

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Check, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  prismeKeys,
  useAjouterProduitACommande,
  useGammes,
  PrismeAPIError,
  type StatutCommande,
} from "@/integrations/prisme";

/**
 * Action compacte par ligne (page Commandes) pour ajouter un produit (gamme) supplémentaire à une
 * commande déjà créée — complète `FormulaireNouvelleCommande`, qui ne permet de référencer des
 * gammes qu'à la création. Popover plutôt qu'un dialogue plein écran : une seule gamme + une
 * quantité à la fois, pas besoin de plus.
 */
export function AjouterProduitCommande({ commande }: { commande: StatutCommande }) {
  const queryClient = useQueryClient();
  const ajouter = useAjouterProduitACommande();
  const { data: gammes } = useGammes();
  const [ouvert, setOuvert] = useState(false);
  const [gammeId, setGammeId] = useState("");
  const [quantite, setQuantite] = useState("");

  // Un admin voit les gammes de tous les clients (useGammes non filtré côté backend pour lui) —
  // ne proposer que celles du client de cette commande, le backend refuserait les autres (400).
  const gammesDisponibles = (gammes ?? []).filter((g) => g.client_id === commande.client_id);
  const erreur = ajouter.error as PrismeAPIError | null;

  function ouvrir(v: boolean) {
    setOuvert(v);
    if (v) {
      setGammeId("");
      setQuantite("");
      ajouter.reset();
    }
  }

  function soumettre() {
    if (!gammeId) return;
    ajouter.mutate(
      {
        commandeId: commande.commande_id,
        requete: { gamme_id: gammeId, quantite: quantite !== "" ? Number(quantite) : undefined },
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: prismeKeys.commandes() });
          queryClient.invalidateQueries({
            queryKey: prismeKeys.commandesInstance(commande.instance_id),
          });
          queryClient.invalidateQueries({ queryKey: prismeKeys.instance(commande.instance_id) });
          queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
          queryClient.invalidateQueries({ queryKey: prismeKeys.executions() });
          setOuvert(false);
        },
      },
    );
  }

  if (gammesDisponibles.length === 0) return null;

  return (
    <Popover open={ouvert} onOpenChange={ouvrir}>
      <PopoverTrigger asChild>
        <Button size="icon" variant="ghost" className="h-7 w-7" title="Ajouter un produit">
          <Plus className="h-3.5 w-3.5" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 space-y-3">
        <div className="space-y-1">
          <Label className="text-xs">Produit (gamme)</Label>
          <Select value={gammeId} onValueChange={setGammeId}>
            <SelectTrigger>
              <SelectValue placeholder="Choisir un produit..." />
            </SelectTrigger>
            <SelectContent>
              {gammesDisponibles.map((g) => (
                <SelectItem key={g.gamme_id} value={g.gamme_id}>
                  {g.produit}
                  {g.nom ? ` — ${g.nom}` : ""}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Quantité</Label>
          <Input
            type="number"
            min={1}
            placeholder="Optionnel"
            value={quantite}
            onChange={(e) => setQuantite(e.target.value)}
          />
        </div>
        {erreur && <p className="text-xs text-destructive">{erreur.message}</p>}
        <Button
          size="sm"
          className="w-full"
          onClick={soumettre}
          disabled={!gammeId || ajouter.isPending}
        >
          <Check className="mr-1.5 h-3.5 w-3.5" />
          {ajouter.isPending ? "Ajout..." : "Ajouter à la commande"}
        </Button>
      </PopoverContent>
    </Popover>
  );
}

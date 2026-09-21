import { AlertTriangle } from "lucide-react";
import type { EtapeProcessus } from "@/integrations/prisme";
import { enchainementsDistincts } from "./processus-utils";

/** Avertit quand les étapes forment plusieurs enchaînements sans lien entre eux — un atelier n'a
 * qu'un seul processus. Ne s'affiche pas (et ne bloque rien) quand il n'y en a qu'un. */
export function AvertissementEnchainements({ etapes }: { etapes: EtapeProcessus[] }) {
  const groupes = enchainementsDistincts(etapes);
  if (groupes.length <= 1) return null;
  return (
    <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-xs">
      <div className="flex items-center gap-2 font-medium text-amber-600">
        <AlertTriangle className="h-4 w-4" />
        {groupes.length} enchaînements distincts détectés — un atelier n'a qu'un seul processus
      </div>
      <ul className="mt-1.5 list-disc space-y-0.5 pl-5 text-muted-foreground">
        {groupes.map((g) => (
          <li key={g[0].id}>{g.map((e) => e.nom ?? e.id).join(" → ")}</li>
        ))}
      </ul>
      <p className="mt-1.5 text-muted-foreground">
        Ces étapes n'ont aucune précédence entre les groupes : vérifiez qu'il manque bien un lien,
        ou que ce ne sont pas deux ateliers différents.
      </p>
    </div>
  );
}

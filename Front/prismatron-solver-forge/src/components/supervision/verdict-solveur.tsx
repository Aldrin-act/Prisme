import { AlertTriangle, CheckCircle2, MinusCircle, XCircle, type LucideIcon } from "lucide-react";
import type {
  ConstatSolveur,
  EvaluationSolveurSupervision,
  VerdictConstatSolveur,
} from "@/integrations/prisme";

// Partagé entre la page /supervision (analyse d'un atelier choisi à la main) et le formulaire
// « Créer un scénario » (verdict demandé juste après l'échec « aucun solveur validé ») — même
// composant, jamais dupliqué : voir `supervision/adequation.py::evaluer_solveur` côté serveur.

const PRESENTATION_VERDICT: Record<
  VerdictConstatSolveur,
  { label: string; icone: LucideIcon; couleur: string }
> = {
  bloquant: { label: "Bloquant", icone: XCircle, couleur: "text-destructive" },
  a_surveiller: { label: "À surveiller", icone: AlertTriangle, couleur: "text-amber-500" },
  sans_impact: { label: "Sans impact", icone: CheckCircle2, couleur: "text-emerald-500" },
  non_verifie: { label: "Non vérifié", icone: MinusCircle, couleur: "text-muted-foreground" },
};

// Ordre d'affichage : ce qui justifie (ou non) la régénération d'abord.
const ORDRE_VERDICT: Record<VerdictConstatSolveur, number> = {
  bloquant: 0,
  a_surveiller: 1,
  non_verifie: 2,
  sans_impact: 3,
};

function LigneConstat({ constat }: { constat: ConstatSolveur }) {
  const { label, icone: Icone, couleur } = PRESENTATION_VERDICT[constat.verdict];
  return (
    <li className="flex gap-2">
      <Icone className={`mt-0.5 h-4 w-4 shrink-0 ${couleur}`} />
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 text-sm font-medium">
          {constat.sujet}
          <span className={`text-xs font-normal ${couleur}`}>{label}</span>
        </div>
        <div className="text-xs text-muted-foreground">{constat.argument}</div>
        {constat.preuves.length > 0 && (
          <ul className="mt-1 space-y-0.5 border-l border-border/60 pl-2">
            {constat.preuves.map((preuve, i) => (
              <li key={i} className="text-xs text-muted-foreground">
                {preuve}
              </li>
            ))}
          </ul>
        )}
      </div>
    </li>
  );
}

/**
 * Verdict « faut-il régénérer ce solveur ? » — un constat argumenté par changement (essai réel,
 * lecture du code, Benchmarker : `supervision/adequation.py`). Seul un constat bloquant recommande
 * de régénérer ; la décision reste humaine. Ne dit jamais « modifie juste le code » — PRISME n'a
 * aucun mécanisme de correctif ciblé, une régénération est toujours le pipeline complet
 * (analyste → benchmarker → architecte → développeur → testeur → boucle de réparation), jamais une
 * édition manuelle d'une partie du code figé.
 */
export function VerdictSolveur({
  evaluation,
  indiceRegeneration,
}: {
  evaluation: EvaluationSolveurSupervision;
  // Ce qu'il reste à faire si une régénération est recommandée — dépend d'où ce verdict est
  // affiché (page Supervision : lancer une analyse d'atelier ; formulaire de scénario : le bouton
  // "Générer un solveur" juste à côté). Par défaut, rappelle qu'aucun correctif ciblé n'existe.
  indiceRegeneration?: string;
}) {
  const constats = [...evaluation.constats].sort(
    (a, b) => ORDRE_VERDICT[a.verdict] - ORDRE_VERDICT[b.verdict],
  );
  const nbBloquants = constats.filter((c) => c.verdict === "bloquant").length;
  return (
    <div
      className={`rounded-xl border p-4 ${
        evaluation.a_regenerer
          ? "border-destructive/40 bg-destructive/5"
          : "border-emerald-500/40 bg-emerald-500/5"
      }`}
    >
      <div className="mb-1 flex items-center gap-2 font-semibold">
        {evaluation.a_regenerer ? (
          <>
            <AlertTriangle className="h-4 w-4 text-destructive" /> Régénération recommandée
          </>
        ) : (
          <>
            <CheckCircle2 className="h-4 w-4 text-emerald-500" /> Pas de raison de régénérer ce
            solveur
          </>
        )}
      </div>
      <p className="mb-3 text-xs text-muted-foreground">
        {evaluation.a_regenerer
          ? `${nbBloquants} argument(s) bloquant(s) montrent que le solveur ne répond plus à cet atelier.`
          : "Aucun argument ne montre que le solveur ne répond plus à cet atelier."}
        {evaluation.essai &&
          (evaluation.essai.erreur
            ? " Essai réel sur l'instance actuelle : en échec."
            : ` Essai réel sur l'instance actuelle : ${evaluation.essai.nb_violations} violation(s).`)}
      </p>
      <ul className="space-y-3">
        {constats.map((constat, i) => (
          <LigneConstat key={i} constat={constat} />
        ))}
      </ul>
      {evaluation.a_regenerer && (
        <p className="mt-3 text-xs text-muted-foreground">
          {indiceRegeneration ??
            "Aucun correctif ciblé n'existe dans PRISME — la seule voie est une régénération " +
              "complète (nouvel appel aux agents, jamais une édition manuelle du code figé)."}
        </p>
      )}
    </div>
  );
}

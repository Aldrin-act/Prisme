import { AlertTriangle, Brain, Hourglass, Scissors, Timer } from "lucide-react";
import type { CauseLatence, MesureAppelLLM } from "@/integrations/prisme";

// Affichage des mesures d'appels au modèle (évènements `statut: "mesure"`, voir
// generation/agents/client_llm.py::MesureAppelLLM) : combien de temps chaque agent a passé à
// attendre le modèle, et surtout pourquoi — réflexion, attente d'une place sur un compte limité
// à une requête simultanée, ou refus du fournisseur.

const FORMAT_NOMBRE = new Intl.NumberFormat("fr-FR");

function formaterDuree(secondes: number): string {
  if (secondes < 1) return "moins d'1 s";
  if (secondes < 60) return `${Math.round(secondes)} s`;
  const minutes = Math.floor(secondes / 60);
  if (minutes < 60) return `${minutes} min ${String(Math.round(secondes % 60)).padStart(2, "0")} s`;
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, "0")} min`;
}

function partReflexion(m: MesureAppelLLM): number | null {
  if (!m.tokens_sortie || m.tokens_reflexion == null) return null;
  return m.tokens_reflexion / m.tokens_sortie;
}

function pourcentage(part: number): string {
  return `${Math.round(part * 100)} %`;
}

function explicationCause(m: MesureAppelLLM): string | null {
  switch (m.cause) {
    case "reflexion": {
      const part = partReflexion(m);
      return (
        `Surtout de la réflexion : ${part === null ? "l'essentiel" : pourcentage(part)} des tokens ` +
        "produits l'ont été avant la réponse, pendant la phase de réflexion du modèle."
      );
    }
    case "attente":
      return (
        `Surtout de l'attente : ${formaterDuree(m.attente_file_s)} à attendre qu'une place se libère ` +
        "— le compte n'accepte qu'un nombre limité de requêtes simultanées."
      );
    case "refus":
      return m.reussi
        ? `Ralenti par ${m.refus_429} refus du fournisseur (429), rattrapés par de nouvelles tentatives.`
        : `Refusé par le fournisseur (429) à chacune des ${m.tentatives} tentatives : sa seule place était occupée.`;
    case "longueur": {
      const part = partReflexion(m);
      const budget =
        m.tokens_sortie != null ? `${FORMAT_NOMBRE.format(m.tokens_sortie)} tokens` : "son budget";
      return (
        `Réponse coupée : le modèle a épuisé ${budget} de sortie avant d’avoir fini` +
        (part !== null && part >= 0.5 ? `, dont ${pourcentage(part)} passés à réfléchir.` : ".") +
        " Couper la réflexion de cet agent règle le problème."
      );
    }
    default:
      return null;
  }
}

const STYLE_CAUSE: Record<Exclude<CauseLatence, null>, string> = {
  reflexion: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  attente: "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  refus: "border-destructive/40 bg-destructive/10 text-destructive",
  longueur: "border-destructive/40 bg-destructive/10 text-destructive",
};

function IconeCause({ cause }: { cause: Exclude<CauseLatence, null> }) {
  const classe = "mt-0.5 h-3.5 w-3.5 shrink-0";
  if (cause === "reflexion") return <Brain className={classe} />;
  if (cause === "attente") return <Hourglass className={classe} />;
  if (cause === "longueur") return <Scissors className={classe} />;
  return <AlertTriangle className={classe} />;
}

function LigneMesure({ mesure }: { mesure: MesureAppelLLM }) {
  const part = partReflexion(mesure);
  const explication = explicationCause(mesure);
  return (
    <li className="space-y-1">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[11px] text-muted-foreground">
        <Timer className="h-3 w-3 shrink-0" aria-hidden />
        <span className="font-semibold text-foreground">{formaterDuree(mesure.duree_s)}</span>
        {mesure.attente_file_s >= 1 && (
          <span>dont {formaterDuree(mesure.attente_file_s)} d'attente</span>
        )}
        {mesure.tokens_entree != null && mesure.tokens_sortie != null && (
          <span>
            {FORMAT_NOMBRE.format(mesure.tokens_entree)} →{" "}
            {FORMAT_NOMBRE.format(mesure.tokens_sortie)} tokens
          </span>
        )}
        {part !== null && part >= 0.05 && <span>{pourcentage(part)} de réflexion</span>}
        {mesure.refus_429 > 0 && (
          <span className="text-destructive">{mesure.refus_429} refus 429</span>
        )}
        {mesure.reponse_conforme === false && (
          <span className="text-amber-700 dark:text-amber-400">réponse hors format, relancée</span>
        )}
        {mesure.modele && <span className="ml-auto">{mesure.modele}</span>}
      </div>
      {mesure.cause && explication && (
        <div
          className={`flex items-start gap-1.5 rounded-md border px-2 py-1 text-[11px] ${STYLE_CAUSE[mesure.cause]}`}
        >
          <IconeCause cause={mesure.cause} />
          <span>{explication}</span>
        </div>
      )}
    </li>
  );
}

// Les appels au modèle faits par un agent, sous sa ligne dans la chronologie.
export function MesuresAgent({ mesures }: { mesures: MesureAppelLLM[] }) {
  if (mesures.length === 0) return null;
  const total = mesures.reduce((s, m) => s + m.duree_s, 0);
  return (
    <div className="mt-2 space-y-1.5 border-l-2 border-border/60 pl-3">
      {mesures.length > 1 && (
        <div className="text-[11px] text-muted-foreground">
          {mesures.length} appels au modèle · {formaterDuree(total)} au total
        </div>
      )}
      <ul className="space-y-1.5">
        {mesures.map((m, i) => (
          <LigneMesure key={i} mesure={m} />
        ))}
      </ul>
    </div>
  );
}

const LIBELLE_CAUSE: Record<Exclude<CauseLatence, null>, string> = {
  reflexion: "la réflexion du modèle",
  attente: "l'attente d'une place chez le fournisseur",
  refus: "les refus du fournisseur (429)",
  longueur: "des réponses coupées à la limite de tokens de sortie",
};

// Bilan de toute la génération : où est passé le temps, et quelle cause domine.
export function BilanLatence({ mesures }: { mesures: MesureAppelLLM[] }) {
  if (mesures.length === 0) return null;
  const total = mesures.reduce((s, m) => s + m.duree_s, 0);
  const attente = mesures.reduce((s, m) => s + m.attente_file_s, 0);
  const sortie = mesures.reduce((s, m) => s + (m.tokens_sortie ?? 0), 0);
  const reflexion = mesures.reduce((s, m) => s + (m.tokens_reflexion ?? 0), 0);
  const refus = mesures.reduce((s, m) => s + m.refus_429, 0);

  const dureeParCause = new Map<Exclude<CauseLatence, null>, number>();
  for (const m of mesures) {
    if (m.cause) dureeParCause.set(m.cause, (dureeParCause.get(m.cause) ?? 0) + m.duree_s);
  }
  const [causePrincipale, dureeCause] = [...dureeParCause.entries()].sort(
    (a, b) => b[1] - a[1],
  )[0] ?? [null, 0];
  const causeMarquante = causePrincipale !== null && total > 0 && dureeCause / total >= 0.3;

  return (
    <div className="mb-3 space-y-2 rounded-lg border border-border/50 p-3 text-xs">
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-muted-foreground">
        <span>
          <span className="font-semibold text-foreground">{mesures.length}</span> appels au modèle
        </span>
        <span>
          <span className="font-semibold text-foreground">{formaterDuree(total)}</span> passées à
          attendre ses réponses
        </span>
        {attente >= 1 && <span>dont {formaterDuree(attente)} d'attente d'une place</span>}
        {sortie > 0 && (
          <span>
            {FORMAT_NOMBRE.format(sortie)} tokens produits
            {reflexion > 0 && `, dont ${pourcentage(reflexion / sortie)} de réflexion`}
          </span>
        )}
        {refus > 0 && <span className="text-destructive">{refus} refus 429</span>}
      </div>
      {causeMarquante && causePrincipale && (
        <div
          className={`flex items-start gap-1.5 rounded-md border px-2 py-1.5 ${STYLE_CAUSE[causePrincipale]}`}
        >
          <IconeCause cause={causePrincipale} />
          <span>
            Latence due surtout à {LIBELLE_CAUSE[causePrincipale]} : {formaterDuree(dureeCause)} sur{" "}
            {formaterDuree(total)} passées dans les appels au modèle.
          </span>
        </div>
      )}
    </div>
  );
}

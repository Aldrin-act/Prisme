import { useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Clock,
  HelpCircle,
  RefreshCw,
  ShieldAlert,
  Cpu,
  MinusCircle,
  Wrench,
  XCircle,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageHeader, EmptyState } from "@/components/app-page";
import {
  prismeKeys,
  usePropositionsSupervision,
  useDeclencherAnalyseSupervision,
  useDeciderPropositionSupervision,
  useLabelsInstances,
  useInstances,
  useSolveurs,
  useEvaluerSolveurSupervision,
  PrismeAPIError,
  type ConstatSolveur,
  type EvaluationSolveurSupervision,
  type VerdictConstatSolveur,
  type PropositionSupervision,
  type ReponseDecisionPropositionSupervision,
} from "@/integrations/prisme";
import { useAuth } from "@/integrations/prisme/auth";

export const Route = createFileRoute("/_authenticated/supervision")({
  head: () => ({ meta: [{ title: "Supervision — PRISME" }] }),
  component: SupervisionPage,
});

const LABEL_TYPE_SIGNAL: Record<PropositionSupervision["type_signal"], string> = {
  signature_orpheline: "Signature orpheline",
  echecs_repetes: "Échecs répétés",
  instance_a_replanifier: "À replanifier",
  commande_en_retard: "Commande en retard",
  solveur_a_regenerer: "Solveur à régénérer",
  instance_jugee_infaisable: "Jugée infaisable",
};

const ICONE_TYPE_SIGNAL: Record<PropositionSupervision["type_signal"], typeof AlertTriangle> = {
  signature_orpheline: AlertTriangle,
  echecs_repetes: XCircle,
  instance_a_replanifier: RefreshCw,
  commande_en_retard: Clock,
  solveur_a_regenerer: Cpu,
  instance_jugee_infaisable: AlertTriangle,
};

export function BadgeTypeSignal({ type }: { type: PropositionSupervision["type_signal"] }) {
  const Icone = ICONE_TYPE_SIGNAL[type];
  return (
    <Badge variant="outline" className="gap-1">
      <Icone className="h-3 w-3" /> {LABEL_TYPE_SIGNAL[type]}
    </Badge>
  );
}

function BadgePriorite({ priorite }: { priorite: PropositionSupervision["priorite"] }) {
  if (priorite === "haute") {
    return <Badge variant="destructive">Haute</Badge>;
  }
  if (priorite === "moyenne") {
    return <Badge variant="secondary">Moyenne</Badge>;
  }
  return <Badge variant="outline">Basse</Badge>;
}

function BadgeDecisionProposition({ decision }: { decision: PropositionSupervision["decision"] }) {
  if (decision === "acceptee") {
    return (
      <Badge variant="secondary" className="gap-1">
        <CheckCircle2 className="h-3 w-3" /> Acceptée
      </Badge>
    );
  }
  if (decision === "refusee") {
    return (
      <Badge variant="destructive" className="gap-1">
        <XCircle className="h-3 w-3" /> Refusée
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="gap-1 text-muted-foreground">
      <HelpCircle className="h-3 w-3" /> En attente
    </Badge>
  );
}

function resumeResultatDispatch(
  resultat: NonNullable<ReponseDecisionPropositionSupervision["resultat"]>,
): string {
  if (resultat.action === "regenerer_solveur")
    return `Génération démarrée (job ${resultat.job_id}).`;
  if (resultat.action === "executer") {
    return resultat.reussi
      ? `Exécution réussie (${resultat.execution_id}).`
      : `Exécution terminée en échec (${resultat.execution_id}).`;
  }
  if (resultat.action === "diagnostiquer")
    return `Diagnostic : cause identifiée — ${resultat.cause}.`;
  if (resultat.action === "aucune")
    return "Signalé — aucune action système : à traiter par vous (données, client, planification).";
  return "Action déclenchée.";
}

const PRESENTATION_VERDICT: Record<
  VerdictConstatSolveur,
  { label: string; icone: typeof AlertTriangle; couleur: string }
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

// Verdict « faut-il régénérer ce solveur ? » — un constat argumenté par changement (essai réel,
// lecture du code, Benchmarker : supervision/adequation.py). Seul un constat bloquant recommande de
// régénérer ; la décision reste humaine, en acceptant la proposition correspondante après analyse.
function VerdictSolveur({ evaluation }: { evaluation: EvaluationSolveurSupervision }) {
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
          Lancez « Analyser cet atelier » pour créer la proposition de régénération, puis
          acceptez-la pour démarrer la génération d'un nouveau solveur.
        </p>
      )}
    </div>
  );
}

function SupervisionPage() {
  const { utilisateur } = useAuth();
  const estAdmin = utilisateur?.role === "admin";
  const [clientId, setClientId] = useState("");

  const queryClient = useQueryClient();
  const { data: propositions, isLoading } = usePropositionsSupervision();
  const analyser = useDeclencherAnalyseSupervision();
  const decider = useDeciderPropositionSupervision();
  const labels = useLabelsInstances();
  const { data: instances } = useInstances();
  const { data: solveurs } = useSolveurs();

  // Entrée de l'analyse : l'atelier (instance_id) puis l'un de ses solveurs (id_solveur). Un
  // solveur ne sert que l'instance qui l'a fait générer : la liste ne propose que ceux de l'atelier
  // choisi. Atelier sans solveur : l'analyse part sans id_solveur, et c'est justement ce qu'elle
  // doit signaler.
  const [instanceId, setInstanceId] = useState<string>("");
  const [idSolveur, setIdSolveur] = useState<string>("");
  const solveursAtelier = useMemo(
    () => (solveurs ?? []).filter((s) => s.instance_id === instanceId),
    [solveurs, instanceId],
  );

  function choisirAtelier(id: string) {
    evaluer.reset();
    setInstanceId(id);
    const siens = (solveurs ?? []).filter((s) => s.instance_id === id);
    // Présélectionne le solveur le plus récent de l'atelier — le cas courant.
    const plusRecent = [...siens].sort((a, b) =>
      b.date_validation.localeCompare(a.date_validation),
    )[0];
    setIdSolveur(plusRecent?.id ?? "");
  }

  const evaluer = useEvaluerSolveurSupervision();
  const erreurEvaluation = evaluer.error as PrismeAPIError | null;

  function verifierSolveur() {
    if (!instanceId || !idSolveur) return;
    evaluer.mutate({ instanceId, idSolveur });
  }

  const erreurAnalyse = analyser.error as PrismeAPIError | null;

  function invaliderPropositions() {
    queryClient.invalidateQueries({ queryKey: prismeKeys.propositionsSupervision() });
  }

  function lancerAnalyseAtelier() {
    if (!instanceId) return;
    analyser.mutate(
      { instance_id: instanceId, id_solveur: idSolveur || undefined },
      {
        onSuccess: (nouvelles) => {
          toast.success(
            nouvelles.length > 0
              ? `${nouvelles.length} nouvelle(s) proposition(s) pour cet atelier.`
              : "Aucun nouveau signal détecté sur cet atelier.",
          );
          invaliderPropositions();
        },
        onError: (erreur) => toast.error((erreur as PrismeAPIError).message),
      },
    );
  }

  function lancerAnalyse() {
    analyser.mutate(
      { client_id: estAdmin && clientId.trim() ? clientId.trim() : undefined },
      {
        onSuccess: (nouvelles) => {
          toast.success(
            nouvelles.length > 0
              ? `${nouvelles.length} nouvelle(s) proposition(s) détectée(s).`
              : "Aucun nouveau signal détecté.",
          );
          invaliderPropositions();
        },
        onError: (erreur) => toast.error((erreur as PrismeAPIError).message),
      },
    );
  }

  function decider_(propositionId: string, decision: "acceptee" | "refusee") {
    decider.mutate(
      { propositionId, requete: { decision } },
      {
        onSuccess: (reponse) => {
          if (reponse.resultat) {
            toast.success(resumeResultatDispatch(reponse.resultat));
          } else {
            toast.success(
              decision === "acceptee" ? "Proposition acceptée." : "Proposition refusée.",
            );
          }
          invaliderPropositions();
        },
        onError: (erreur) => toast.error((erreur as PrismeAPIError).message),
      },
    );
  }

  // Atelier choisi : seules ses propositions sont affichées, pour traiter un atelier à la fois.
  const propositionsTriees = [...(propositions ?? [])]
    .filter((p) => !instanceId || p.instance_id === instanceId)
    .sort((a, b) => b.date_creation.localeCompare(a.date_creation));

  return (
    <>
      <PageHeader
        title="Supervision"
        desc="L'agent de supervision détecte des signaux sur l'historique des instances, exécutions et commandes (signature orpheline, échecs répétés, instance en attente de replanification, commande en retard) et propose une action — jamais appliquée automatiquement. Accepter une proposition déclenche l'action correspondante (génération, exécution, diagnostic) ou reste purement informatif pour un retard de commande."
      />

      <div className="glass mb-4 space-y-4 rounded-2xl p-4">
        <div>
          <h3 className="text-sm font-semibold">Analyser un atelier</h3>
          <p className="text-xs text-muted-foreground">
            L'agent analyse un atelier à la fois : il ne voit que cet atelier, le solveur choisi et
            les exécutions de ce solveur.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1.5">
            <Label htmlFor="supervision_atelier">Atelier (instance)</Label>
            <Select value={instanceId || undefined} onValueChange={choisirAtelier}>
              <SelectTrigger id="supervision_atelier" className="w-72">
                <SelectValue placeholder="Choisir un atelier" />
              </SelectTrigger>
              <SelectContent>
                {(instances ?? []).map((inst) => (
                  <SelectItem key={inst.instance_id} value={inst.instance_id}>
                    {labels.get(inst.instance_id)?.label ?? inst.instance_id.slice(0, 8)} ·{" "}
                    {inst.client_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="supervision_solveur">Solveur</Label>
            <Select
              value={idSolveur || undefined}
              onValueChange={(v) => {
                evaluer.reset();
                setIdSolveur(v);
              }}
              disabled={!instanceId || solveursAtelier.length === 0}
            >
              <SelectTrigger id="supervision_solveur" className="w-72">
                <SelectValue
                  placeholder={
                    !instanceId ? "Choisir d'abord un atelier" : "Aucun solveur pour cet atelier"
                  }
                />
              </SelectTrigger>
              <SelectContent>
                {solveursAtelier.map((s) => (
                  <SelectItem key={s.id} value={s.id}>
                    <span className="font-mono text-xs">{s.id.slice(0, 8)}</span>
                    {s.algorithme ? ` · ${s.algorithme}` : ""} ·{" "}
                    {new Date(s.date_validation).toLocaleDateString("fr-FR")}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={lancerAnalyseAtelier}
            disabled={analyser.isPending || !instanceId}
            className="bg-gradient-to-r from-primary to-accent"
          >
            <Zap className="mr-2 h-4 w-4" />
            {analyser.isPending ? "Analyse en cours..." : "Analyser cet atelier"}
          </Button>
          <Button
            variant="outline"
            onClick={verifierSolveur}
            disabled={evaluer.isPending || !instanceId || !idSolveur}
            title="Contraintes, objectifs et algorithme : faut-il régénérer ce solveur ?"
          >
            <Cpu className="mr-2 h-4 w-4" />
            {evaluer.isPending ? "Vérification..." : "Faut-il régénérer ce solveur ?"}
          </Button>
          {instanceId && (
            <Button
              variant="ghost"
              onClick={() => {
                setInstanceId("");
                setIdSolveur("");
              }}
            >
              Voir tous les ateliers
            </Button>
          )}
        </div>
        {erreurAnalyse && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" /> {erreurAnalyse.message}
          </p>
        )}
        {erreurEvaluation && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" /> {erreurEvaluation.message}
          </p>
        )}
        {evaluer.data && <VerdictSolveur evaluation={evaluer.data} />}
      </div>

      <div className="glass mb-6 flex flex-wrap items-end gap-4 rounded-2xl p-4">
        <p className="w-full text-xs text-muted-foreground">
          Ou analyser tous les ateliers d'un coup — chacun reste traité séparément, l'un après
          l'autre.
        </p>
        {estAdmin && (
          <div className="space-y-1.5">
            <Label htmlFor="client_id_supervision">Client (optionnel — vide = tous)</Label>
            <Input
              id="client_id_supervision"
              value={clientId}
              onChange={(e) => setClientId(e.target.value)}
              placeholder="tous les clients"
              className="w-64"
            />
          </div>
        )}
        <Button variant="outline" onClick={lancerAnalyse} disabled={analyser.isPending}>
          <Zap className="mr-2 h-4 w-4" />
          Analyser tous les ateliers
        </Button>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Chargement...</p>
      ) : propositionsTriees.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title={instanceId ? "Aucune proposition pour cet atelier" : "Aucune proposition"}
          desc="Lancez une analyse pour détecter d'éventuels signaux sur vos ateliers et exécutions."
        />
      ) : (
        <div className="glass overflow-hidden rounded-2xl">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Signal</TableHead>
                <TableHead>Priorité</TableHead>
                <TableHead>Résumé</TableHead>
                <TableHead>Instance</TableHead>
                <TableHead>Statut</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {propositionsTriees.map((p) => (
                <TableRow key={p.proposition_id}>
                  <TableCell>
                    <BadgeTypeSignal type={p.type_signal} />
                  </TableCell>
                  <TableCell>
                    <BadgePriorite priorite={p.priorite} />
                  </TableCell>
                  <TableCell className="max-w-md text-sm">{p.resume}</TableCell>
                  <TableCell>
                    {p.instance_id ? (
                      <Badge variant="outline" className="font-mono text-xs" title={p.instance_id}>
                        {labels.get(p.instance_id)?.label ?? p.instance_id}
                      </Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground">instance supprimée</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <BadgeDecisionProposition decision={p.decision} />
                  </TableCell>
                  <TableCell>
                    {p.decision === null && (
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={decider.isPending}
                          onClick={() => decider_(p.proposition_id, "refusee")}
                        >
                          Refuser
                        </Button>
                        <Button
                          size="sm"
                          disabled={decider.isPending}
                          onClick={() => decider_(p.proposition_id, "acceptee")}
                        >
                          <Wrench className="mr-1.5 h-3.5 w-3.5" /> Accepter
                        </Button>
                      </div>
                    )}
                    {p.decision !== null && p.horodatage_decision && (
                      <span className="flex items-center justify-end gap-1 text-xs text-muted-foreground">
                        <Clock className="h-3 w-3" />{" "}
                        {new Date(p.horodatage_decision).toLocaleString()}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </>
  );
}

import { useState } from "react";
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
  Wrench,
  XCircle,
  Zap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
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
  PrismeAPIError,
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
};

const ICONE_TYPE_SIGNAL: Record<PropositionSupervision["type_signal"], typeof AlertTriangle> = {
  signature_orpheline: AlertTriangle,
  echecs_repetes: XCircle,
  instance_a_replanifier: RefreshCw,
};

function BadgeTypeSignal({ type }: { type: PropositionSupervision["type_signal"] }) {
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
  return "Action déclenchée.";
}

function SupervisionPage() {
  const { utilisateur } = useAuth();
  const estAdmin = utilisateur?.role === "admin";
  const [clientId, setClientId] = useState("");

  const queryClient = useQueryClient();
  const { data: propositions, isLoading } = usePropositionsSupervision();
  const analyser = useDeclencherAnalyseSupervision();
  const decider = useDeciderPropositionSupervision();

  const erreurAnalyse = analyser.error as PrismeAPIError | null;

  function invaliderPropositions() {
    queryClient.invalidateQueries({ queryKey: prismeKeys.propositionsSupervision() });
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

  const propositionsTriees = [...(propositions ?? [])].sort((a, b) =>
    b.date_creation.localeCompare(a.date_creation),
  );

  return (
    <>
      <PageHeader
        title="Supervision"
        desc="L'agent de supervision détecte des signaux sur l'historique des instances et exécutions (signature orpheline, échecs répétés, instance en attente de replanification) et propose une action — jamais appliquée automatiquement. Accepter une proposition déclenche l'action correspondante (génération, exécution ou diagnostic)."
      />

      <div className="glass mb-6 flex flex-wrap items-end gap-4 rounded-2xl p-4">
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
        <Button
          onClick={lancerAnalyse}
          disabled={analyser.isPending}
          className="bg-gradient-to-r from-primary to-accent"
        >
          <Zap className="mr-2 h-4 w-4" />
          {analyser.isPending ? "Analyse en cours..." : "Analyser maintenant"}
        </Button>
        {erreurAnalyse && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="h-4 w-4" /> {erreurAnalyse.message}
          </p>
        )}
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Chargement...</p>
      ) : propositionsTriees.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title="Aucune proposition"
          desc="Lancez une analyse pour détecter d'éventuels signaux sur vos instances et exécutions."
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
                      <Badge variant="outline" className="font-mono text-xs">
                        {p.instance_id}
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

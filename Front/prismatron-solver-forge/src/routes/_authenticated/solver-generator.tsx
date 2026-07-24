import { useEffect, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { AlertCircle, CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { PageHeader, EmptyState } from "@/components/app-page";
import { useInstances, useGenererSolveur, PrismeAPIError } from "@/integrations/prisme";

export const Route = createFileRoute("/_authenticated/solver-generator")({
  head: () => ({ meta: [{ title: "Générateur de solveurs — PRISME" }] }),
  component: SolverGeneratorPage,
});

const MESSAGES_GENERATION = [
  "Rédaction du code du solveur par l'agent générateur...",
  "Validation statique du code généré (garde-fou §5.3)...",
  "Exécution en isolation et jugement par la cascade (faisabilité, optimalité, fidélité)...",
  "Enregistrement de l'artefact si la cascade est au vert...",
];

// Ni les étapes ni leur durée ne sont réelles — l'appel serveur est
// atomique (un seul aller-retour). Sert uniquement à ce que l'attente ne
// semble pas figée, même motif que donnees.tsx.
function IndicateurGeneration() {
  const [secondes, setSecondes] = useState(0);
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const debut = Date.now();
    const timerSecondes = setInterval(() => setSecondes(Math.floor((Date.now() - debut) / 1000)), 1000);
    const timerMessage = setInterval(
      () => setMessageIndex((i) => (i + 1) % MESSAGES_GENERATION.length),
      4000,
    );
    return () => {
      clearInterval(timerSecondes);
      clearInterval(timerMessage);
    };
  }, []);

  const minutes = Math.floor(secondes / 60);
  const reste = (secondes % 60).toString().padStart(2, "0");

  return (
    <div className="glass flex items-center gap-3 rounded-xl p-4">
      <Loader2 className="h-5 w-5 shrink-0 animate-spin text-primary" />
      <div className="min-w-0">
        <div className="text-sm font-medium">
          Génération en cours — {minutes}:{reste}
        </div>
        <div className="truncate text-xs text-muted-foreground">{MESSAGES_GENERATION[messageIndex]}</div>
      </div>
    </div>
  );
}

function SolverGeneratorPage() {
  const { data: instances, isLoading } = useInstances();
  const [instanceId, setInstanceId] = useState<string>("");
  const generer = useGenererSolveur();

  const erreurRequete = generer.error as PrismeAPIError | null;
  const resultat = generer.data;

  function lancer() {
    if (!instanceId) return;
    generer.reset();
    generer.mutate(instanceId);
  }

  return (
    <>
      <PageHeader
        title="Générateur de solveurs"
        desc="Pipeline multi-agents avec boucle de réparation bornée (jusqu'à 3 tentatives, Reviewer et Debugger corrigeant le code entre chaque essai) : jugé par la cascade complète (faisabilité, optimalité, fidélité) à chaque tentative, et enregistré seulement si intégralement vert."
        action={
          <Button
            className="bg-gradient-to-r from-primary to-accent"
            onClick={lancer}
            disabled={!instanceId || generer.isPending}
          >
            {generer.isPending ? "Génération en cours..." : "Lancer la génération"}
          </Button>
        }
      />

      <div className="space-y-4">
        <div className="glass rounded-2xl p-6">
          <Label htmlFor="instance_cible">Instance</Label>
          {!isLoading && instances && instances.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">
              Aucune instance disponible — ingérez-en une d'abord depuis la page Instances.
            </p>
          ) : (
            <Select value={instanceId} onValueChange={setInstanceId}>
              <SelectTrigger id="instance_cible" className="mt-2 w-full sm:w-96">
                <SelectValue placeholder="Choisir une instance..." />
              </SelectTrigger>
              <SelectContent>
                {instances?.map((i) => (
                  <SelectItem key={i.instance_id} value={i.instance_id}>
                    <span className="font-mono text-xs">{i.instance_id}</span> — {i.client_id} (
                    {i.structure_contraintes})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <p className="mt-2 text-xs text-muted-foreground">
            Le code généré est générique à tout le DSL, pas spécifique aux données de cette instance — elle sert
            seulement à déterminer sous quelle clé (client, structure des contraintes, objectifs) enregistrer le
            solveur, pour que <code className="font-mono">/execution</code> le retrouve ensuite.
          </p>
        </div>

        {generer.isPending && <IndicateurGeneration />}

        {erreurRequete && (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            <div className="flex items-center gap-2 font-medium">
              <AlertCircle className="h-4 w-4" /> Échec de la requête
            </div>
            <p className="mt-1">{erreurRequete.message}</p>
          </div>
        )}

        {resultat && (
          <div
            className={`glass rounded-2xl p-6 ${resultat.reussi ? "border border-primary/40" : "border border-destructive/40"}`}
          >
            {resultat.reussi ? (
              <>
                <div className="flex items-center gap-2 font-medium text-primary">
                  <CheckCircle2 className="h-4 w-4" /> Solveur généré et enregistré
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  Réussi en {resultat.nombre_tentatives} tentative{resultat.nombre_tentatives > 1 ? "s" : ""}.
                </p>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-muted-foreground">id_solveur :</span>
                  <Badge variant="secondary" className="font-mono text-xs">{resultat.id_solveur}</Badge>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                  <span className="text-muted-foreground">clé de matching :</span>
                  <Badge variant="outline" className="font-mono text-xs">{resultat.structure_contraintes}</Badge>
                  <Badge variant="outline" className="font-mono text-xs">{resultat.signature_objectifs}</Badge>
                </div>
              </>
            ) : (
              <>
                <div className="flex items-center gap-2 font-medium text-destructive">
                  <AlertCircle className="h-4 w-4" /> Échec après {resultat.nombre_tentatives} tentative
                  {resultat.nombre_tentatives > 1 ? "s" : ""} — rien n'a été enregistré
                </div>
                {resultat.erreur && <p className="mt-2 text-sm text-muted-foreground">{resultat.erreur}</p>}
                {resultat.echecs_cascade.length > 0 && (
                  <ul className="mt-3 space-y-2">
                    {resultat.echecs_cascade.map((e, i) => (
                      <li key={i} className="rounded-md border border-border/50 p-2 text-sm">
                        <div className="font-medium">
                          {e.nom}
                          {e.brique_en_echec && (
                            <Badge variant="outline" className="ml-2 text-xs">{e.brique_en_echec}</Badge>
                          )}
                        </div>
                        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">
                          {e.details.map((d, j) => (
                            <li key={j}>{d}</li>
                          ))}
                        </ul>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
        )}

        {!generer.isPending && !resultat && !erreurRequete && (
          <EmptyState
            icon={Sparkles}
            title="Aucune génération lancée"
            desc="Choisissez une instance et lancez la génération pour voir le résultat de la cascade de validation ici."
          />
        )}
      </div>
    </>
  );
}

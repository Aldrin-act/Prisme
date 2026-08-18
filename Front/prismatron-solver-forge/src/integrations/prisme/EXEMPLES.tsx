/**
 * COMPOSANTS EXEMPLES - Intégration PRISME
 *
 * Composants React prêts à l'emploi utilisant l'intégration PRISME.
 * Copiez-collez et adaptez selon vos besoins.
 */

import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useInstances,
  useExecutions,
  usePlanning,
  useSante,
  useIngererInstance,
  useDeclencherExecution,
  useDiagnostiquer,
  useSoumettreDecision,
  prismeKeys,
  type InstanceTRCO,
} from "./index";

// ============================================================================
// EXEMPLE 1 : Dashboard de supervision
// ============================================================================

export function DashboardSupervision() {
  const { data: sante } = useSante();
  const { data: instances, isLoading: loadingInstances } = useInstances({
    refetchInterval: 5000,
  });
  const { data: executions } = useExecutions({ refetchInterval: 5000 });

  return (
    <div className="p-6 space-y-6">
      {/* Santé du système */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-semibold mb-3">Santé du Système</h2>
        <div className="flex gap-6">
          <div>
            <span className={sante?.api ? "text-green-600" : "text-red-600"}>
              {sante?.api ? "🟢" : "🔴"}
            </span>{" "}
            API FastAPI
          </div>
          <div>
            <span className={sante?.sandbox_docker ? "text-green-600" : "text-red-600"}>
              {sante?.sandbox_docker ? "🟢" : "🔴"}
            </span>{" "}
            Sandbox Docker
          </div>
        </div>
      </div>

      {/* Instances */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-semibold mb-3">Instances ({instances?.length || 0})</h2>
        {loadingInstances ? (
          <p>Chargement...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Client
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Statut
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {instances?.map((inst) => (
                  <tr key={inst.instance_id}>
                    <td className="px-6 py-4 text-sm">{inst.instance_id}</td>
                    <td className="px-6 py-4 text-sm">{inst.client_id}</td>
                    <td className="px-6 py-4 text-sm">
                      {inst.executee ? "Exécutée" : "En attente"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Exécutions récentes */}
      <div className="bg-white rounded-lg shadow p-4">
        <h2 className="text-lg font-semibold mb-3">Exécutions Récentes</h2>
        <div className="space-y-2">
          {executions?.slice(0, 5).map((exec) => (
            <div
              key={exec.execution_id}
              className="flex items-center justify-between p-3 bg-gray-50 rounded"
            >
              <span className="text-sm font-mono">{exec.execution_id}</span>
              <span className={exec.reussi ? "text-green-600" : "text-red-600"}>
                {exec.reussi ? "✅ Succès" : "❌ Échec"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// EXEMPLE 2 : Formulaire d'ingestion
// ============================================================================

export function IngestionForm() {
  const [clientId, setClientId] = useState("client-001");
  const mutation = useIngererInstance();
  const queryClient = useQueryClient();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const instance: InstanceTRCO = {
      taches: [{ id: "T1" }, { id: "T2" }, { id: "T3" }],
      ressources: [
        { id: "R1", competences: [] },
        { id: "R2", competences: [] },
      ],
      contraintes: [
        {
          type: "compatibilite_ressource_tache",
          tache: "T1",
          ressource: "R1",
          duree: 30,
        },
        {
          type: "compatibilite_ressource_tache",
          tache: "T2",
          ressource: "R2",
          duree: 45,
        },
        {
          type: "precedence",
          avant: "T1",
          apres: "T2",
        },
      ],
      objectifs: [{ type: "minimiser_makespan" }],
    };

    mutation.mutate(
      { clientId, instance },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
        },
      },
    );
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-md mx-auto p-6 space-y-4">
      <h2 className="text-xl font-bold">Ingérer une Instance</h2>

      <div>
        <label className="block text-sm font-medium mb-1">Client ID</label>
        <input
          type="text"
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          className="w-full border rounded px-3 py-2"
        />
      </div>

      <button
        type="submit"
        disabled={mutation.isPending}
        className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50"
      >
        {mutation.isPending ? "Ingestion en cours..." : "Ingérer"}
      </button>

      {mutation.isError && (
        <div className="p-3 bg-red-50 text-red-700 rounded">Erreur: {mutation.error.message}</div>
      )}

      {mutation.isSuccess && (
        <div className="p-3 bg-green-50 text-green-700 rounded">
          ✅ Instance ingérée : {mutation.data.instance_id}
        </div>
      )}
    </form>
  );
}

// ============================================================================
// EXEMPLE 3 : Exécution avec polling
// ============================================================================

export function ExecutionPanel({ instanceId }: { instanceId: string }) {
  const [executionId, setExecutionId] = useState<string | null>(null);
  const mutation = useDeclencherExecution();
  const queryClient = useQueryClient();

  // Polling si exécution en cours
  useExecutions({
    refetchInterval: (query) => {
      if (!executionId) return false;
      const executions = query.state.data;
      const execution = executions?.find((e) => e.execution_id === executionId);
      // Arrêter si terminé
      return execution && !execution.reussi && !execution.erreur ? 2000 : false;
    },
  });

  const handleExecute = () => {
    mutation.mutate(
      { instanceId },
      {
        onSuccess: (data) => {
          setExecutionId(data.execution_id);
          queryClient.invalidateQueries({ queryKey: prismeKeys.executions() });
        },
      },
    );
  };

  return (
    <div className="p-6 max-w-md mx-auto">
      <h2 className="text-xl font-bold mb-4">Exécution</h2>

      <button
        onClick={handleExecute}
        disabled={mutation.isPending}
        className="w-full bg-green-600 text-white py-2 rounded hover:bg-green-700"
      >
        {mutation.isPending ? "⏳ Exécution..." : "▶️ Exécuter"}
      </button>

      {executionId && (
        <div className="mt-4 p-3 bg-blue-50 rounded">
          <p className="text-sm font-mono">Execution ID: {executionId}</p>
          <p className="text-sm text-gray-600 mt-1">Polling actif...</p>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// EXEMPLE 4 : Affichage Planning avec Gantt simple
// ============================================================================

export function PlanningGantt({ executionId }: { executionId: string }) {
  const { data: planning, isLoading } = usePlanning(executionId);

  if (isLoading) return <div className="p-6">Chargement du planning...</div>;
  if (!planning) return <div className="p-6">Aucun planning disponible</div>;

  // Ni `fin` ni `makespan` n'existent sur le fil (`dsl/schema/planning.py`
  // est volontairement permissif) — `fin` se déduit de `durees["tache|ressource"]`.
  const operations = planning.operations.map((op) => ({
    ...op,
    fin: op.debut + (planning.durees[`${op.tache}|${op.ressource}`] ?? 0),
  }));
  const makespan = operations.length > 0 ? Math.max(...operations.map((op) => op.fin)) : 100;
  const scale = (time: number) => (time / makespan) * 100;

  return (
    <div className="p-6">
      <h2 className="text-xl font-bold mb-4">Planning (Makespan: {makespan})</h2>

      <div className="space-y-3">
        {operations.map((op, idx) => (
          <div key={idx} className="flex items-center gap-4">
            <span className="w-32 text-sm font-medium">
              {op.tache} → {op.ressource}
            </span>
            <div className="flex-1 h-8 bg-gray-100 rounded relative border">
              <div
                className="absolute h-full bg-blue-500 rounded flex items-center justify-center text-white text-xs"
                style={{
                  left: `${scale(op.debut)}%`,
                  width: `${scale(op.fin - op.debut)}%`,
                }}
              >
                {op.debut} → {op.fin}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================================================
// EXEMPLE 5 : Diagnostic avec feedback
// ============================================================================

export function DiagnosticPanel({ executionId }: { executionId: string }) {
  const [motif, setMotif] = useState("");
  const mutation = useDiagnostiquer();

  const handleDiagnostic = () => {
    mutation.mutate({ executionId, payload: { motif_declenchement: motif } });
  };

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <h2 className="text-xl font-bold mb-4">Diagnostic</h2>

      <textarea
        value={motif}
        onChange={(e) => setMotif(e.target.value)}
        placeholder="Décrivez le problème (ex: Makespan trop élevé, ressources mal utilisées...)"
        rows={4}
        className="w-full border rounded p-3 mb-4"
      />

      <button
        onClick={handleDiagnostic}
        disabled={mutation.isPending || !motif}
        className="w-full bg-orange-600 text-white py-2 rounded hover:bg-orange-700 disabled:opacity-50"
      >
        {mutation.isPending ? "🔍 Diagnostic en cours (2 min max)..." : "🔍 Lancer Diagnostic"}
      </button>

      {mutation.isError && (
        <div className="mt-4 p-4 bg-red-50 border-l-4 border-red-500 text-red-700">
          <p className="font-semibold">Erreur</p>
          <p className="text-sm">{mutation.error.message}</p>
        </div>
      )}

      {mutation.data && (
        <div className="mt-4 p-4 bg-blue-50 border-l-4 border-blue-500">
          <h3 className="font-semibold mb-2">Résultat du Diagnostic</h3>
          <dl className="space-y-2 text-sm">
            <div>
              <dt className="font-medium">Cause:</dt>
              <dd className="ml-4">{mutation.data.cause}</dd>
            </div>
            <div>
              <dt className="font-medium">Détails:</dt>
              <dd className="ml-4">{mutation.data.details}</dd>
            </div>
            <div>
              <dt className="font-medium">Proposition:</dt>
              <dd className="ml-4">{mutation.data.proposition}</dd>
            </div>
          </dl>
          {mutation.data.humain_decide && (
            <div className="mt-3 p-2 bg-yellow-100 text-yellow-800 rounded">
              ⚠️ Décision humaine requise
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// EXEMPLE 6 : Validation avec décision
// ============================================================================

export function ValidationPanel({ executionId }: { executionId: string }) {
  const [commentaire, setCommentaire] = useState("");
  const mutation = useSoumettreDecision();
  const queryClient = useQueryClient();

  const handleDecision = (acceptee: boolean) => {
    mutation.mutate(
      {
        executionId,
        decision: {
          decision: acceptee ? "acceptee" : "refusee",
          commentaire: commentaire || undefined,
        },
      },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: prismeKeys.executions() });
          setCommentaire("");
        },
      },
    );
  };

  return (
    <div className="p-6 max-w-md mx-auto">
      <h2 className="text-xl font-bold mb-4">Validation Planning</h2>

      <textarea
        value={commentaire}
        onChange={(e) => setCommentaire(e.target.value)}
        placeholder="Commentaire (optionnel)"
        rows={3}
        className="w-full border rounded p-3 mb-4"
      />

      <div className="flex gap-3">
        <button
          onClick={() => handleDecision(true)}
          disabled={mutation.isPending}
          className="flex-1 bg-green-600 text-white py-2 rounded hover:bg-green-700"
        >
          ✅ Accepter
        </button>
        <button
          onClick={() => handleDecision(false)}
          disabled={mutation.isPending}
          className="flex-1 bg-red-600 text-white py-2 rounded hover:bg-red-700"
        >
          ❌ Rejeter
        </button>
      </div>

      {mutation.isSuccess && (
        <div className="mt-4 p-3 bg-green-50 text-green-700 rounded">
          ✅ Décision enregistrée: {mutation.data.decision}
        </div>
      )}
    </div>
  );
}

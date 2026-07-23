# Intégration API PRISME

Client TypeScript type-safe pour l'API PRISME (FastAPI backend) avec hooks **TanStack Query** intégrés.

---

## 📦 Installation

Aucune dépendance supplémentaire nécessaire ! Le projet utilise déjà :
- ✅ `@tanstack/react-query` (gestion d'état async + cache)
- ✅ `zod` (validation optionnelle)
- ✅ TypeScript

---

## ⚙️ Configuration

### 1. Variables d'environnement

Créez `.env.local` :

```bash
cp .env.example .env.local
```

Puis modifiez :

```env
VITE_PRISME_API_URL=http://localhost:8000
```

### 2. Démarrer l'API backend

```bash
cd ../Prisme
uv run uvicorn api.app:app --reload
```

L'API sera disponible sur **http://localhost:8000**
Documentation : **http://localhost:8000/docs**

---

## 🚀 Utilisation

### Import

```typescript
import {
  // Client bas-niveau
  prismeClient,

  // Hooks TanStack Query
  useInstances,
  useExecutions,
  usePlanning,
  useIngererInstance,
  useDeclencherExecution,

  // Types
  type InstanceTRCO,
  type ReponseExecution,
  type PlanningAvecDurees,
} from '@/integrations/prisme';
```

---

## 📖 API Reference

### 🔍 Queries (Lecture - avec cache automatique)

#### `useInstances()`
Liste toutes les instances ingérées.

```typescript
function InstancesList() {
  const { data, isLoading, error, refetch } = useInstances({
    refetchInterval: 5000, // Auto-refresh toutes les 5s
  });

  if (isLoading) return <div>Chargement...</div>;
  if (error) return <div>Erreur: {error.message}</div>;

  return (
    <div>
      <button onClick={() => refetch()}>Rafraîchir</button>
      {data?.map((instance) => (
        <div key={instance.instance_id}>
          {instance.client_id} - {instance.structure_contraintes}
        </div>
      ))}
    </div>
  );
}
```

#### `useExecutions()`
Liste toutes les exécutions.

```typescript
function ExecutionsList() {
  const { data } = useExecutions();

  return (
    <ul>
      {data?.map((exec) => (
        <li key={exec.execution_id}>
          {exec.reussi ? '✅' : '❌'} {exec.instance_id}
        </li>
      ))}
    </ul>
  );
}
```

#### `usePlanning(executionId)`
Récupère le planning d'une exécution.

```typescript
function PlanningView({ executionId }: { executionId: string | null }) {
  const { data: planning, isLoading } = usePlanning(executionId);

  if (!executionId) return <div>Sélectionnez une exécution</div>;
  if (isLoading) return <div>Chargement du planning...</div>;

  return (
    <div>
      <h3>Makespan: {planning?.makespan}</h3>
      {planning?.operations.map((op, idx) => (
        <div key={idx}>
          {op.tache_id} sur {op.ressource_id} : {op.debut} → {op.fin}
        </div>
      ))}
    </div>
  );
}
```

#### `useSante()`
Vérifie la santé du système (auto-refresh 30s).

```typescript
function SystemStatus() {
  const { data: sante } = useSante();

  return (
    <div>
      API: {sante?.api ? '🟢' : '🔴'}
      Docker: {sante?.sandbox_docker ? '🟢' : '🔴'}
    </div>
  );
}
```

#### `useCodeSource(executionId)`
Récupère le code source du solveur (audit).

```typescript
function CodeAudit({ executionId }: { executionId: string }) {
  const { data, refetch } = useCodeSource(executionId, {
    enabled: false, // Ne pas charger automatiquement
  });

  return (
    <div>
      <button onClick={() => refetch()}>Afficher Code Source</button>
      {data && <pre>{data.code_source}</pre>}
    </div>
  );
}
```

---

### ✏️ Mutations (Écriture)

#### `useIngererInstance()`
Ingère une nouvelle instance.

```typescript
function IngestionForm() {
  const mutation = useIngererInstance();
  const queryClient = useQueryClient();

  const handleSubmit = async () => {
    const instance: InstanceTRCO = {
      taches: [{ id: 'T1' }, { id: 'T2' }],
      ressources: [{ id: 'R1' }],
      contraintes: [
        {
          type: 'compatibilite_ressource_tache',
          tache: 'T1',
          ressource: 'R1',
          duree: 30,
        },
      ],
      objectifs: [{ type: 'minimiser_makespan' }],
    };

    mutation.mutate(
      { clientId: 'client-001', instance },
      {
        onSuccess: (data) => {
          console.log('Instance ingérée:', data.instance_id);
          // Invalider le cache pour rafraîchir la liste
          queryClient.invalidateQueries({ queryKey: prismeKeys.instances() });
        },
        onError: (error) => {
          console.error('Erreur:', error.message);
        },
      }
    );
  };

  return (
    <div>
      <button onClick={handleSubmit} disabled={mutation.isPending}>
        {mutation.isPending ? 'Ingestion...' : 'Ingérer'}
      </button>
      {mutation.isError && <p>Erreur: {mutation.error.message}</p>}
      {mutation.isSuccess && <p>Succès ! ID: {mutation.data.instance_id}</p>}
    </div>
  );
}
```

#### `useDeclencherExecution()`
Déclenche l'exécution d'un solveur.

```typescript
function ExecuteButton({ instanceId }: { instanceId: string }) {
  const mutation = useDeclencherExecution();
  const queryClient = useQueryClient();

  const handleExecute = () => {
    mutation.mutate(
      { instanceId, clientId: 'client-001' },
      {
        onSuccess: (data) => {
          if (data.reussi) {
            console.log('Exécution réussie:', data.execution_id);
            queryClient.invalidateQueries({ queryKey: prismeKeys.executions() });
          } else {
            console.error('Exécution échouée:', data.erreur);
          }
        },
      }
    );
  };

  return (
    <button onClick={handleExecute} disabled={mutation.isPending}>
      {mutation.isPending ? 'Exécution...' : 'Exécuter'}
    </button>
  );
}
```

#### `useDiagnostiquer()`
Lance un diagnostic (opération lente, 2 min timeout).

```typescript
function DiagnosticForm({ executionId }: { executionId: string }) {
  const mutation = useDiagnostiquer();
  const [motif, setMotif] = useState('');

  const handleDiagnostic = () => {
    mutation.mutate({
      executionId,
      payload: { motif_declenchement: motif },
    });
  };

  return (
    <div>
      <textarea
        value={motif}
        onChange={(e) => setMotif(e.target.value)}
        placeholder="Motif du diagnostic..."
      />
      <button onClick={handleDiagnostic} disabled={mutation.isPending}>
        {mutation.isPending ? 'Diagnostic en cours (2 min max)...' : 'Diagnostiquer'}
      </button>
      {mutation.data && (
        <div>
          <p>Cause: {mutation.data.cause}</p>
          <p>Proposition: {mutation.data.proposition}</p>
        </div>
      )}
    </div>
  );
}
```

#### `useSoumettreDecision()`
Soumet une décision de validation.

```typescript
function ValidationButtons({ executionId }: { executionId: string }) {
  const mutation = useSoumettreDecision();

  const handleDecision = (accepte: boolean) => {
    mutation.mutate({
      executionId,
      decision: { accepte, commentaire: 'Validé par chef atelier' },
    });
  };

  return (
    <div>
      <button onClick={() => handleDecision(true)}>✅ Accepter</button>
      <button onClick={() => handleDecision(false)}>❌ Rejeter</button>
    </div>
  );
}
```

---

## 🎯 Patterns Avancés

### Workflow complet avec composition

```typescript
function WorkflowComplet() {
  const [instanceId, setInstanceId] = useState<string | null>(null);
  const [executionId, setExecutionId] = useState<string | null>(null);

  const ingestion = useIngererInstance();
  const execution = useDeclencherExecution();
  const { data: planning } = usePlanning(executionId);

  const handleWorkflow = async () => {
    // Étape 1 : Ingestion
    const instance: InstanceTRCO = { /* ... */ };
    const ingestionResult = await ingestion.mutateAsync({
      clientId: 'client-001',
      instance,
    });
    setInstanceId(ingestionResult.instance_id);

    // Étape 2 : Exécution
    const executionResult = await execution.mutateAsync({
      instanceId: ingestionResult.instance_id,
      clientId: 'client-001',
    });
    setExecutionId(executionResult.execution_id);

    // Étape 3 : Planning sera chargé automatiquement via usePlanning
  };

  return (
    <div>
      <button onClick={handleWorkflow}>Démarrer Workflow</button>
      {planning && <PlanningView planning={planning} />}
    </div>
  );
}
```

### Polling avec invalidation conditionnelle

```typescript
function ExecutionMonitor({ executionId }: { executionId: string }) {
  const queryClient = useQueryClient();

  // Polling toutes les 2s
  const { data } = useExecutions({
    refetchInterval: (query) => {
      const executions = query.state.data;
      const execution = executions?.find((e) => e.execution_id === executionId);

      // Arrêter le polling si terminé
      if (execution && (execution.reussi || execution.erreur)) {
        return false;
      }

      return 2000; // Continue polling
    },
  });

  return <div>{/* UI */}</div>;
}
```

### Optimistic Updates

```typescript
function QuickValidation({ executionId }: { executionId: string }) {
  const queryClient = useQueryClient();
  const mutation = useSoumettreDecision();

  const handleAccept = () => {
    mutation.mutate(
      { executionId, decision: { accepte: true } },
      {
        // Update optimiste immédiat
        onMutate: async () => {
          await queryClient.cancelQueries({ queryKey: prismeKeys.executions() });

          const previousData = queryClient.getQueryData(prismeKeys.executions());

          queryClient.setQueryData(prismeKeys.executions(), (old: any) => {
            return old?.map((exec: any) =>
              exec.execution_id === executionId
                ? { ...exec, validated: true }
                : exec
            );
          });

          return { previousData };
        },
        // Rollback si erreur
        onError: (err, variables, context) => {
          queryClient.setQueryData(prismeKeys.executions(), context.previousData);
        },
        // Resync avec serveur
        onSettled: () => {
          queryClient.invalidateQueries({ queryKey: prismeKeys.executions() });
        },
      }
    );
  };

  return <button onClick={handleAccept}>Accepter</button>;
}
```

---

## 🔧 Configuration TanStack Query

Dans votre `App.tsx` ou layout root :

```typescript
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      {/* Votre app */}
    </QueryClientProvider>
  );
}
```

---

## 🛠️ Utilisation du client bas-niveau (sans hooks)

Si vous avez besoin d'appeler l'API en dehors de React :

```typescript
import { prismeClient } from '@/integrations/prisme';

// Dans un middleware, serveur, ou fonction utilitaire
async function checkSystem() {
  try {
    const sante = await prismeClient.verifierSante();
    console.log('API:', sante.api);
    console.log('Docker:', sante.sandbox_docker);
  } catch (error) {
    if (error instanceof PrismeAPIError) {
      console.error('Erreur API:', error.status, error.detail);
    }
  }
}
```

---

## 📊 Structure des données

Tous les types sont exportés et documentés dans `types.ts`. Exemple :

```typescript
import type { InstanceTRCO, Planning, DiagnosticResultat } from '@/integrations/prisme';

const instance: InstanceTRCO = {
  taches: [{ id: 'T1' }],
  ressources: [{ id: 'R1' }],
  contraintes: [
    {
      type: 'compatibilite_ressource_tache',
      tache: 'T1',
      ressource: 'R1',
      duree: 30,
    },
  ],
  objectifs: [{ type: 'minimiser_makespan' }],
};
```

---

## 🚨 Gestion d'Erreurs

```typescript
import { PrismeAPIError } from '@/integrations/prisme';

function MyComponent() {
  const mutation = useIngererInstance();

  mutation.mutate(
    { clientId, instance },
    {
      onError: (error) => {
        if (error instanceof PrismeAPIError) {
          switch (error.status) {
            case 404:
              toast.error('Instance introuvable');
              break;
            case 409:
              toast.error('Aucun solveur disponible - générez-en un');
              break;
            case 422:
              toast.error('Données invalides');
              break;
            default:
              toast.error(`Erreur API: ${error.detail}`);
          }
        }
      },
    }
  );
}
```

---

## 📚 Ressources

- **API Backend** : http://localhost:8000/docs (Swagger UI)
- **TanStack Query** : https://tanstack.com/query/latest
- **Projet PRISME** : `../Prisme/README.md`

---

## ✅ Checklist Integration

- [x] Types TypeScript générés depuis modèles Pydantic
- [x] Client API avec fetch + timeout + retry
- [x] Hooks TanStack Query (queries + mutations)
- [x] Query keys centralisés
- [x] Gestion d'erreurs structurée
- [x] Support polling / refetch
- [x] Documentation complète + exemples
- [x] Configuration via .env

---

**Version** : 1.0.0
**Dernière mise à jour** : 2026-07-22

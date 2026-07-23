# Contrat d'API backend — PRISME

Ce document décrit l'API que le frontend PRISME (ce dépôt) attend d'un backend pour remplacer les données statiques actuellement codées en dur dans les pages de l'application (`src/routes/_authenticated/*`).

## 1. État actuel du frontend

Le frontend est aujourd'hui un prototype **entièrement statique** côté données métier :

- L'authentification est branchée sur le backend PRISME (FastAPI) via `src/integrations/prisme/auth/*` : inscription, connexion, déconnexion, rafraîchissement de token, tout transite par `/auth/*` (voir §2). Supabase et Lovable Cloud Auth ont été retirés du projet.
- Toutes les pages sous `/app`, `/instances`, `/dsl`, `/solver-generator`, `/solvers`, `/execution`, `/schedules`, `/validation`, `/audit`, `/analytics`, `/alerts`, `/api-keys`, `/settings` affichent des tableaux `const XXX = [...]` codés en dur dans le composant. Il n'y a **aucun appel réseau** vers un backend métier pour l'instant (hors auth).

Le but de ce document est de spécifier l'API REST qu'un backend doit exposer pour que ces pages deviennent fonctionnelles.

## 2. Authentification

Gérée par le backend PRISME lui-même (pas de fournisseur tiers). Le client (`src/integrations/prisme/auth/service.ts`) attend les routes suivantes sur `VITE_PRISME_API_URL` :

| Méthode | Route | Description |
|---|---|---|
| POST | `/auth/login` | `{ email, password }` → `{ session: { utilisateur, token, expires_at }, message }` |
| POST | `/auth/register` | `{ email, password, nom, prenom, role?, client_id? }` → même forme que login |
| POST | `/auth/logout` | Invalide le token courant |
| GET | `/auth/verify` | Vérifie la validité du token → `{ valid: boolean }` |
| POST | `/auth/refresh` | Émet un nouveau token avant expiration |
| POST | `/auth/change-password` | `{ ancien_mot_de_passe, nouveau_mot_de_passe }` |
| POST | `/auth/forgot-password` | `{ email }` |
| POST | `/auth/reset-password` | `{ token, nouveau_mot_de_passe }` |

- Le token est un JWT (ou équivalent) renvoyé dans `session.token`, stocké côté client (`localStorage`) et envoyé en `Authorization: Bearer <token>` sur chaque appel API métier suivant.
- Erreurs attendues au format `{ code, message }` avec `code` parmi `INVALID_CREDENTIALS | USER_EXISTS | UNAUTHORIZED | TOKEN_EXPIRED | UNKNOWN` (le frontend traduit ces codes en français).
- `Utilisateur` porte un `role` (`maintenant | operateur | admin`) qui détermine les permissions côté frontend (`PERMISSIONS_PAR_ROLE` dans `src/integrations/prisme/auth/types.ts`) — le backend doit renvoyer ce rôle sur chaque session.
- Réponse `401 Unauthorized` sur les endpoints métier ci-dessous si le token est absent, expiré ou invalide.

## 3. Conventions générales

- **Base URL** : `VITE_PRISME_API_URL` (déjà utilisée par le module auth, cf. `.env`), partagée par les endpoints métier ci-dessous.
- **Format** : JSON, `Content-Type: application/json`.
- **Dates** : ISO 8601 UTC (`2026-07-22T14:30:00Z`). Le frontend se charge du formatage relatif ("il y a 12min") et de la locale française à l'affichage.
- **Identifiants** : chaînes opaques (UUID ou équivalent), jamais d'entiers auto-incrémentés exposés.
- **Enums** : toujours en anglais/minuscules côté API (ex. `"active" | "draft" | "archived"`) — c'est le frontend qui traduit pour l'affichage. Ne pas envoyer de libellés déjà traduits.
- **Pagination** : `?page=1&pageSize=20` en query params, réponse enveloppée :
  ```json
  { "items": [...], "page": 1, "pageSize": 20, "total": 137 }
  ```
- **Erreurs** : format uniforme
  ```json
  { "error": { "code": "not_found", "message": "Instance not found" } }
  ```
- **Scoping** : toutes les ressources ci-dessous sont scopées par utilisateur/organisation (déduit du JWT) — un utilisateur ne voit jamais les instances d'un autre.

## 4. Ressources

### 4.1 Instances

Regroupe DSL, solveurs, exécutions et audit (`src/routes/_authenticated/instances.tsx`). Correspond au concept `InstanceTRCO` (Tâches-Ressources-Contraintes-Objectifs) déjà présent côté client dans `src/integrations/prisme/types.ts` et `client.ts` (`ingererInstance`, `listerInstances`, etc.) — ce sont les mêmes objets.

| Méthode | Route | Description |
|---|---|---|
| GET | `/instances` | Liste paginée des instances |
| POST | `/instances` | Créer une instance `{ name, description? }` |
| GET | `/instances/:id` | Détail d'une instance |
| PATCH | `/instances/:id` | Renommer / modifier |
| DELETE | `/instances/:id` | Supprimer |

```json
// Instance
{
  "id": "inst_01h...",
  "name": "Automotive · FR-01",
  "description": "Ligne d'assemblage carrosserie",
  "createdAt": "2026-06-01T10:00:00Z",
  "stats": { "solvers": 3, "runsToday": 0, "auditEvents": 12 }
}
```

### 4.2 DSL Definitions

Le texte DSL édité dans `/dsl` (`src/routes/_authenticated/dsl.tsx`), versionné comme du code.

| Méthode | Route | Description |
|---|---|---|
| GET | `/instances/:instanceId/dsl` | Dernière version du DSL de l'instance |
| GET | `/instances/:instanceId/dsl/versions` | Historique des versions |
| PUT | `/instances/:instanceId/dsl` | Enregistrer une nouvelle version `{ source }` |

```json
// DslDocument
{
  "id": "dsl_01h...",
  "instanceId": "inst_01h...",
  "version": 3,
  "source": "resource Line1 { capacity: 1 }\n...",
  "updatedAt": "2026-07-22T09:00:00Z",
  "updatedBy": "user_01h..."
}
```

### 4.3 Solver Generation (pipeline multi-agents)

Déclenché depuis `/dsl` ou `/solver-generator` (`src/routes/_authenticated/solver-generator.tsx`). C'est un **job asynchrone** — le pipeline (parse → génération → validation → stockage) prend plusieurs secondes.

| Méthode | Route | Description |
|---|---|---|
| POST | `/instances/:instanceId/generations` | Démarre une génération à partir du DSL courant, retourne `{ generationId }` |
| GET | `/generations/:id` | Statut courant + étapes du pipeline |

```json
// GenerationStatus
{
  "id": "gen_01h...",
  "instanceId": "inst_01h...",
  "status": "running", // "queued" | "running" | "succeeded" | "failed"
  "steps": [
    { "key": "parse_dsl",       "label": "Parse DSL",           "status": "done" },
    { "key": "author_solver",   "label": "Author solver",       "status": "done" },
    { "key": "validate_explain","label": "Validate & explain",  "status": "running" },
    { "key": "store_artifact",  "label": "Store artifact",      "status": "pending" }
  ],
  "logs": [
    "[parser] 4 resources, 2 jobs, 3 constraints, 1 objective — OK",
    "[generator] emitting model.py — 132 lines"
  ],
  "resultSolverId": null // rempli quand status = "succeeded"
}
```

**Temps réel** : puisque ce process dure plusieurs secondes, prévoir soit :
- **polling** court (le frontend interroge `GET /generations/:id` toutes les 1-2s), soit
- **WebSocket/SSE** (`/generations/:id/stream`) émettant les mêmes champs à chaque changement d'étape — recommandé pour éviter le polling sur `/execution` et `/solver-generator`.

### 4.4 Solvers (artefacts générés)

Table listée dans `/solvers` (`src/routes/_authenticated/solvers.tsx`).

| Méthode | Route | Description |
|---|---|---|
| GET | `/instances/:instanceId/solvers` | Liste des solveurs de l'instance |
| GET | `/solvers/:id` | Détail (métadonnées + code) |
| GET | `/solvers/:id/export` | Télécharge le fichier Python (`Content-Type: text/x-python`) |
| POST | `/solvers/:id/promote` | Passe le statut à `active` (nécessite validation OK, cf 4.6) |
| POST | `/solvers/:id/archive` | Archive un solveur |

```json
// Solver
{
  "id": "solver_01h...",
  "instanceId": "inst_01h...",
  "name": "assembly-line-v3",
  "status": "active", // "active" | "draft" | "archived"
  "generatedAt": "2026-07-22T12:00:00Z",
  "generationId": "gen_01h...",
  "sourceUrl": "/solvers/solver_01h.../export",
  "linesOfCode": 132,
  "signature": "sha256:..."
}
```

### 4.5 Executions (bac à sable)

Table de `/execution` (`src/routes/_authenticated/execution.tsx`).

| Méthode | Route | Description |
|---|---|---|
| POST | `/solvers/:id/runs` | Lance une exécution en bac à sable, retourne `{ runId }` |
| GET | `/runs?instanceId=` | Liste des exécutions récentes (+ KPIs agrégés) |
| GET | `/runs/:id` | Détail d'une exécution (statut, durée, logs, sortie) |

```json
// Run
{
  "id": "run_912",
  "solverId": "solver_01h...",
  "solverName": "assembly-line-v3",
  "status": "success", // "queued" | "running" | "success" | "failed"
  "startedAt": "2026-07-22T13:00:00Z",
  "durationMs": 4200,
  "exitCode": 0,
  "output": null // schedule produit, cf. 4.6, ou message d'erreur si failed
}
```

```json
// GET /runs?instanceId=... -> résumé pour les cartes KPI de la page Execution Center
{
  "items": [ /* Run[] */ ],
  "kpis": { "runsToday": 4, "avgWallTimeMs": 4900, "sandboxUptimePct": 100 }
}
```

### 4.6 Schedules (résultat de l'optimisation)

Vue Gantt de `/schedules` (`src/routes/_authenticated/schedules.tsx`), produite par une exécution réussie.

| Méthode | Route | Description |
|---|---|---|
| GET | `/instances/:instanceId/schedules/latest` | Dernier planning optimisé |
| GET | `/runs/:runId/schedule` | Planning produit par une exécution donnée |

```json
// Schedule
{
  "id": "sched_01h...",
  "runId": "run_912",
  "resource": "Line 1",
  "week": 42,
  "makespanMinutes": 494,
  "utilizationPct": 92,
  "lanes": [
    {
      "job": "Body-Paint",
      "blocks": [ { "startMinute": 60, "durationMinute": 120 } ]
    }
  ]
}
```

### 4.7 Validation

Résultats affichés sur `/validation` (`src/routes/_authenticated/validation.tsx`), produits pendant l'étape `validate_explain` de la génération.

| Méthode | Route | Description |
|---|---|---|
| GET | `/solvers/:id/validation` | Résultats des vérifications pour ce solveur |

```json
// ValidationReport
{
  "solverId": "solver_01h...",
  "issueCount": 1,
  "checks": [
    { "key": "static_types",     "label": "Static type checks",        "status": "pass" },
    { "key": "reachability",     "label": "Constraint reachability",   "status": "pass" },
    { "key": "property_tests",   "label": "Property tests (500 seeds)","status": "warn", "note": "3 flaky seeds" },
    { "key": "resource_bounds",  "label": "Resource-usage bounds",     "status": "pass" },
    { "key": "determinism",      "label": "Deterministic output",      "status": "fail", "note": "Non-deterministic tie-break at Line1" },
    { "key": "signature",        "label": "Signature & provenance",    "status": "pass" }
  ]
}
```

### 4.8 Audit

Journal immuable de `/audit` (`src/routes/_authenticated/audit.tsx`). Doit être **append-only** côté backend (jamais de PATCH/DELETE).

| Méthode | Route | Description |
|---|---|---|
| GET | `/instances/:instanceId/audit?since=&page=` | Liste paginée, plus récent en premier |

```json
// AuditEvent
{
  "id": "audit_01h...",
  "occurredAt": "2026-07-22T13:58:00Z",
  "actor": "you", // "you" | "ai-generator" | "validator" | "sandbox" | ...
  "action": "solver.promoted",
  "description": "Approved solver assembly-line-v3 → Production",
  "metadata": { "solverId": "solver_01h..." }
}
```

### 4.9 Analytics

KPIs et séries temporelles de `/analytics` (`src/routes/_authenticated/analytics.tsx`).

| Méthode | Route | Description |
|---|---|---|
| GET | `/instances/:instanceId/analytics` | KPIs courants + série des 12 dernières semaines |

```json
{
  "kpis": {
    "avgMakespanMinutes": { "value": 402, "deltaPct": -12 },
    "oeePct":             { "value": 82.3, "deltaPct": 3.1 },
    "solverSuccessPct":   { "value": 97, "deltaPct": 1 },
    "p95SandboxMs":       { "value": 5900, "deltaMs": -400 }
  },
  "runsPerWeek": [12, 18, 22, 16, 28, 34, 30, 40, 44, 38, 52, 48]
}
```

### 4.10 Alerts

Notifications de `/alerts` (`src/routes/_authenticated/alerts.tsx`).

| Méthode | Route | Description |
|---|---|---|
| GET | `/instances/:instanceId/alerts` | Liste des alertes récentes |
| POST | `/alerts/:id/ack` | Marquer comme lue |
| GET/PUT | `/instances/:instanceId/alert-routes` | Config du routage (Slack/email/webhook) |

```json
// Alert
{
  "id": "alert_01h...",
  "level": "warn", // "warn" | "info"
  "title": "Schedule drift on Line1",
  "occurredAt": "2026-07-22T13:48:00Z",
  "acknowledged": false
}
```

### 4.11 API Keys

Gestion des clés de `/api-keys` (`src/routes/_authenticated/api-keys.tsx`). **La clé en clair n'est retournée qu'une seule fois**, à la création — le backend ne stocke qu'un hash + préfixe affichable.

| Méthode | Route | Description |
|---|---|---|
| GET | `/api-keys` | Liste (préfixe uniquement, jamais la clé complète) |
| POST | `/api-keys` | Crée une clé `{ name, scopes }` → retourne la clé en clair une fois |
| DELETE | `/api-keys/:id` | Révoque |

```json
// création
POST /api-keys { "name": "ci-readonly", "scopes": ["solvers:read", "schedules:read"] }
// réponse (une seule fois)
{ "id": "key_01h...", "name": "ci-readonly", "secret": "pk_live_9f0e7a2b...", "prefix": "pk_live_9f0e…" }

// GET /api-keys -> liste normale, sans secret
{ "id": "key_01h...", "name": "ci-readonly", "prefix": "pk_live_9f0e…", "createdAt": "...", "lastUsedAt": "..." }
```

### 4.12 Settings (profil & organisation)

`/settings` (`src/routes/_authenticated/settings.tsx`). L'identité (email, nom, prénom) vient déjà de `Utilisateur` (§2) ; le reste (organisation, plan, facturation) est propre au backend métier.

| Méthode | Route | Description |
|---|---|---|
| PATCH | `/me` | Met à jour `{ nom, prenom }` |
| GET | `/organization` | Organisation courante |
| PATCH | `/organization` | Met à jour `{ companyName }` |
| GET | `/organization/billing-portal` | Retourne une URL de redirection (ex. portail Stripe) pour "Gérer la facturation" |

```json
// GET /organization
{ "id": "org_01h...", "companyName": "Acme Manufacturing", "plan": "professional" }
```

## 5. Récapitulatif des variables d'environnement frontend

```
VITE_PRISME_API_URL=http://localhost:8000   # base URL du backend FastAPI (auth + endpoints métier ci-dessus)
```

## 6. Ordre d'implémentation suggéré

1. **Instances + DSL** — CRUD simple, débloque la saisie de contraintes.
2. **Solver Generation + Solvers** — le cœur du produit (pipeline IA).
3. **Validation** — dépend des résultats de génération.
4. **Executions + Schedules** — dépend d'un solveur `active`.
5. **Audit** — peut être alimenté en parallèle dès que 1-4 émettent des événements.
6. **Analytics, Alerts** — agrégations, viennent naturellement après avoir des runs réels.
7. **API Keys, Settings** — indépendants, peuvent être faits à tout moment.

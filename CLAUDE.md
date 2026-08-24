# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PRISME is a PFE (EIGSI Casablanca × BARAA Consult): an API that **generates the code of a
scheduling solver from a business description, then re-executes that frozen code repeatedly**
without calling the AI again. The problem is the **Flexible Job-Shop Scheduling Problem (FJSP)**;
no algorithm is hardcoded — the generation pipeline's Benchmarker agent always runs first and picks
one per instance: `cp_sat` (OR-Tools CP-SAT, the only *exact* one, for small/medium instances) or a
genetic/ACO/tabu/simulated-annealing/dispatching/greedy heuristic for very large ones (Étape 6).
The authoritative spec is
[`PRISME_Note_de_Cadrage (2).md`](<./PRISME_Note_de_Cadrage (2).md>) (French) — source of truth for
every design decision, read before architectural changes. Code comments cite sections as `§N`.

## Commands

Dependency management is **uv** (see `CONTRIBUTING.md` PH0-T2). `.python-version` pins **3.11** —
`ortools` has no wheels for newer CPython (3.14 resolution fails); `uv` downloads 3.11
transparently regardless of system Python. `uv.lock` is the source of truth for exact dependency
versions — regenerate with `uv lock` after any `pyproject.toml` change. Core deps (`ortools`,
`pydantic`, `fastapi`, `pytest`) are pinned `==`; others keep `>=`.

```bash
uv sync --all-extras   # rebuilds the whole environment (downloads Python 3.11 if needed)
uv sync --extra llm    # + anthropic, langchain (multi-agent); uv sync --extra sandbox  # + docker SDK
uv sync --extra estimation                                 # + scikit-learn/numpy (estimation/, MT3)
uv run pytest                                              # full suite (Docker/Postgres tests self-skip if unreachable)
uv run pytest tests/unit                                   # Layer-1 only — no OR-Tools/Docker needed
uv run pytest tests/unit/test_cascade.py::<name> -k <expr> # single test / filter
uv run ruff check . && uv run ruff format --check .        # lint + format check (drop --check to apply)
# Dev scripts (always as modules from repo root, never `python path/to/file.py`):
uv run python -m scripts.generer_banc_synthetique          # regenerate synthetic bench JSON
uv run python -m scripts.mesurer_taux_succes_generation    # single-shot generation success rate (needs .[llm] + creds)
uv run python -m scripts.enregistrer_solveur_reference     # seed solver_store (idempotent)
uv run python -m scripts.demo_bout_en_bout                 # Étape 8 end-to-end demo
uv run uvicorn api.app:app --reload                        # API (docs at /docs), needed by the frontend
docker build -t prisme-sandbox sandbox/container/          # sandbox image (env setup, never automatic)
cd Front/prismatron-solver-forge && npm install && npm run dev  # frontend dev server (TanStack Start, Vite-based)
```

No type-checker configured. Environment variables:
- `PRISME_LLM_PROVIDER` (`mistral` default, or `qwen`|`together`|`nvidia`|`minimax`|`deepseek`) /
  `PRISME_LLM_MODEL` — fallback for single-call paths; `generation/graph.py` instead routes each
  agent to its own provider via `config_fournisseurs.py`, overridable per agent with
  `PRISME_LLM_PROVIDER_<AGENT>` / `_MODEL_<AGENT>` / `_TIMEOUT_SECONDES_<AGENT>`.
- `DATABASE_URL` — Postgres DSN read by `EtatPostgres`/`Registre`; `obtenir_etat()` always builds
  `EtatPostgres` outside tests, which override it with an in-memory `EtatAPI()` instead.
- `JWT_SECRET_KEY`/`JWT_ALGORITHM`/`JWT_EXPIRE_MINUTES` (`api/routes/auth.py`, insecure hardcoded
  default — set outside dev); `PRISME_AUTH_DESACTIVEE=1` disables auth (demo/local only).

`[tool.ruff]` sets `line-length = 115` (wider than 88/100 — French code and docstrings run longer).
CI (`.github/workflows/ci.yml`) runs lint → format check → `pytest` on push/PR; `ubuntu-latest`
runners have Docker preinstalled, so sandbox/bout-en-bout tests actually execute there — **require
the `test` check in `main`'s branch protection**.

**Project stage:** Étapes 1–8 of 9 (§8) implemented (Étape 6 arrived later than originally planned,
see below) plus Phase 10 (frontend, §2.3), out of roadmap order (see Build order). Since PH0-T4 the
full test suite (Docker included) runs and passes — see "Verified" notes below for two real bugs
found and fixed then.

- **Étape 1 — DSL** (`dsl/schema/`): Pydantic v2 — `Tache`, `Ressource`, `Contrainte` (discriminated
  union), `Objectif`s (now configurable — `objectifs_parametrables.py`), `InstanceTRCO` aggregate
  root (cross-axis validation); `Planning`/`OperationPlanifiee` deliberately invariant-free (Étape 2).
- **Étape 2 — feasibility checker** (`validation_engine/feasibility_checker.py`):
  `verifier_faisabilite(instance, planning) -> ResultatFaisabilite`, pure, never raises — every
  anomaly becomes a `Violation`. `CompatibiliteRessourceTache` is mandatory (≥1 per task, enforced by
  `InstanceTRCO`) and carries `duree` per (task, resource), not a fixed `Tache` field (true flexible FJSP).
- **Étape 3 — synthetic bench** (`validation_engine/synthetic_bench/`): `construction_inverse.py`
  builds instances *around* a chosen-optimal `Planning` — each "job" a precedence chain on
  dedicated resources (never shared), so the optimum is provable by arithmetic, no solver needed.
  `catalogue.py` (1→80 tasks), `stockage.py` (JSON); regenerate via `generer_banc_synthetique.py`.
  `scripts/_solveur_minimal.py` is a hand-written CP-SAT solver, a dev/demo/test fixture only —
  never imported by production code.
- **Étape 4 — single-shot generator** (`generation/tentative_unique.py`): one LLM call, no repair
  loop — still used by dev scripts (`generer_solveur_simple.py`, `mesurer_taux_succes_generation.py`)
  for quick/cheap iteration, but no longer what the API calls. `validation_statique.py` is an AST
  **allowlist** (only `ortools`/`dsl`/`collections`/`dataclasses`/`typing`/`__future__`; rejects
  `eval`/`exec`/`__import__`/`open`/dunder escapes) run *before* `executer.py`'s `exec()`, which
  gives no real isolation — **actual sandboxing is Étape 7**.
- **Étape 5 — validation cascade** (`validation_engine/cascade.py`): `evaluer_cascade(solveur)`
  takes any `Callable[[InstanceTRCO], Planning | None]` through, in order: **faisabilité** (every
  instance), **optimalité** (Étape 3 bench vs known optimum), **fidélité** (`reference_cases/`,
  partial comparison). Each instance gets a `DiagnosticInstance` naming which brick failed.
  `stability_test.py` (§6.5): N runs, stable only if every run is legal and hits the same makespan
  (`tester_stabilite.__test__ = False` needed — pytest's `python_functions` bare-matches `"test"`).
- **Étape 6 — bounded repair loop** (`generation/graph.py`), the pipeline wired to the API
  (`api/routes/generation.py`): a LangGraph `StateGraph` — analyste → benchmarker (always runs,
  picks an algorithm; only `cp_sat` is *exact*, the rest of its catalogue are heuristics for very
  large instances, mostly generated inline since `generation/algorithms/` only has a `genetic.py`
  skeleton) → architecte → développeur → testeur → **test_sandbox/validation/debugger loop, max 10
  tentatives** (`MAX_TENTATIVES_REPARATION`) → documentation (best-effort). Each attempt runs the
  Testeur's generated pytest module for real inside the Docker sandbox first (§6.6bis,
  `sandbox/runner.py::executer_tests_dans_sandbox`) — a failure routes straight to the Debugger,
  never blocking if the sandbox itself is unreachable — then the deterministic cascade. Reviewer
  (LLM code critique) is **disabled**: not wired into `_construire_graphe`, its signal being
  redundant once tests run for real in sandbox; `_noeud_reviewer`/`_route_apres_reviewer`/
  `generation/agents/reviewer.py` are untouched and re-wirable in two lines if ever needed. 3
  channels: blocking `POST /{instance_id}`, or `POST /{instance_id}/demarrer` + SSE
  `GET /jobs/{job_id}/stream` (background thread, state in `_JOBS`/`api/etat.py`, survives client
  disconnects). Replaced the earlier `loop.py`/`pipeline_avec_boucle.py`/`pipeline_multi_agents.py`;
  no Orchestrateur (deleted, never routed anything) or Optimiseur (`optimiseur.py` orphaned,
  unreliable JSON-string code) either.
- **Étape 7 — store + ephemeral sandbox** (`solver_store/`, `sandbox/`). `Registre` is
  PostgreSQL-backed (`DATABASE_URL`, migrated from the original SQLite PoC per PH8-T1) — one schema
  per instance; artifacts stay on disk, never duplicated in the DB. **Refuses to register** any
  non-green `VerdictCascade`; re-verifies a SHA-256 hash on retrieval. `sandbox/runner.py` runs a
  frozen artifact in a fresh `--rm` container: no network, read-only rootfs, non-root, CPU/memory/PID
  limits, `no-new-privileges`, force-kill on timeout. The in-container harness has zero dependency on
  `validation_engine/` — both §6.7 guardrails run on the **host**; it registers the loaded module in
  `sys.modules` before `exec_module` (`dataclasses` needs `cls.__module__` resolvable) — **verified
  (PH0-T4):** omitting this crashed every frozen `@dataclass` solver on the first real Docker run.
  `resoudre`'s contract (Phase 2 gap-analysis, `docs/plan_implementation_fonctionnalites_aps.md`)
  is `resoudre(instance, planning_precedent=None, horizon_gele_jours=0) -> Planning | None` — the
  two new params are optional/defaulted so every already-registered solver (9 artifacts at time
  of writing, all still the 1-param signature) keeps working unchanged for a normal execution;
  requesting `horizon_gele_jours>0` against one of them fails explicitly (`sandbox/runner.py::
  _solveur_supporte_horizon_gele`, a pure `ast.parse` of `ArtefactSolveur.code_source`, never an
  exec) rather than silently falling back to a full replan — never automatic regeneration either.
- **Étape 8 — API + adapters** (`api/`, `adapters/`): a multi-tenant surface — **Instance**
  (`api/etat.py`) is the sole primary entity: it owns its own execution/planning history directly
  and is what execution triggers on (**`POST /execution/{instance_id}`**, solver lookup by
  `client_id` + the instance's **exact** constraint-type-signature match). Deleting an instance
  cascade-deletes its own executions/plannings/decisions. **SourceDonnees** (`routes/sources.py`)
  is a separate, deliberately minimal concept: persisted raw data replayable through the
  comprehension agent (`generer-instance`) — it owns no execution history and has no "current
  instance" pointer; `instances_trco.source_id` is pure provenance (`ON DELETE SET NULL`), never a
  delete-guard. Replaces an earlier Projet-owns-instance-as-current-pointer model (removed
  entirely, not just renamed — see git history around the `Projet` → `SourceDonnees` migration for
  the full rationale). Sits above `routes/ingestion.py` (→ `input_validation/`, §6.7 guardrail),
  `routes/execution.py`, `routes/planning.py`/`planifier.py`/`audit.py` (source, explicit request
  only), `routes/auth.py`/`clients.py` (JWT, see env vars above); `adapters/` — see module map
  below. **Verified (PH0-T4):** `demo_bout_en_bout`/`test_api_bout_en_bout.py` run clean end to
  end. Docker/Postgres tests **skip**, not fail, if unreachable (`conftest.py` fixtures).

Codebase is **French** (identifiers, docstrings, domain terms) — match it (`Tache`, `Ressource`,
`faisabilité`...). Commit messages: short imperative French, focusing on *why* over *what* (e.g.,
"Ajoute la vérification de compatibilité ressource-tâche"). Branch naming: `<type>/<sujet-court>`
where type ∈ {`feature/`, `fix/`, `docs/`, `chore/`, `refactor/`}; PR + squash-merge to `main`.

## The founding principle (do not violate)

**Generate once, re-execute many times.** The AI writes solver code a single time, offline, at a
rare event (new client / new constraint structure). Once validated, that code is **frozen**,
persisted (`solver_store/`), and re-run on changing data inside a fresh ephemeral container
(`sandbox/`) — **never regenerated per execution**: *code persists* (performance), *execution is
disposable* (security).

**Human-in-the-loop is non-negotiable.** At every risky decision — triggering a reschedule,
diagnosing a bad plan, a generation failure — the system alerts and *proposes*; a human decides,
never an autonomous action.

## Architecture — data flow

ERP (proprietary) → **adapter** (anti-corruption → canonical T-R-C-O) → **API** → input validation
→ sandbox runs frozen solver → feasibility guardrail → **operational** (planning JSON, every
iteration) / **audit** (solver source, explicit request) output channels.

The **T-R-C-O DSL** (`dsl/`) is exchange format, generation input, and validation frame at once.
Vocabulary is deliberately **finite and typed** to bound the AI's generation surface (§5.3 security
control — `dsl/schema/common.py`'s `Identifiant`). Four axes: **T**âches, **R**essources,
**C**ontraintes (precedence, ressource-task compatibility — *constraints*, not fields on
`Tache`/`Ressource`), **O**bjectifs (configurable, see `objectifs_parametrables.py` — not just makespan).

**`dsl/schema/` conventions:** every model sets `extra="forbid"`; `Contrainte` is a
`Literal["type"]`-discriminated `Union` so new kinds join without touching existing ones;
`InstanceTRCO` enforces per-axis unique IDs and that every constraint references a declared
`Tache`/`Ressource` — that cross-axis check *is* the §6.7 upstream guardrail. **Minimal viable
core:** precedence, ressource-task compatibility, durations. **Optional extensions** (`Contrainte`
subtypes with no effect on an instance that doesn't use them, taught to the generation prompts —
`generation/prompts/generation_solveur.md`/`architecte.md` — and checked by
`feasibility_checker.py`): `Echeance` (deadline in relative days, never a calendar date),
`CompetenceRequise` (task↔resource skill match — can also *derive* `CompatibiliteRessourceTache`
at the ingestion layer only, see `adapters/competence_derivation.py`), `ContrainteCapacite` (a
resource processes up to N operations concurrently — `AddCumulative` in generated CP-SAT code
instead of `AddNoOverlap`; implicit capacity 1, i.e. today's behavior, if absent),
`ContrainteIncompatibilite` (two named tasks can never share a resource, regardless of time —
independent of any temporal overlap check), `ContrainteDisponibiliteRessource` (a resource is
unavailable on listed relative days and/or on a recurring `jours_semaine_indisponibles` weekly
pattern — never a calendar date, converting a real calendar/holiday list to days stays an
adapter's job upstream of ingestion; a global workshop calendar is *not* a separate mechanism,
it's the same constraint declared identically for every resource — in generated CP-SAT code, a
fixed interval per unavailable day added to that resource's own `AddNoOverlap`/`AddCumulative`
list, at full capacity demand), `ContrainteTailleLot` (bound-checks `Tache.quantite` against
`lot_min`/`lot_max` — a static value check, no solver encoding: verified entirely by
`feasibility_checker.py`, never read by generated code), `ContrainteChangementSerie` (setup time: a
directed `ressource`/`tache_avant`/`tache_apres`/`duree_setup` — an extra gap required between the
two only if the solver chooses to sequence them back-to-back on that resource, never an ordering
constraint itself, that stays `Precedence`'s job; generated CP-SAT code encodes it deliberately
**conservatively** via a reified order boolean — the setup gap is enforced whenever `tache_avant`
precedes `tache_apres` in time on the resource at all, not only when strictly adjacent, traded off
against exact `AddCircuit`-based sequencing for LLM-generation reliability). `Tache.priorite`
(1–5) is consumed by generated code as a **tie-break only** — never a weight on the primary
objective, never a constraint — see "Priorité des tâches" in `generation_solveur.md`.
`Tache.statut`/`Ressource.type` remain purely informative fields (no constraint or objective reads
them).

Order intake also feeds the DSL indirectly: `adapters/commande_derivation.py` derives `Echeance`
constraints from `Commande` (id, tasks, client, deadline) objects — explicit `Echeance` always
wins over a derived one, tightest deadline wins when a task belongs to several commandes; wired
into the CSV/JSON adapters, never a DSL-level concept itself. Separately, `groupe_scenario_id` (a
self-referencing FK on `instances_trco`, `ON DELETE SET NULL`) lets several what-if instance
variants be grouped for side-by-side comparison (`POST/GET .../scenarios`,
`api/comparaison_scenarios.py`) — unrelated to the removed `instance_parente_id` lineage concept
and to `SourceDonnees`; purely an API/storage-layer grouping, never touches the DSL.

## Module map

| Module | Role |
|---|---|
| `dsl/` | T-R-C-O canonical model: typed `schema/`, payload `validation/`, `examples/` |
| `generation/` | `tentative_unique.py` (legacy single-shot) + `graph.py` (production: LangGraph multi-agent + bounded repair, Étape 6) → CP-SAT or heuristic code; `algorithms/` catalogue mostly unimplemented |
| `validation_engine/` | Validation cascade + `stability_test.py` |
| `solver_store/` + `sandbox/` | Persistent registry (`registry.py`) + frozen `artifacts/`; ephemeral disposable-container execution (`runner.py`, `container/`) |
| `api/` | `auth`/`clients` (JWT, multi-tenant), `sources`/`ingestion`/`adapters`, `generation` (SSE), `execution`/`planning`/`planifier`/`audit`/`validation`/`diagnostics`/`supervision`; state via `etat.py` (in-memory, tests) or `etat_postgres.py` (prod), same interface |
| `adapters/` | ERP anti-corruption layer: `erp_reference/` (PoC), `greensig/` (real ERP), `tableur/`/`csv_import/`/`json_import/` (xlsx/CSV/JSON; the latter two can derive `CompatibiliteRessourceTache` from declared competences + an estimated duration instead of it being hand-typed, shared logic in `competence_derivation.py`, now optionally backed by `estimation/`), `agent_comprehension/` (LLM-proposed mapping, never trusted directly) |
| `estimation/` | MT3 (load/duration estimation) implemented: `EstimateurDuree` (scikit-learn `GradientBoostingRegressor`) predicts a task's duration from task/resource traits, trained on **synthetic** data (`historique_synthetique()`, mirrors `validation_engine/synthetic_bench/`) — no real observed-duration data exists anywhere in PRISME yet (see `docs/perspective_estimation_charge.md`). Wired into `csv_import`/`json_import` via an optional `estimateur_duree` param (`competence_derivation.py::completer_durees_par_estimation`); `traduire()` in both now returns `ResultatTraduction(instance, avertissements)` instead of a bare `InstanceTRCO` — every ML-filled duration surfaces as an explicit avertissement, never silently trusted (§FC4). Extra: `uv sync --extra estimation`. |
| `Front/prismatron-solver-forge/` | TanStack Start + React + TS + Tailwind — auth, clients, instances, solver-generator (SSE), execution, schedules, analytics |
| `tests/` | `unit/`, `integration/` only — no separate property-based/generation-stability suites (see below) |
| `docs/` | Substantial by now: agent pipeline (`agents_utilises.md`, `agents_fonctionnement_detaille.md`, `schema_agents.md`), `boucle_reparation.md`, DSL nomenclature |
| `scripts/` | Dev env, synthetic-bench generation, CI tasks, `_solveur_minimal.py` (dev/demo/test fixture); LangSmith for LLM-call observability, no custom metrics stack |

## Validation & testing philosophy (§6)

Non-deterministic generated code is **not** tested like hand-written code: **Layer 1** hand-written
code gets classic unit/integration tests (`tests/unit/`, `tests/integration/`); **Layer 2** the
generated solver is judged on **properties of the planning it produces** via the cascade
(`validation_engine/cascade.py`), not a dedicated `tests/property_based/` (never built); **Layer 3**
the generation itself is tested by running the same DSL N times and checking plans are equivalent
— `validation_engine/stability_test.py` + `tests/unit/test_stability.py`, no dedicated
`tests/generation_stability/` either.

The generate-test-repair loop (`generation/graph.py`, §6.6) stays **bounded** (10 attempts, then
honest failure to a human), **offline**, and **diagnostic** (names which constraint is violated).
The diagnostic loop (`diagnostics/`) attributes cause in a fixed order before acting: code fault
(synthetic ground truth) → corrupt data (feasibility) → wrong DSL spec (reference cases). Never
"improve" healthy code for bad data.

## Security posture

Executing AI-generated code is risk #1 (§5.3), above auth/encryption. Three layers, all implemented:
ephemeral sandbox (Étape 7, real isolation), static AST-allowlist (Étape 4, weaker, never a
substitute), DSL-bounded generation surface (`Identifiant`) — preserve all three when touching
`generation/`/`sandbox/`/`solver_store/` (`test_sandbox_securite.py` proves the sandbox holds alone).

## Build order (roadmap §8, dependency-ordered)

DSL → feasibility checker → synthetic bench → single-shot generator → validation cascade →
generate-test-repair loop → store + sandbox → API + ERP adapter → dashboard (`docs/roadmap.md` TBD).

**Actual order deviates:** cascade (Étape 5) was built and made green *before* the generator
(Étape 4) — it only needs a `Callable[[InstanceTRCO], Planning | None]`, a hand-written solver
stood in as candidate. **Étape 8 was built ahead of Étape 6** — `/execution` only needed *some*
validated solver (`enregistrer_solveur_reference.py`); Étape 6 arrived later still, as a full
LangGraph rewrite (`generation/graph.py`) that replaced the single-agent path wired to the API.

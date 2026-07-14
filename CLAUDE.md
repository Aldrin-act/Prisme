# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PRISME is a PFE (EIGSI Casablanca × BARAA Consult): an API that **generates the code of a
scheduling solver from a business description, then re-executes that frozen code repeatedly**
without calling the AI again. The scheduling problem is the **Flexible Job-Shop Scheduling
Problem (FJSP)**, solved with **OR-Tools CP-SAT**.

The authoritative spec is [`PRISME_Note_de_Cadrage (2).md`](<./PRISME_Note_de_Cadrage (2).md>)
(French). It is the source of truth for every design decision — read it before making
architectural changes. Code comments reference its sections as `§N` (e.g. `§5.2`, `§6.7`); keep
that convention and cite the section a piece of code implements.

## Commands

Dependency management is **uv** (not pip/Poetry directly — see `CONTRIBUTING.md` PH0-T2 for why).
`.python-version` pins the interpreter to **3.11** — `ortools` does not yet publish wheels for
newer CPython versions (verified: resolution against system Python 3.14 fails; 3.11 works), so
`uv` transparently downloads and uses 3.11 regardless of the system Python. `uv.lock` is the
single source of truth for exact (including transitive) dependency versions — commit it, and
regenerate with `uv lock` after any `pyproject.toml` dependency change. Core dependencies
(`ortools`, `pydantic`, `fastapi`, `pytest`) are pinned with `==` in `pyproject.toml` itself, per
PH0-T2; other deps keep `>=` bounds.

Run everything from the repo root. `pyproject.toml` sets `pythonpath = ["."]`, so tests and
`python -m` scripts resolve the packages without an install once the environment is synced.

```bash
uv sync --all-extras   # the one command that rebuilds the whole environment (downloads Python 3.11 if needed)
uv sync                # core deps only, no extras
uv sync --extra llm    # + anthropic, openai (needed only to actually call the generator)
uv sync --extra sandbox  # + docker SDK (needed only for sandboxed execution)

uv run pytest                                              # full suite (Docker tests self-skip if unreachable)
uv run pytest tests/unit                                   # Layer-1 tests only — no OR-Tools/Docker needed
uv run pytest tests/integration/test_solveur_reference.py  # a single file
uv run pytest tests/unit/test_cascade.py::<name> -k <expr> # a single test / filter

# Dev scripts (all run as modules from the repo root, never `python path/to/file.py`):
uv run python -m scripts.generer_banc_synthetique          # regenerate synthetic bench JSON after bench changes
uv run python -m scripts.benchmarker_solveur_reference     # reference solver: makespan-vs-optimum + solve time
uv run python -m scripts.mesurer_taux_succes_generation    # measure single-shot generation success (needs .[llm] + creds)
uv run python -m scripts.enregistrer_solveur_reference     # seed solver_store with the reference solver (idempotent)
uv run python -m scripts.demo_bout_en_bout                 # Étape 8 end-to-end demo (adapter→ingestion→execution→planning→audit)

uv run uvicorn api.app:app --reload                        # run the API (docs at /docs)
docker build -t prisme-sandbox sandbox/container/          # build the sandbox image (env setup, never done by app code)
```

Known issue found while verifying this section: `uv run pytest tests/unit` errors on
`tests/unit/test_stability.py` — pytest's default `test*` collection glob matches the imported
`tester_stabilite` function (no `test_` prefix guard) and tries to collect it as a test, failing
on a missing `solveur` fixture. Pre-existing, unrelated to environment setup; not yet fixed.

There is **no configured linter/formatter/type-checker** — don't invent a `ruff`/`black`/`mypy`
command. LLM provider/model are selected via `PRISME_LLM_PROVIDER` (`anthropic`|`openai`) and
`PRISME_LLM_MODEL` env vars.

**Project stage:** early scaffolding, Étapes 1–5, 7, and 8 of 9 (§8) implemented (out of the
roadmap's own order — see Build order below; Étape 6, the bounded repair loop, is deliberately
skipped so far), plus one hand-written step the roadmap doesn't list. Every module directory
besides `dsl/`, `validation_engine/`, `solveur_reference/`, `generation/`, `solver_store/`,
`sandbox/`, `adapters/`, and `api/` currently holds only a `README.md` describing its intended
contents.

- **Étape 1 — DSL** (`dsl/`): `schema/` — typed Pydantic v2 models for the minimal core (`Tache`,
  `Ressource`, `Contrainte` as a `precedence`/`compatibilite_machine_tache` discriminated union,
  `MinimiserMakespan`, `InstanceTRCO` as the aggregate root with cross-axis referential validation,
  and `Planning`/`OperationPlanifiee` — the solver's output shape, deliberately a dumb container
  with no invariants of its own; see below on why). `validation/` — `charger_instance`, the entry
  point that will back `api/input_validation/`. `examples/{valid,invalid}/` — hand-written
  payloads, one invalid example per rejection rule.
- **Étape 2 — feasibility checker** (`validation_engine/feasibility_checker.py`):
  `verifier_faisabilite(instance, planning) -> ResultatFaisabilite` — pure, deterministic, never
  raises. Every anomaly (the three legality rules plus the structural ones needed to make them
  well-defined: unknown task/resource reference, task missing or duplicated in the planning)
  becomes a `Violation` in `ResultatFaisabilite.violations`; this is *why* `Planning` has no
  pydantic-level invariants — a production guardrail (§6.7) needs one uniform reporting path, not
  "sometimes an exception, sometimes a violation object" depending on which rule fired. Design
  choice worth knowing: a task with **no** `CompatibiliteMachineTache` constraint is unrestricted
  (compatible with any declared resource) — constraints are restrictions, so absence of one imposes
  none.
- **Étape 3 — synthetic bench** (`validation_engine/synthetic_bench/`): `construction_inverse.py`
  builds an instance *around* a chosen-optimal `Planning`, never the other way round. Scheme: each
  "job" is a precedence chain on resources dedicated to it alone (never shared across jobs), so
  machine-task compatibility is forced (one legal resource per task, no routing choice). That
  makes optimality provable by pure arithmetic, not by running a solver — a precedence chain can't
  finish faster than the sum of its durations, jobs never contend for a resource, and the
  constructed schedule already hits that sum with zero idle time. `catalogue.py` holds the
  versioned "tailles croissantes" list (1 → 80 tasks); `stockage.py` (de)serializes to/from
  `instances/*.json`, the checked-in catalogue; `scripts/generer_banc_synthetique.py` regenerates
  those files after any change to `construction_inverse.py` or the catalogue. A task can revisit
  the same dedicated resource more than once in its chain (when `n_ressources < n_taches`) — the
  one place this bench actually exercises the Étape 2 checker's overlap rule.
- **Reference solver — not in the roadmap, done before Étape 4 on purpose** (`solveur_reference/`):
  `resoudre(instance) -> ResultatResolution` is a hand-written OR-Tools CP-SAT model of the minimal
  core (classic FJSP formulation: one optional interval per task/compatible-resource pair,
  exactly-one-resource-chosen, per-resource `NoOverlap`, precedence between actual start/end times,
  minimize the max end time). It exists to (1) prove the core is actually solvable and calibrate
  performance before trusting AI-generated code to do the same, and (2) become the fidelity target
  (§6.2 brique 3) the generated solver will later have to match. Never touched by `generation/` or
  `solver_store/` — it's permanent hand-written code living outside the "generate once" cycle, on
  purpose. **Keep its compatibility semantics synchronized with
  `validation_engine/feasibility_checker.py`**: a task with no `CompatibiliteMachineTache`
  constraint is unrestricted in both places, by the same reasoning — if they ever disagree, the
  solver could produce something the checker calls illegal, or vice versa.
  `scripts/benchmarker_solveur_reference.py` reports makespan-vs-optimum and solve time across the
  Étape 3 catalogue.
- **Étape 4 — single-shot generator** (`generation/`), built *after* Étape 5 in practice (see Build
  order): one LLM call, no repair loop yet (that's Étape 6). `agents/client_llm.py` picks the
  provider/model from `PRISME_LLM_PROVIDER`/`PRISME_LLM_MODEL` env vars (default Anthropic) — a
  deliberate choice so this project isn't locked to one vendor; the corresponding SDK is an optional
  extra (`pip install -e .[llm]`), imported lazily so installing one doesn't require the other.
  `agents/generateur.py` sends `prompts/generation_solveur.md` and extracts the returned code.
  `validation_statique.py` is an AST-based **allowlist** gate (only `ortools`, `dsl`, `collections`,
  `dataclasses`, `typing`, `__future__` prefixes; `eval`/`exec`/`__import__`/`open`/etc. and
  dunder-attribute sandbox-escape patterns all rejected) that runs *before* `executer.py` ever calls
  `exec()` on generated code — but `exec()` itself gives no real isolation; **the actual sandboxing
  is still Étape 7**, not this. Never treat `executer.py` as safe for untrusted code outside a
  controlled dev environment. `tentative_unique.py` chains generate → static-validate → execute →
  judge-by-the-Étape-5-cascade into one `ResultatTentative`, swallowing any runtime exception from
  the generated code so one bad attempt can't crash a whole measurement run.
  `scripts/mesurer_taux_succes_generation.py` runs N such attempts and reports the raw success
  rate — deliberately not a threshold to hit yet, just a starting-point measurement.
- **Étape 5 — validation cascade** (`validation_engine/cascade.py`): `evaluer_cascade(solveur)`
  takes *any* candidate solver — a `Callable[[InstanceTRCO], Planning | None]`, so the reference
  solver and the future generated code plug in identically — and runs it through the three bricks
  in the order §6.3 requires, since each depends on the previous one: **faisabilité** (Étape 2, on
  every instance touched), **optimalité** (Étape 2 checker's result *plus* makespan-vs-known-optimum,
  but only on the Étape 3 bench — the only place an optimum is proven), and **fidélité** (Étape 2
  checker's result *plus* comparison against a hand-written expected planning, but only on
  `reference_cases/` — the only place a human has validated one specific answer). Comparison for
  fidelity is deliberately partial: same task→resource assignment and same makespan as expected, not
  strict timing equality, since multiple differently-timed schedules can be equally valid. Each
  instance gets a `DiagnosticInstance` naming exactly which brick failed and why — never a bare
  pass/fail. `reference_cases/cases/*.json` holds two hand-written (instance, expected planning)
  pairs; `choix_ressource_attendu.json` is built around a genuine optimality trade-off (one task's
  resource choice measurably changes the achievable makespan) rather than a symmetric tie, precisely
  so the expected answer is forced and doesn't depend on a solver's internal tie-breaking.
  `stability_test.py` implements §6.5: run the same solver N times on the same instance, and it's
  stable only if every run is legal (Étape 2) and every run hits the same makespan.
- **Étape 7 — store + ephemeral sandbox** (`solver_store/`, `sandbox/`), skipping Étape 6 (the
  bounded repair loop) on purpose, at your explicit direction. `solver_store/registry.py`'s
  `Registre` is SQLite-backed (your choice over PostgreSQL — no DB server or Docker exists in the
  environment that built this, so nothing here has actually run; see caveats). It **refuses to
  register** any solver whose `VerdictCascade` isn't green — the store can never hold code that
  hasn't cleared Étape 5 — and re-verifies a SHA-256 hash on every retrieval, so a tampered/corrupted
  "frozen" file on disk is caught, not silently executed. `sandbox/runner.py`'s
  `executer_dans_sandbox` runs a frozen artifact via the `docker` SDK (extra `sandbox`, imported
  lazily — `import sandbox` never requires Docker to be installed) in a **fresh, `--rm`** container
  built from `sandbox/container/Dockerfile`: `network_mode="none"`, read-only rootfs, non-root user
  (uid 10001, baked into the image), CPU/memory/PID limits, `no-new-privileges`, and a wait-timeout
  that force-kills+removes the container on expiry. The harness that runs *inside* the container
  (`sandbox/container/executer_dans_conteneur.py`) has zero dependency on `validation_engine/` —
  both §6.7 guardrails (input validation upstream, feasibility downstream) run on the **host**,
  never inside the container. `executer_solveur_valide` chains registry lookup → sandboxed execution
  → the Étape 2 feasibility guardrail into one `ResultatExecution`, matching the Étape 7 validation
  criterion end to end. The image is never built automatically by application code — building an
  image is environment setup, not a solver execution, and conflating the two would blur the
  "generate once, execute many times" boundary this whole architecture protects.
- **Étape 8 — API + ERP adapter** (`api/`, `adapters/erp_reference/`). `api/app.py` wires four
  routers into one `FastAPI()` (OpenAPI docs free at `/docs`): `routes/ingestion.py` (validates via
  `api/input_validation/`, which just wraps `dsl.validation.charger_instance` in an `HTTPException`
  — the §6.7 upstream guardrail, one entry point regardless of transport, exactly as promised back
  in Étape 1), `routes/execution.py` (looks up a validated solver in `solver_store/registry.py` by
  `client_id` + **exact** constraint-type-signature match — see `api/etat.structure_contraintes`;
  a solver registered for `"precedence,compatibilite_machine_tache"` will *not* be found for an
  instance using only one of those two, even though the same general-purpose solver could handle
  it — this is a deliberate, literal reading of "structure de contraintes" from the module map, not
  an oversight), then calls `sandbox.executer_solveur_valide`, `routes/planning.py` (operational
  channel, JSON planning only), and `routes/audit.py` (solver source code, **only** on this explicit
  route, never mixed into the operational response). `api/etat.py` is deliberately a bare in-memory
  dict-backed store for demo wiring between routes — not a real job queue/DB, which is out of scope
  for the minimal core; the only durable persistence in the whole system is still `solver_store/`.
  `api/dependencies.py`'s `obtenir_registre()` points at the *real* default `solver_store/` location
  at import time (correct for production use) — tests must override it via
  `app.dependency_overrides` or they'd touch the real store; see `tests/integration/conftest.py`'s
  pattern, reused in every API test file. `adapters/erp_reference/` is the anti-corruption layer:
  `schema_erp.py` defines a **deliberately poorer, differently-named** simulated legacy format
  (`PayloadERP`/`OperationERP`/`PosteERP` — single forced machine per operation, no flexible
  routing, unlike T-R-C-O which can express it) with its own field-mapping table in
  `mapping/regles.md`; `translator.py`'s `traduire()` is the one-way conversion into `InstanceTRCO`.
  `scripts/enregistrer_solveur_reference.py` seeds the store with the reference solver (idempotent —
  safe to call repeatedly) by **re-running the full Étape 5 cascade** first, refusing to register on
  anything less than green; `scripts/demo_bout_en_bout.py` chains adapter → ingestion → execution →
  planning → audit into the Étape 8 validation criterion, using `fastapi.testclient.TestClient`
  (no real port binding needed) — run it with `python -m scripts.demo_bout_en_bout` from the repo
  root, **not** `python scripts/demo_bout_en_bout.py` directly (see the module docstring: it
  cross-imports `scripts.enregistrer_solveur_reference`, which only resolves if the repo root is on
  `sys.path`, which only `-m` or an editable install guarantees — `scripts/` is a real installable
  package now, in `pyproject.toml`'s wheel list, specifically so this cross-import works).

`pyproject.toml` establishes the tooling (Pydantic v2 + `ortools` + `fastapi` + `httpx` + pytest,
plus optional extras `llm`, `sandbox`, and `uvicorn` under `dev`);
`tests/unit/test_dsl_schema.py`, `tests/unit/test_feasibility_checker.py`,
`tests/unit/test_synthetic_bench.py`, `tests/unit/test_cascade.py`, `tests/unit/test_stability.py`,
`tests/unit/test_registry.py`, and `tests/unit/test_erp_adapter.py` are the Layer 1 (§6.1) proof of
their respective validation criteria and need neither OR-Tools execution nor Docker — the
synthetic-bench test also recomputes each catalogue entry's optimum independently (via the
precedence chains alone) rather than trusting the generator's own bookkeeping, and checks the
versioned JSON files haven't drifted from what the generator currently produces; `test_cascade.py`
proves the cascade's layered diagnosis using two deliberately-buggy pure-Python stub solvers (no
OR-Tools needed for these) — one that ignores precedence (caught at *faisabilité*) and one that's
fully correct on the bench but picks the wrong resource on `choix_ressource_attendu.json` (passes
*faisabilité* and *optimalité*, caught only at *fidélité*). `tests/integration/test_solveur_reference.py`
and `test_cascade_solveur_reference.py` close the loop with the real OR-Tools solver: it must
reproduce the known optimum on every bench entry, its output must itself pass the Étape 2 checker,
and it must clear the full cascade. `tests/integration/test_api_ingestion.py` exercises the API
without Docker (ingestion never touches the sandbox). `tests/integration/test_sandbox_execution.py`,
`test_sandbox_securite.py`, and `test_api_bout_en_bout.py` need Docker — a session fixture in
`tests/integration/conftest.py` builds the image and **skips** (not fails) if Docker isn't
reachable; the security tests feed hand-written malicious code (network exfiltration attempt, write
outside the read-only rootfs) directly to `executer_dans_sandbox`, deliberately bypassing
`generation/validation_statique.py`'s AST gate, to prove the *container* isolation itself holds
independent of that earlier layer (defense in depth, §5.3). Run tests with `pytest` from the repo
root.

The codebase is written in **French** (identifiers, docstrings, comments, domain terms). Match it —
use `Tache`, `Ressource`, `Contrainte`, `Objectif`, `faisabilité`, `planning`, etc.

## The founding principle (do not violate)

**Generate once, re-execute many times.** The AI writes solver code a single time, offline, at a
rare event (new client / new constraint structure). Once validated, that code is **frozen**,
persisted (`solver_store/`), and re-run on changing data inside a fresh ephemeral container
(`sandbox/`) — **never regenerated per execution**. Any design that calls the AI on each
scheduling run breaks the core innovation. Two independent layers: *code persists* (performance),
*execution is disposable* (security).

**Human-in-the-loop is non-negotiable.** At every risky decision — triggering a reschedule,
diagnosing a bad plan, a generation failure — the system alerts and *proposes*; a human decides.
Never design autonomous action at these points.

## Architecture — data flow

ERP (proprietary format) → **adapter** (anti-corruption, translates to canonical T-R-C-O) →
**API** → input validation → sandbox runs frozen solver from the store → feasibility guardrail →
two output channels: **operational** (planning JSON, every iteration) and **audit** (solver source
code, on explicit request only).

The **T-R-C-O DSL** (`dsl/`) is the contract between business and machine and plays three roles at
once: exchange format with ERPs, generation input for the AI, and validation frame. Its vocabulary
is deliberately **finite and typed** to bound the AI's generation surface (a security control,
§5.3) — see `dsl/schema/common.py` where `Identifiant` is a length- and alphabet-constrained
string. Four axes: **T**âches (operations/durations), **R**essources (machines/compatibility),
**C**ontraintes (rules: precedence, machine-task compatibility, later preemptibility &
reschedule-scope), **O**bjectifs (makespan, load balancing, deadlines).

**Axis placement rule:** precedence relations and machine-task compatibility are *constraints*
(axis C), not fields on `Tache` or `Ressource`. A `Tache` holds only its own attributes (id,
duration); relationships live in `Contrainte`.

**Established `dsl/schema/` conventions (follow these when extending the DSL):** every model sets
`model_config = ConfigDict(extra="forbid")`; `Contrainte` is a `Literal["type"]`-discriminated
`Union` (see `contraintes.py`) so new constraint kinds join the union without touching existing
ones; `InstanceTRCO` (`instance.py`) is the aggregate root — it enforces per-axis unique
identifiers and that every constraint references a `Tache`/`Ressource` actually declared in the
instance. That cross-axis check *is* the upstream guard-rail described in §6.7 — `dsl/validation/`
just exposes it as `charger_instance()`, the entry point `api/input_validation/` will call once it
exists.

**Minimal viable core (in scope):** precedence, machine-task compatibility, durations. Everything
else (sequence-dependent setup times, resource calendars, client priorities/due dates, capacity)
is explicitly **out of the initial scope** — the DSL and architecture are designed to accept them
later without redesign, but do not implement them into the core. Guard against scope creep: the
proof rests on one small core mastered end-to-end.

## Module map

| Module | Role |
|---|---|
| `dsl/` | T-R-C-O canonical model: typed `schema/`, payload `validation/`, `examples/` |
| `generation/` | Multi-agent generate-test-repair loop → CP-SAT code (`agents/`, `loop.py`, `prompts/`, `failures/`) |
| `validation_engine/` | Validation cascade (see order below) + `stability_test.py` |
| `solveur_reference/` | Not in the roadmap: hand-written CP-SAT solver, permanent, outside the generate-once cycle — fidelity target for `generation/` |
| `solver_store/` | Persistent registry (`registry.py`) + frozen `artifacts/` |
| `sandbox/` | Ephemeral disposable-container execution (`runner.py`, `container/`) |
| `api/` | Routes: `ingestion`, `execution`, `planning` (operational), `audit`; `input_validation/` |
| `adapters/` | ERP anti-corruption layer; one real adapter `erp_reference/` for the PoC |
| `diagnostics/` | Cause attribution before improvement (`attribution.py`) |
| `dashboard/` | Human alerting, reschedule trigger, plan validation |
| `tests/` | `unit/`, `integration/`, `property_based/`, `generation_stability/` |
| `docs/` | `architecture/`, `dsl/` spec (next priority), `roadmap.md` |
| `scripts/` | Dev env, synthetic-bench generation, CI tasks |

## Validation & testing philosophy (§6)

Non-deterministic generated code is **not** tested like hand-written code. Three layers:

- **Layer 1** — hand-written code (API, adapters, orchestration): deterministic, classic
  unit/integration tests → `tests/unit/`, `tests/integration/`.
- **Layer 2** — the AI-generated solver: you cannot test code you haven't seen, so test the
  **properties of the planning it produces**, not the code text → `tests/property_based/`.
- **Layer 3** — the generation itself: non-deterministic; tested *through* layer 2 by running the
  same DSL N times and checking the plans are equivalent → `tests/generation_stability/`.

The **validation cascade** in `validation_engine/` is built strictly in this order because each
brick depends on the previous one:

1. **Feasibility checker** — is the plan *legal*? (no precedence violation, no double-booked
   machine, no incompatible resource). Written once, deterministic, the highest-ROI test. Used
   **twice**: offline in code validation *and* online as a production guardrail (§6.7).
2. **Synthetic bench** — is the plan *good*? Instances with known ground truth via **inverse
   construction** (pick an optimal plan → build the instance around it, so the optimum is known
   for free — critical because FJSP is NP-hard and computing optima directly doesn't scale).
3. **Reference cases** — does the plan solve the *right* problem? Hand-written (DSL + expected
   plan) pairs for semantic fidelity (catches "A before B" translated as "B before A").

Implemented as `validation_engine.cascade.evaluer_cascade` — see the Étape 5 bullet above for the
solver interface and the per-instance diagnostic shape it returns.

The generate-test-repair loop (`generation/`) must stay **bounded** (max attempts, then honest
failure to a human), **offline** (runs at generation, never per execution), and **diagnostic**
(the tester says *which constraint is violated*, not just "wrong").

The diagnostic improvement loop (`diagnostics/`) attributes cause in a fixed order before acting:
code fault (test on synthetic ground truth) → corrupt data (feasibility) → wrong DSL spec
(reference cases). Never "improve" healthy code in response to bad data.

## Security posture

Executing AI-generated code is risk #1 (§5.3), above auth/encryption. Defense in layers, all three
now implemented: ephemeral sandbox with restricted privileges & network (`sandbox/runner.py` +
`sandbox/container/`, Étape 7 — no network, read-only rootfs, non-root, resource limits, real
isolation), static validation of generated code before running (`generation/validation_statique.py`,
Étape 4 — an AST allowlist, weaker than the sandbox and never a substitute for it), and DSL-bounded
generation surface (`dsl/schema/common.py`'s `Identifiant`). Preserve all three when touching
`generation/`, `sandbox/`, or `solver_store/` — and don't mistake the static-validation layer alone
for a safe execution boundary; `generation/executer.py` says so explicitly in its own docstring, and
`tests/integration/test_sandbox_securite.py` deliberately bypasses the AST gate to prove the sandbox
holds on its own.

## Build order (roadmap §8, dependency-ordered)

DSL → feasibility checker → synthetic bench → single-shot generator → validation cascade →
generate-test-repair loop → store + sandbox → API + ERP adapter → dashboard. Each step depends on
the earlier ones; `docs/roadmap.md` is meant to track progress but doesn't exist yet — create it
when starting the roadmap work. The **detailed T-R-C-O DSL spec** is the declared next priority
(§9). The hand-written reference solver (`solveur_reference/`) slots in between synthetic bench and
single-shot generator, even though the roadmap doesn't name it as a step. **Note the actual build
order deviates from this list**: the validation cascade (Étape 5) was implemented and made green
*before* Étape 4 (the AI single-shot generator) existed — `validation_engine/cascade.py` was
written and tested against the hand-written reference solver standing in as "a candidate solver,"
since `evaluer_cascade` only needs something matching `Callable[[InstanceTRCO], Planning | None]`,
not specifically AI-generated code. Étape 4 (`generation/`) now exists too and plugs into the exact
same cascade unchanged, as designed — but its own single-shot success rate against that cascade has
never actually been measured (no LLM credentials in the environment that built it); running
`scripts/mesurer_taux_succes_generation.py` for the first time is real, not-yet-done work. **Étape 6
(the bounded generate-test-repair loop) was skipped entirely, at explicit direction**, jumping
straight to Étape 7 (`solver_store/` + `sandbox/`) — there is no `generation/loop.py` and no
`generation/failures/` yet. `solver_store.registry.Registre.enregistrer_solveur` currently expects
to be handed a `VerdictCascade` directly (e.g. from a manual `evaluer_cascade` call, as in
`tests/integration/test_sandbox_execution.py`); when Étape 6 eventually lands, its loop is the
natural caller of `enregistrer_solveur` on success. None of `solver_store/` or `sandbox/` has
actually been run anywhere — this session's environment has neither Python, nor Docker, nor a
database; every line here is reasoned through carefully but genuinely unverified. Treat first real
runs of `pytest tests/integration/test_sandbox_*.py` (with Docker available) as the true test of
this step, not this implementation's existence. **Étape 8 (`api/`, `adapters/erp_reference/`) was
built next, ahead of Étape 6 in the roadmap's own order — same reasoning as Étape 5 before it: the
API and adapter only need *some* validated solver behind `/execution`, and
`scripts/enregistrer_solveur_reference.py` supplies exactly that by re-running the Étape 5 cascade
on the hand-written reference solver.** When Étape 6 eventually lands, its bounded loop becomes the
real-world producer of what that seeding script fakes today. Same verification caveat as Étape 7:
nothing in `api/` or `adapters/` has actually been run — no Python, no Docker, no live LLM in the
environment that wrote it. Running `python -m scripts.demo_bout_en_bout` (or
`pytest tests/integration/test_api_bout_en_bout.py`) for the first time is real, not-yet-done
verification work, not a formality.

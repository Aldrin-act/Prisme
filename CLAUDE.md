# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.Must stay at 200 lines 

## What this is

PRISME is a PFE (EIGSI Casablanca × BARAA Consult): an API that **generates the code of a
scheduling solver from a business description, then re-executes that frozen code repeatedly**
without calling the AI again. The scheduling problem is the **Flexible Job-Shop Scheduling
Problem (FJSP)**, solved with **OR-Tools CP-SAT**.

The authoritative spec is [`PRISME_Note_de_Cadrage (2).md`](<./PRISME_Note_de_Cadrage (2).md>)
(French) — source of truth for every design decision, read it before architectural changes. Code
comments cite its sections as `§N`; keep that convention.

## Commands

Dependency management is **uv** (see `CONTRIBUTING.md` PH0-T2). `.python-version` pins **3.11** —
`ortools` has no wheels for newer CPython (3.14 resolution fails); `uv` downloads 3.11
transparently regardless of system Python. `uv.lock` is the source of truth for exact dependency
versions — regenerate with `uv lock` after any `pyproject.toml` change. Core deps (`ortools`,
`pydantic`, `fastapi`, `pytest`) are pinned `==`; others keep `>=`.

```bash
uv sync --all-extras   # rebuilds the whole environment (downloads Python 3.11 if needed)
uv sync --extra llm    # + anthropic, openai; uv sync --extra sandbox  # + docker SDK
uv run pytest                                              # full suite (Docker tests self-skip if unreachable)
uv run pytest tests/unit                                   # Layer-1 only — no OR-Tools/Docker needed
uv run pytest tests/unit/test_cascade.py::<name> -k <expr> # single test / filter
uv run ruff check . && uv run ruff format --check .        # lint + format check (drop --check to apply)
# Dev scripts (always as modules from repo root, never `python path/to/file.py`):
uv run python -m scripts.generer_banc_synthetique          # regenerate synthetic bench JSON
uv run python -m scripts.benchmarker_solveur_reference     # makespan-vs-optimum + solve time
uv run python -m scripts.mesurer_taux_succes_generation    # single-shot generation success rate (needs .[llm] + creds)
uv run python -m scripts.enregistrer_solveur_reference     # seed solver_store (idempotent)
uv run python -m scripts.demo_bout_en_bout                 # Étape 8 end-to-end demo
uv run uvicorn api.app:app --reload                        # API (docs at /docs), needed by the dashboard
docker build -t prisme-sandbox sandbox/container/          # sandbox image (env setup, never automatic)
cd dashboard && npm install && npm run dev                 # dashboard dev server, :5173 (Node via nvm, no sudo)
```

No type-checker configured. `PRISME_LLM_PROVIDER` (`anthropic`|`openai`) / `PRISME_LLM_MODEL`
select the generation LLM. `[tool.ruff]` sets `line-length = 115` (wider than 88/100 — French code
and docstrings run longer). CI (`.github/workflows/ci.yml`) runs lint → format check → `pytest` on
push/PR; `ubuntu-latest` runners have Docker preinstalled, so sandbox/bout-en-bout tests actually
execute there — require this check in `main`'s branch protection.

**Project stage:** Étapes 1–5, 7, 8 of 9 (§8) implemented plus Phase 10 (dashboard, §2.3) from the
dev plan, out of roadmap order (see Build order). Étape 6 (bounded repair loop) deliberately
skipped so far. Since PH0-T4 the full test suite (Docker included)
actually runs and passes — see "Verified" notes below for two real bugs found and fixed then.

- **Étape 1 — DSL** (`dsl/schema/`): Pydantic v2 — `Tache`, `Ressource`, `Contrainte` (discriminated
  union), `MinimiserMakespan`, `InstanceTRCO` aggregate root (cross-axis validation),
  `Planning`/`OperationPlanifiee` deliberately invariant-free (see Étape 2 for why).
  `validation/charger_instance` backs `api/input_validation/`.
- **Étape 2 — feasibility checker** (`validation_engine/feasibility_checker.py`):
  `verifier_faisabilite(instance, planning) -> ResultatFaisabilite`, pure, never raises — every
  anomaly becomes a `Violation`. `CompatibiliteMachineTache` is mandatory (≥1 per task, enforced by
  `InstanceTRCO`) and carries `duree` per (task, resource), not a fixed `Tache` field (true flexible FJSP).
- **Étape 3 — synthetic bench** (`validation_engine/synthetic_bench/`): `construction_inverse.py`
  builds instances *around* a chosen-optimal `Planning` — each "job" a precedence chain on
  dedicated resources (never shared), so the optimum is provable by arithmetic, no solver needed.
  `catalogue.py` (1→80 tasks), `stockage.py` (JSON); regenerate via `generer_banc_synthetique.py`.
- **Reference solver** (`solveur_reference/`, not in the roadmap, predates Étape 4 on purpose):
  hand-written CP-SAT FJSP model. Two entry points: `resoudre(instance) -> Planning | None` (the
  cascade/store/sandbox contract, what generated code must match) and
  `resoudre_detaille(instance) -> ResultatResolution` (adds statut/makespan/temps, for
  `scripts/benchmarker_solveur_reference.py`). **Verified (PH0-T4):** split added after the first
  real Docker run found the store freezing the raw `ResultatResolution` module while the cascade
  validated a `.planning`-unwrapped version — validated ≠ frozen. Keep both in sync, and in sync
  with `feasibility_checker.py`'s mandatory-`CompatibiliteMachineTache`/per-pair-`duree` rule.
- **Étape 4 — single-shot generator** (`generation/`), built *after* Étape 5 in practice: one LLM
  call, no repair loop. `client_llm.py` picks provider via `PRISME_LLM_PROVIDER`/`_MODEL` (extra
  `.[llm]`, lazy import). `validation_statique.py` is an AST **allowlist** (only `ortools`, `dsl`,
  `collections`, `dataclasses`, `typing`, `__future__`; rejects `eval`/`exec`/`__import__`/`open`/
  dunder escapes) run *before* `executer.py`'s `exec()` — but `exec()` gives no real isolation;
  **actual sandboxing is Étape 7**. `tentative_unique.py` chains generate → static-validate →
  execute → cascade-judge, swallowing runtime exceptions from generated code.
- **Étape 5 — validation cascade** (`validation_engine/cascade.py`): `evaluer_cascade(solveur)`
  takes any `Callable[[InstanceTRCO], Planning | None]` through, in order: **faisabilité** (every
  instance), **optimalité** (Étape 3 bench vs known optimum), **fidélité** (`reference_cases/`,
  partial comparison — same task→resource + same makespan, not strict timing). Each instance gets
  a `DiagnosticInstance` naming which brick failed. `stability_test.py` (§6.5): N runs, stable only
  if every run is legal and hits the same makespan (`tester_stabilite.__test__ = False` needed
  after import in tests — pytest's default `python_functions` bare-matches `"test"`, not `"test_*"`).
- **Étape 7 — store + ephemeral sandbox** (`solver_store/`, `sandbox/`), Étape 6 skipped on
  purpose. `Registre` is SQLite-backed (Postgres deferred to `PRISME_Plan_Developpement.md`
  PH8-T1). **Refuses to register** any non-green `VerdictCascade`; re-verifies a SHA-256 hash on
  retrieval. `sandbox/runner.py` runs a frozen artifact in a fresh `--rm` container: no network,
  read-only rootfs, non-root (uid 10001), CPU/memory/PID limits, `no-new-privileges`, force-kill on
  timeout. The in-container harness (`executer_dans_conteneur.py`) has zero dependency on
  `validation_engine/` — both §6.7 guardrails run on the **host**. It registers the loaded module
  in `sys.modules` before `exec_module` (`dataclasses` needs `cls.__module__` resolvable) —
  **verified (PH0-T4):** omitting this crashed every frozen `@dataclass` solver, found and fixed on
  the first real Docker run; `pytest tests/integration/test_sandbox_*.py` now passes for real.
- **Étape 8 — API + ERP adapter** (`api/`, `adapters/erp_reference/`): `routes/ingestion.py` (→
  `input_validation/`, §6.7 guardrail), `routes/execution.py` (solver lookup by `client_id` +
  **exact** constraint-type-signature match — deliberate literal reading, not a bug:
  `"precedence,compatibilite_machine_tache"` won't match an instance using only one),
  `routes/planning.py` (operational JSON), `routes/audit.py` (source code, explicit request only,
  never mixed into the operational response). `api/etat.py` is in-memory demo wiring only.
  `api/dependencies.py`'s `obtenir_registre()` points at the real store — tests must override via
  `app.dependency_overrides` (`conftest.py`). `adapters/erp_reference/` translates a deliberately
  poorer simulated legacy format (single forced machine) into `InstanceTRCO`. **Verified
  (PH0-T4):** `demo_bout_en_bout` and `test_api_bout_en_bout.py` now run clean end to end.

Docker-dependent tests (`test_sandbox_execution.py`, `test_sandbox_securite.py`,
`test_api_bout_en_bout.py`) **skip**, not fail, if Docker is unreachable (`conftest.py` session
fixture); the security test feeds malicious code straight to `executer_dans_sandbox`, bypassing
the AST gate, to prove container isolation holds independently (§5.3). Codebase is **French**
(identifiers, docstrings, domain terms) — match it (`Tache`, `Ressource`, `faisabilité`...).

## The founding principle (do not violate)

**Generate once, re-execute many times.** The AI writes solver code a single time, offline, at a
rare event (new client / new constraint structure). Once validated, that code is **frozen**,
persisted (`solver_store/`), and re-run on changing data inside a fresh ephemeral container
(`sandbox/`) — **never regenerated per execution**. Any design calling the AI per run breaks the
core innovation. Two independent layers: *code persists* (performance), *execution is disposable*
(security).

**Human-in-the-loop is non-negotiable.** At every risky decision — triggering a reschedule,
diagnosing a bad plan, a generation failure — the system alerts and *proposes*; a human decides.
Never design autonomous action at these points.

## Architecture — data flow

ERP (proprietary) → **adapter** (anti-corruption → canonical T-R-C-O) → **API** → input validation
→ sandbox runs frozen solver → feasibility guardrail → **operational** (planning JSON, every
iteration) / **audit** (solver source, explicit request) output channels.

The **T-R-C-O DSL** (`dsl/`) is exchange format, generation input, and validation frame at once.
Vocabulary is deliberately **finite and typed** to bound the AI's generation surface (§5.3 security
control — `dsl/schema/common.py`'s `Identifiant`). Four axes: **T**âches, **R**essources,
**C**ontraintes (precedence, machine-task compatibility — *constraints*, not fields on
`Tache`/`Ressource`), **O**bjectifs (makespan, load balancing, deadlines).

**`dsl/schema/` conventions:** every model sets `extra="forbid"`; `Contrainte` is a
`Literal["type"]`-discriminated `Union` so new kinds join without touching existing ones;
`InstanceTRCO` enforces per-axis unique IDs and that every constraint references a declared
`Tache`/`Ressource` — that cross-axis check *is* the §6.7 upstream guardrail.

**Minimal viable core (in scope):** precedence, machine-task compatibility, durations only. Setup
times, calendars, priorities/due dates, capacity are **out of initial scope** by design — accept
later without redesign, don't implement now. Guard against scope creep.

## Module map

| Module | Role |
|---|---|
| `dsl/` | T-R-C-O canonical model: typed `schema/`, payload `validation/`, `examples/` |
| `generation/` | Single-shot LLM generator → CP-SAT code (`agents/`, `tentative_unique.py`); repair loop (`loop.py`, `failures/`) not built — Étape 6 skipped |
| `validation_engine/` | Validation cascade + `stability_test.py` |
| `solveur_reference/` | Hand-written CP-SAT solver, permanent, outside the generate-once cycle |
| `solver_store/` | Persistent registry (`registry.py`) + frozen `artifacts/` |
| `sandbox/` | Ephemeral disposable-container execution (`runner.py`, `container/`) |
| `api/` | Routes: `ingestion`, `execution`, `planning`, `audit`, `alertes`, `executions/{id}/decision` (`validation.py`), `diagnostics`, `supervision` (dashboard read-only view) |
| `adapters/` | ERP anti-corruption layer; `erp_reference/` for the PoC |
| `diagnostics/` | Cause attribution (`attribution.py`) + sandbox wrapper (`solveur_sandbox.py`) — done |
| `dashboard/` | React/Vite (§2.3, Phase 10) — alerts, human validation, live diagnostic — done |
| `tests/` | `unit/`, `integration/`, `property_based/`, `generation_stability/` |
| `docs/` | Architecture + DSL spec (next priority) + roadmap — not yet written |
| `scripts/` | Dev env, synthetic-bench generation, CI tasks |

## Validation & testing philosophy (§6)

Non-deterministic generated code is **not** tested like hand-written code: **Layer 1** hand-written
code gets classic unit/integration tests (`tests/unit/`, `tests/integration/`); **Layer 2** the
AI-generated solver is judged on **properties of the planning it produces**, not the code text
(`tests/property_based/`); **Layer 3** the generation itself is tested by running the same DSL N
times and checking plans are equivalent (`tests/generation_stability/`).

The generate-test-repair loop (`generation/`, not yet built) must stay **bounded** (max attempts,
then honest failure to a human), **offline** (at generation, never per execution), and
**diagnostic** (names which constraint is violated). The diagnostic loop (`diagnostics/`)
attributes cause in a fixed order before acting: code fault (synthetic ground truth) → corrupt
data (feasibility) → wrong DSL spec (reference cases). Never "improve" healthy code for bad data.

## Security posture

Executing AI-generated code is risk #1 (§5.3), above auth/encryption. Three layers, all
implemented: ephemeral sandbox (Étape 7, real isolation), static AST-allowlist validation (Étape 4,
weaker, never a substitute), DSL-bounded generation surface (`Identifiant`). Preserve all three
when touching `generation/`, `sandbox/`, `solver_store/` — static validation alone is never a safe
execution boundary (`test_sandbox_securite.py` bypasses it to prove the container holds alone).

## Build order (roadmap §8, dependency-ordered)

DSL → feasibility checker → synthetic bench → single-shot generator → validation cascade →
generate-test-repair loop → store + sandbox → API + ERP adapter → dashboard. The **detailed
T-R-C-O DSL spec** is the declared next priority (§9); `docs/roadmap.md` doesn't exist yet.

**Actual order deviates:** cascade (Étape 5) was built and made green *before* the generator
(Étape 4) — it only needs a `Callable[[InstanceTRCO], Planning | None]`, and the reference solver
stood in as a candidate; success rate against a live LLM is still unmeasured. **Étape 6 skipped at
explicit direction** — no `generation/loop.py`/`failures/` yet; `Registre.enregistrer_solveur`
expects a `VerdictCascade` handed directly (manual call today, the loop's caller later). **Étape 8
built ahead of Étape 6** — `/execution` only needs *some* validated solver, supplied by
`enregistrer_solveur_reference.py` re-running the cascade on the reference solver.

# Check-semantics manifest — M4 / M5 gate checks (B8)

**Stamp:** 2026-08-13T11:20Z · **Author:** Review
**Basis:** in-tree harness obligations (sibling contracts + skills).
**Status:** binding (in-tree).
**Doctrine:** fixture-proof ≠ semantically adequate (3rd occurrence this campaign — smoke/root-cause family).

## How to read a row

| Column | Meaning |
|--------|---------|
| **Check id** | Stable name in verdict `required_checks` / floor receipts |
| **Operands** | Exact inputs the check may touch (paths, URLs, scripts, env) |
| **Coverage claim** | What PASS asserts about the **product** (not the harness) |
| **Adequacy class** | `SEMANTIC` (product truth) · `ADMISSION` (fixture/schema only) · `TOOLING` (harness health) |
| **Over-promise risk** | What a green check can **hide** |
| **Lint** | Mechanical guard proposed (tip-bank land) |

---

## M4 floor (`run-m4-floor.sh` → receipts under `evidence/receipts/m4-floor/`)

| Check id | Operands | Coverage claim | Adequacy | Over-promise risk | Lint |
|----------|----------|----------------|----------|-------------------|------|
| `boot_health` | `mvn -DskipTests package` (JDK matching pom release); Quarkus boot; probe `/q/health` (or contract URL) | Whole-app **packages and boots**; health endpoint returns success | **SEMANTIC** | Does **not** claim REST API fidelity, CDI bean completeness beyond boot wiring, or G-4 parity | Receipt schema requires `package_rc` + `health_status`; forbid PASS if package skipped |
| `endpoint_smoke` | Configured smoke URL(s) from floor contract (historically health/root — **not** `/api/*`) | Named smoke path returns success **after** boot | **SEMANTIC (narrow)** | Name suggests “endpoints”; operand is often health/root only — **must not** be read as REST CRUD proof | Manifest + runner: smoke URL list declared; if list excludes `/api/*`, check id must be `endpoint_smoke_health` **or** claim text must say “health/root only” |
| `g4_hook` | Admission G-4 fixtures / hook script under check-release-readiness | Hook **ran**; admission fixtures evaluated | **ADMISSION** until product partitions harvested | PASS/INCONCLUSIVE on fixtures ≠ product G-4 runtime parity | Verdict router: `g4_mode=SAMPLE` ⇒ forbid mapping hook PASS → product G-4 closed; M5 ACCEPT blocked on INCONCLUSIVE (already AD-H §18) |

**Campaign proof:** M4 run#1 `boot_health` FAIL correctly caught whole-app CDI (`JdbcTemplate`) while per-story scoped-compile stayed green — **SEMANTIC adequacy of `boot_health` validated**.
**Campaign scar:** run#1 verifier patched product to chase boot — conduct breach (separate); does not weaken the check’s semantic claim.

---

## M4 `required_checks` (dispatch-phase / check-release-readiness)

| Check id | Operands | Coverage claim | Adequacy | Over-promise risk | Lint |
|----------|----------|----------------|----------|-------------------|------|
| `mvn_clean_verify` | `mvn clean verify` (± `-DskipTests` per body); `JAVA_HOME` = pom release | Clean rebuild + verify succeed | **SEMANTIC** | SkipTests hides test emptiness; stale MapStruct bytecode can false-green without `clean` | Require `clean` token in command line for PASS; tip-bank B3 |
| `unit_it_contract` | `mvn test` / product `*Test`/`*IT` discovery scripts | Unit/IT contract as declared | **SEMANTIC or TOOLING** | Empty suite + exit 0 = false ACCEPT path (seen as M5 `no-product-tests`) | FAIL (not SKIP) when AR-2.8 requires tests and zero found — or explicit `SKIP` with `accept_scope` block |
| `sonar` | `mvn sonar:sonar` | Quality gate if configured | **TOOLING** | Unconfigured plugin → SKIP must not upgrade ACCEPT | SKIP allowed only when plugin absent; never maps to ship |
| `g1_characterization` | G-1 scripts + fixtures (volume probe / characterization) | Characterization gate per AD | **ADMISSION** until product thresholds pinned | Fixture PASS ≠ kill-ratio PASS (`g1_kill_ratio=pending_threshold`) | Schema: pending_threshold ⇒ PASS forbidden for ship (already noted in verdicts) |
| `g2_if_harvest` | G-2 harvest-fidelity scripts/fixtures | Harvest fidelity if harvest present | **ADMISSION** on fixtures | Same family | Label `ADMISSION` in manifest until harvest product artifacts exist |

---

## M5 `required_checks` (from `m5-t_7d56398e` / `m5-t_d0160a26` banked verdicts)

| Check id | Operands | Coverage claim | Adequacy | Over-promise risk | Lint |
|----------|----------|----------------|----------|-------------------|------|
| `preflight` | Phase preflight scripts | Preconditions for M5 runner | **TOOLING** | Does not prove runtime API | — |
| `regression_suite` | Product regression command | Product regressions green | **SEMANTIC** | SKIP when no tests = hole | Same as unit_it_contract |
| `mta_rescan` | MTA / analysis scripts | Findings scan executed | **SEMANTIC (analysis)** | Not runtime | — |
| `g3_findings_delta` | G-3 delta scripts/fixtures | Findings delta within bound | **ADMISSION** on fixtures | Fixture PASS ≠ product finding close | — |
| `acceptance_live` | Live HTTP against running app (paths exercised) | Named live acceptance paths behave | **SEMANTIC** | Must list paths; `/q/health` PASS must not imply `/api/*` | **Path manifest required**; M5 REFUSE correctly used JAX-RS 404 on `/api/*` |
| `g4_runtime_parity` | Product G-4 partitions + runtime compare | Product runtime parity closed | **SEMANTIC** only with harvested partitions | Admission fixtures → INCONCLUSIVE ≠ ACCEPT | Block M5 ACCEPT on INCONCLUSIVE (held); policy rules harvest vs admission change |
| `accept_scope` | Closure / promote policy | Scope of ACCEPT idle/active | **TOOLING** | IDLE must block ship | — |

---

## Known over-promise incidents (campaign)

| # | Symptom | Check that looked green | Semantic miss | Manifest control |
|---|---------|-------------------------|---------------|------------------|
| 1 | Per-story compile green | scoped-compile / story gates | Whole-app CDI package fail | M4 `boot_health` owns package; optional advisory pre-M4 package (execution review §e) |
| 2 | M4 `endpoint_smoke` / health PASS | health/root smoke | `/api/*` 404 (M5) | Rename or narrow claim; `acceptance_live` owns API paths |
| 3 | G-1/G-2/G-3 fixture PASS | admission fixtures | Product G-4 still SAMPLE | Adequacy class **ADMISSION**; no promote to SEMANTIC without harvest |

---

## Adequacy checklist

1. Every new/changed gate check adds one row here **before** first live use.
2. Name ↔ claim review: if the English name implies more than operands, **rename or shrink the claim**.
3. Lint (mechanical where possible):
 - `g4_mode=SAMPLE` + `g4_*` PASS ⇒ warning
 - `endpoint_smoke` PASS with only `/q/health` ⇒ warning if id still says `endpoint` without qualifier
 - `unit_it_contract` / `regression_suite` exit 0 with zero tests when AR-2.8 on ⇒ FAIL or forced SKIP+block
4. Reviewer (human steward) stamps Adequacy class on first green receipt.

## Status

| Item | State |
|------|-------|
| Manifest authored (Review Need) | **DONE** — this file |
| Lint tooling | **DONE** — `check-release-readiness/scripts/check-semantics-manifest.py` (B8 tip `Lead:wire-b8-check-semantics-manifest`) |
| Rename `endpoint_smoke` / path lists | **DONE** — floor runner emits `endpoint_smoke_health` when smoke paths exclude `/api/*` |
| G-4 harvest vs admission | **OPEN** (lint forbids SAMPLE→product-closed; harvest still required for SEMANTIC close) |

Callers: `check-m4-floor-receipts.py`, `run-m4-floor.sh` / `write-receipt.py`, `validate-contracts` (negative fixtures under `governance/fixtures/check-semantics-manifest/`).

— Review

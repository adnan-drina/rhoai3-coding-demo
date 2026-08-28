---
name: check-release-readiness
description: Use before advancing or shipping — lint M4/M5 verdict tokens and floor receipts, parse surefire XML, snapshot test reports before any rebuild, and refuse an M4 card body that already names a verdict token or ship flag. Do not compose evidence/verdicts/m4-verdict.json (compose-m4-verdict). Do not use for domain parity (check-domain-parity), wall/crash requeue or chaos (retired with .hermes/_park; rebuild later on dest GO), or phase-dispatch matrix (deleted in v2).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; reads migration/ receipts
metadata:
  author: rhoai3-harness-team
  version: "1.5.1"
  hermes:
    tags:
    - gates
    - m4
    - m5
    category: gates
    kind: guidance
---
## When to Use

- **A verdict is about to be consumed** at M4/M5/factory: confirm every
  JSON under `evidence/verdicts/` and `evidence/preflight/` carries a
  legal token + routing pair (M4 is literally `PROVISIONAL_ACCEPT` only
  when `failed_floors` is empty). Skill **`compose-m4-verdict`** is the
  producer that writes `evidence/verdicts/m4-verdict.json`; this skill
  lints routing and floors. Do not pin only this leaf on M4.
- **A ship or `promoted_to_main` claim exists**: factory must not contradict a
  *full* M5 `ACCEPT`, the claim must name a candidate SHA, and standing entry-
  point descopes must force `SCOPED_ACCEPT`.
- **A Phase-3 dual-arm verify needs the M4 floor** (boot health, endpoint smoke,
  G-4 hook).
- **Not this skill** when the question is whether migrated code still behaves
  like the referent — mutation volume, field conservation, findings delta and
  HTTP parity are `check-domain-parity`. **Not** composing the M4 JSON
  (`compose-m4-verdict`). Wall/crash requeue, chaos, and
  workspace restore retired with `.hermes/_park/` (Operator GO `155455Z`;
  rebuild later on dest GO; never dump into kernel).

# Validation and release gates (AD-H §18 / §18.0)

## Contracts

- `AGENTS.md (doctrine; was validation-release-gates)`
- This skill (routing / gate-receipt schemas live here; `m4-verdict.json`
  schema is `compose-m4-verdict`; no `governance/` folder)
- Native Kanban state is the phase DAG (`hermes kanban show --json`)

**§18.0:** M4 verdict = literal `PROVISIONAL_ACCEPT` (never ship); M5 = `ACCEPT`
(G-4); shared-substrate reopen = closure ∩ implicated; kill-ratio `PASS`
forbidden until threshold pinned — use `pending_threshold` at M4. M5 ACCEPT
requires kill-ratio PASS+pin; a waiver cannot author ACCEPT (B-4/C-3(a)).

## Procedure

Ordered stages. Completion-floor scripts take the product root as their first
positional arg and are idle (exit 0) when their trigger artifact is absent.
**Not idle:** `assert-retrievable-tree`, `assert-pinned-gates-ran`, and
`assert-no-fence-evasion` — those fail closed on silence (Architect `142524ZA`;
Operator `074910ZO`). Commands under **Checks**.

0. **Before `PROVISIONAL_ACCEPT`** — `scripts/run-m4-pre-verdict.sh` (Architect
   `151334ZA` **(a)** runner-invoked). `run-m4-floor.sh` calls it first.
   Order: snapshot surefire/failsafe into `evidence/m4-pre-rebuild/` (first
   XML snapshot wins; never overwrite with empty), parse the snapshot
   (Failures>0 or missing XML is REFUSE), refuse an M4 body that names
   `Token:`/`ship:`, then `assert-retrievable-tree`, **run the pinned
   feeding gates** (`check-partition-coverage`, `check-product-tests`,
   `check-test-toolchain`) with `--write-receipt` into
   `evidence/receipts/gates/`, then `assert-pinned-gates-ran`
   (`ran: true` only), `assert-g4-claim-consistency`, `assert-no-fence-evasion`.
   Pinning a leaf is availability, not enforcement. These do **not**
   idle-exit-0. Residual skip of this parent skill is **(c)** until a later
   K2 GO (**(b)** PARK). Worker logs: `FENCE_EVASION_LOGS` (colon list), or
   parent-chain walk from `$HERMES_KANBAN_TASK` (M1/M2/M3 stories — **not**
   this M4 card's own log; Operator `105656ZO`). `FENCE_EVASION_LOG` is a
   single extra path for land-time tests, not a substitute under M4.
   Do not `mvn clean` before the snapshot; the floor never runs `clean`.
1. **Completion floors** (refuse a phase that never ran anything real) —
   `check-runnable-db-config.py`, `check-empty-security.py`,
   `assert-no-trivial-quarkusmain.py`, `assert-inherited-id-not-redeclared.py`,
   `check-test-toolchain.py`, and `../check-domain-parity/scripts/check-product-tests.py`.
2. **Verdict lint** — composition is `compose-m4-verdict`. Then
   `check-verdict-routing.py` over `evidence/verdicts/` + `evidence/preflight/`;
   `check-accept-scope.py` for descope ⇒ `SCOPED_ACCEPT`;
   `compute-substrate-reopen.py --check <verdict>` (or `--implicated a,b
   --print`) against `evidence/slices/closure-map.json`.
3. **Semantics (B8)** — `check-semantics-manifest.py` (contract
   `check-semantics-manifest.md`; also via `check-m4-floor-receipts.py`).
4. **Ship** — `check-factory-m5.py` (required oracle) and
   `check-candidate-promote.py` (candidate SHA before `promoted_to_main`).
5. **Floor** — `run-m4-floor.sh` then `check-m4-floor-receipts.py`.
   Wall/crash requeue, chaos, and complete-exit asserts retired with
   `.hermes/_park/` (not this skill; rebuild later on dest GO).

## Checks

```bash
# Before PROVISIONAL_ACCEPT — runner-invoked (fail-closed; not idle)
bash "${HERMES_SKILL_DIR}/scripts/run-m4-pre-verdict.sh" /projects/modernized

# Snapshot + surefire + M4 body (also invoked by the runner above)
python3 "${HERMES_SKILL_DIR}/scripts/snapshot-m4-test-reports.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/assert-surefire-results.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/assert-m4-card-body.py"

# Verdict routing + §18.0 composition
python3 "${HERMES_SKILL_DIR}/scripts/check-verdict-routing.py" /projects/modernized

# B8 check-semantics (see references/available-scripts.md + fixtures README)
python3 "${HERMES_SKILL_DIR}/scripts/check-semantics-manifest.py" /projects/modernized

# Shared-substrate reopen set (§18.0 ¶4 / §11.3)
python3 "${HERMES_SKILL_DIR}/scripts/compute-substrate-reopen.py" /projects/modernized \
  --implicated com.example.shared.Entity --print

# Factory must not contradict M5 ACCEPT (required oracle)
python3 "${HERMES_SKILL_DIR}/scripts/check-factory-m5.py" /projects/modernized

# AD-H §16.6 / AR-2.1 — refuse non-runnable default DB (idle until DB intent)
python3 "${HERMES_SKILL_DIR}/scripts/check-runnable-db-config.py" /projects/modernized

# AD-H §16.6 / AR-2.2 — refuse empty/placeholder security (idle until security intent)
python3 "${HERMES_SKILL_DIR}/scripts/check-empty-security.py" /projects/modernized

# W6 — dest @QuarkusMain on a trivial SpringApplication.run wrapper (idle if none)
python3 "${HERMES_SKILL_DIR}/../../migration/spring-to-quarkus-patterns/scripts/assert-no-trivial-quarkusmain.py" /projects/modernized

# W6 — subclass @Id when a mapped superclass already declares identity
python3 "${HERMES_SKILL_DIR}/../../migration/form-entity-persistence/scripts/assert-inherited-id-not-redeclared.py" /projects/modernized

# AD-H §G.1 / AR-2.8 — product-test families (boot/CRUD/security/DB); not harness probe
python3 "${HERMES_SKILL_DIR}/../check-domain-parity/scripts/check-product-tests.py" /projects/modernized

# dest-8 complete-around lint (pass the measured floor rc; do not re-run AR-2.8 here)
python3 "${HERMES_SKILL_DIR}/scripts/assert-m4-complete-around-red.py" \
  --verdict /projects/modernized/evidence/verdicts/m4-verdict.json --floor-rc 1

# S-010 Class A — assertj-core pin + rest-assured in pom (harness-owned toolchain)
python3 "${HERMES_SKILL_DIR}/scripts/check-test-toolchain.py" /projects/modernized

# Wall/crash requeue, chaos, workspace restore: retired with `_park/`
# (not dest; not this skill; rebuild later on dest GO)
```

Contracts: this skill (M4/M5 verdict routing; no `governance/` folder),
`.hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md`,
`.hermes/skills/migration/manage-quarkus-extensions/references/test-toolchain.md`.

Domain-gate oracles (G-1…G-4) remain authoritative; this skill does not replace them.

## M4 floor runner (R-HX.9 Phase-2)

Minimum ordered runner for Phase-3 dual-arm verify — **not** full AD-010.

Contract: `.hermes/skills/gates/check-release-readiness/references/m4-floor-runner.md`  
Schema: this skill (`check-m4-floor-receipts.py`; no `governance/` folder)

```bash
bash "${HERMES_SKILL_DIR}/scripts/run-m4-floor.sh" /path/to/frozen-modernized
python3 "${HERMES_SKILL_DIR}/scripts/check-m4-floor-receipts.py" \
  /path/to/frozen-modernized/evidence/receipts/m4-floor/<run-id>
# dry fixtures
python3 "${HERMES_SKILL_DIR}/scripts/check-m4-floor-receipts.py" \
  /projects/modernized/.hermes/skills/gates/check-release-readiness/fixtures/m4-floor/known-good
```

## Chaos matrix (retired)

Timeout / crash / dup-dispatch chaos retired with `.hermes/_park/`. Dest
omit + bootstrap refuse if `run-chaos-matrix.py` reappears. Not this skill.
Rebuild later only on dest GO.

## Pitfalls

- Reading idle `OK: no … artifacts` lines as a pass — N must be > 0 for the
  lint to have policed anything.
- Shipping on `PROVISIONAL_ACCEPT` or unpinned G-1 kill-ratio.
- Treating M4 floor green (`ad010_demo`) as `release_qualified`.

## Verification

- `scripts/run-m4-pre-verdict.sh` (called first by `run-m4-floor.sh`) invokes
  `snapshot-m4-test-reports.py`, `assert-surefire-results.py`,
  `assert-m4-card-body.py`, `assert-retrievable-tree.py`,
  `assert-pinned-gates-ran.py` (`ran: true` only; `ran: false` is not a run),
  `assert-g4-claim-consistency.py` (G-4 N/A vs `INCONCLUSIVE` is OBJECT),
  and `assert-no-fence-evasion.py` over **work** logs (`resolve-m4-work-logs.py`
  walks parents or `FENCE_EVASION_LOGS`; scanning `$HERMES_KANBAN_TASK.log`
  alone is REFUSE) and **fail closed**. KEEP the detector (Operator
  `115007ZO` / `122315ZO`: dest-3 encode-after-refusal is the class; tirith
  is retired and never covered it).
  Idle is not a pass for those asserts. `specimen-n/a: no DB` belongs on a
  `"ran": true` N/A file. `check-release-readiness` `scripts/` must `grep`
  both leaf names and `assert-no-fence-evasion` (Architect `151334ZA` (a);
  Operator `074910ZO` / `105656ZO` / `115007ZO`). Negative controls: dest-5
  `Failures: 1` surefire, dest-5 `Token: PROVISIONAL_ACCEPT` body, dest-5
  `"ran": false` refusal — all REFUSE.
- `check-verdict-routing.py` prints `OK: verdict-routing checks passed (N
  artifact(s))`. **Silent-failure assertion: N must be > 0.** `N = 0` — or the
  idle line `OK: no verdict/preflight artifacts — routing lint idle` — means
  nothing was policed, not that the phase is clean. The same rule applies to the
  idle lines from `check-factory-m5.py`, `check-candidate-promote.py`,
  `check-accept-scope.py`, and `check-persisted-data-contract.py`: idle is not a pass.
- No artifact carries `ship: true` with a verdict other than a full M5 `ACCEPT`,
  no `PROVISIONAL_ACCEPT` outside M4, and no `g1_kill_ratio: PASS` without
  `g1_kill_ratio_threshold_pinned`. A `g1_kill_ratio_waiver` or
  `operator_waiver` on an M5 ACCEPT is REFUSE.
- M4 floor: `evidence/receipts/m4-floor/<run-id>/` holds all three receipts —
  `boot_health.json`, `endpoint_smoke.json`, `g4_hook.json`, schema
  `rhoai3.gate-receipt/v1` — and `check-m4-floor-receipts.py` prints `OK: M4
  floor receipts complete`. `boot_health`/`endpoint_smoke` must be `PASS`;
  `g4_hook` `INCONCLUSIVE` is honest for the SAMPLE floor, `REFUSE` fails.
  Every receipt has `ad010_demo: false` —   floor green is not `release_qualified`. B8: health-only smoke →
  `endpoint_smoke_health`; `check-semantics-manifest.py` must pass.
- Wall/crash requeue policy retired with `.hermes/_park/` (not dest; not
  this skill; rebuild later on dest GO).
- Conformance lint passes for this skill.

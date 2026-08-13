---
name: check-release-readiness
description: Before advancing, requeueing or shipping — lint verdict tokens, phase required_checks and floor receipts
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; reads migration/ receipts
metadata:
  author: rhoai3-harness-team
  version: "1.2.0"
  hermes:
    tags:
    - gates
    - m4
    - m5
    category: gates
    kind: guidance
---
## When to Use

- **A verdict is about to be written or consumed** at M4/M5/factory: confirm
  `.hermes/phase-dispatch.yaml` `required_checks` still cover the §18 matrix and
  that every JSON under `evidence/verdicts/` and `evidence/preflight/` carries
  a legal token + routing pair (M4 is literally `PROVISIONAL_ACCEPT`).
- **A ship or `promoted_to_main` claim exists**: factory must not contradict a
  *full* M5 `ACCEPT`, the claim must name a candidate SHA, and standing entry-
  point descopes must force `SCOPED_ACCEPT`.
- **A task hit `timed_out` / `crashed` / `gave_up`**, or a card with cmd-shaped
  `exit_criteria` is about to be completed: evaluate exits, apply the wall/crash
  requeue ceilings, and prove workspace restore before requeue.
- **A Phase-3 dual-arm verify needs the M4 floor** (boot health, endpoint smoke,
  G-4 hook) or a chaos sweep proving every failure leaves a named terminal.
- **Not this skill** when the question is whether migrated code still behaves
  like the referent — mutation volume, field conservation, findings delta and
  HTTP parity are `check-domain-parity`. This skill lints the verdicts those oracles
  feed and the completion/ship policy around them; it never re-derives them.

# Validation and release gates (AD-H §18 / §18.0)

## Contracts

- `governance/contracts/validation-release-gates.md`
- `governance/schemas/verdict.md`
- Phase `required_checks` + `accept_kind`: `.hermes/phase-dispatch.yaml`

**§18.0:** M4 verdict = literal `PROVISIONAL_ACCEPT` (never ship); M5 = `ACCEPT`
(G-4); shared-substrate reopen = closure ∩ implicated; kill-ratio `PASS`
forbidden until threshold pinned — use `pending_threshold` or typed waiver.

## Procedure

Ordered stages; each script takes the product root as its first positional arg
and is idle (exit 0) when its trigger artifact is absent. Commands under
**Checks**.

1. **Matrix** — `check-phase-matrix.py <root>` asserts `required_checks` per
   phase; `--print M4|M5|factory` emits the validator preflight checklist.
2. **Completion floors** (refuse a phase that never ran anything real) —
   `check-runnable-db-config.py`, `check-empty-security.py`,
   `check-test-toolchain.py`, and `../check-domain-parity/scripts/check-product-tests.py`.
3. **Verdict composition** — `check-verdict-routing.py` over
   `evidence/verdicts/` + `evidence/preflight/`; `check-accept-scope.py` for
   descope ⇒ `SCOPED_ACCEPT`; `compute-substrate-reopen.py --check <verdict>`
   (or `--implicated a,b --print`) against `evidence/slices/closure-map.json`.
4. **Semantics (B8)** — `check-semantics-manifest.py` (contract
   `check-semantics-manifest.md`; also via `check-m4-floor-receipts.py`).
5. **Terminals and requeue** — `evaluate-exit-criteria.py`, wall/crash apply
   scripts, `restore-or-refuse-requeue.py`, `check-workspace-clean.py`,
   `apply-dependency-wait-hold.py`, `check-side-effect-recovery.py`.
6. **Completion** — `assert-complete-exit-criteria.py --task-id --body` →
   `evidence/runs/<task>/complete-exit-ok.json` before `kanban_complete`.
7. **Ship** — `check-factory-m5.py` (required oracle) and
   `check-candidate-promote.py` (candidate SHA before `promoted_to_main`).
8. **Floor / chaos** — `run-m4-floor.sh` then `check-m4-floor-receipts.py`;
   `run-chaos-matrix.py` under the Hermes venv.

## Checks

```bash
# Assert dispatch-phase matrix matches §18 (M3/M4/M5)
python3 "${HERMES_SKILL_DIR}/scripts/check-phase-matrix.py" /projects/modernized

# Print checklist for a phase
python3 "${HERMES_SKILL_DIR}/scripts/check-phase-matrix.py" /projects/modernized --print M4

# Verdict routing + §18.0 composition
python3 "${HERMES_SKILL_DIR}/scripts/check-verdict-routing.py" /projects/modernized

# B8 check-semantics (see references/available-scripts.md + fixtures README)
python3 "${HERMES_SKILL_DIR}/scripts/check-semantics-manifest.py" /projects/modernized

# Shared-substrate reopen set (§18.0 ¶4 / §11.3)
python3 "${HERMES_SKILL_DIR}/scripts/compute-substrate-reopen.py" /projects/modernized \
  --implicated com.example.shared.Entity --print

# Factory must not contradict M5 ACCEPT (required oracle)
python3 "${HERMES_SKILL_DIR}/scripts/check-factory-m5.py" /projects/modernized

# AD-H §5.1 / ER#2 F4 — before requeue after crashed/gave_up/kill (requeue≠restore)
python3 "${HERMES_SKILL_DIR}/scripts/restore-or-refuse-requeue.py" /projects/modernized \
  --terminal crashed
python3 "${HERMES_SKILL_DIR}/scripts/check-workspace-clean.py" /projects/modernized

# AD-H §16.6 / AR-2.1 — refuse non-runnable default DB (idle until DB intent)
python3 "${HERMES_SKILL_DIR}/scripts/check-runnable-db-config.py" /projects/modernized

# AD-H §16.6 / AR-2.2 — refuse empty/placeholder security (idle until security intent)
python3 "${HERMES_SKILL_DIR}/scripts/check-empty-security.py" /projects/modernized

# AD-H §G.1 / AR-2.8 — product-test families (boot/CRUD/security/DB); not harness probe
python3 "${HERMES_SKILL_DIR}/../check-domain-parity/scripts/check-product-tests.py" /projects/modernized

# S-010 Class A — assertj-core + rest-assured in pom (harness-owned toolchain)
python3 "${HERMES_SKILL_DIR}/scripts/check-test-toolchain.py" /projects/modernized

# Architect E-110403Z / E-121300Z — wall exit-eval + soft K requeue policy
python3 "${HERMES_SKILL_DIR}/scripts/evaluate-exit-criteria.py" /projects/modernized \
  --body evidence/bodies/m3-s-010.json --task-id t_xxx --trigger timed_out
python3 "${HERMES_SKILL_DIR}/scripts/check-wall-exit-eval.py" /projects/modernized \
  --task-id t_xxx --trigger timed_out --require-test-compile
python3 "${HERMES_SKILL_DIR}/scripts/apply-wall-requeue-policy.py" /projects/modernized \
  --task-id t_xxx --body evidence/bodies/m3-s-010.json --k-soft 1

# Architect E-20260810T142650Z — crash requeue ceiling (does not spend wall soft-K)
python3 "${HERMES_SKILL_DIR}/scripts/apply-crash-requeue-policy.py" /projects/modernized \
  --task-id t_xxx --k-crash 1 --cause harness_fault --stamp
```

Contracts: `governance/contracts/workspace-recovery.md`,
`governance/contracts/runnable-db-security.md`,
`governance/contracts/product-tests.md`,
`governance/contracts/test-toolchain.md`,
`governance/contracts/wall-exit-eval.md`,
`governance/contracts/crash-requeue.md`.

Domain-gate oracles (G-1…G-4) remain authoritative; this skill does not replace them.

## M4 floor runner (R-HX.9 Phase-2)

Minimum ordered runner for Phase-3 dual-arm verify — **not** full AD-010.

Contract: `governance/contracts/m4-floor-runner.md`  
Schema: `governance/schemas/gate-receipt.md`

```bash
bash "${HERMES_SKILL_DIR}/scripts/run-m4-floor.sh" /path/to/frozen-modernized
python3 "${HERMES_SKILL_DIR}/scripts/check-m4-floor-receipts.py" \
  /path/to/frozen-modernized/evidence/receipts/m4-floor/<run-id>
# dry fixtures
python3 "${HERMES_SKILL_DIR}/scripts/check-m4-floor-receipts.py" \
  /projects/modernized/governance/fixtures/m4-floor/known-good
```

## Chaos matrix (plan #7)

Timeout, process death, dup dispatch, digest mismatch, and gate refusal —
exercised together; each must leave a named Kanban/verdict terminal. Uses
Hermes-native `enforce_max_runtime` / `detect_crashed_workers` / idempotency
(no LLM spawn; AD-004).

```bash
HERMES_AGENT_ROOT="${HOME}/.hermes/hermes-agent"
"${HERMES_AGENT_ROOT}/venv/bin/python" \
  "${HERMES_SKILL_DIR}/scripts/run-chaos-matrix.py" /projects/modernized \
  --out /tmp/chaos-7-out --board chaos-matrix-7
```

## Available scripts

Full inventory: `references/available-scripts.md` (UPLIFT-4). Includes
`write-receipt.py` (creates the receipts `check-m4-floor-receipts.py` validates).

## Verification

- `check-phase-matrix.py` prints `OK: AD-H §18 phase-matrix present in
  phase-dispatch.yaml` after one `OK: <phase> required_checks cover §18 matrix`
  line per phase; a missing check names the phase and the absent ids.
- `check-verdict-routing.py` prints `OK: verdict-routing checks passed (N
  artifact(s))`. **Silent-failure assertion: N must be > 0.** `N = 0` — or the
  idle line `OK: no verdict/preflight artifacts — routing lint idle` — means
  nothing was policed, not that the phase is clean. The same rule applies to the
  idle lines from `check-factory-m5.py`, `check-candidate-promote.py`,
  `check-accept-scope.py`, `check-side-effect-recovery.py` and
  `check-persisted-data-contract.py`: idle is not a pass.
- No artifact carries `ship: true` with a verdict other than a full M5 `ACCEPT`,
  no `PROVISIONAL_ACCEPT` outside M4, and no `g1_kill_ratio: PASS` without
  `g1_kill_ratio_threshold_pinned` or a typed waiver.
- M4 floor: `evidence/receipts/m4-floor/<run-id>/` holds all three receipts —
  `boot_health.json`, `endpoint_smoke.json`, `g4_hook.json`, schema
  `rhoai3.gate-receipt/v1` — and `check-m4-floor-receipts.py` prints `OK: M4
  floor receipts complete`. `boot_health`/`endpoint_smoke` must be `PASS`;
  `g4_hook` `INCONCLUSIVE` is honest for the SAMPLE floor, `REFUSE` fails.
  Every receipt has `ad010_demo: false` —   floor green is not `release_qualified`. B8: health-only smoke →
  `endpoint_smoke_health`; `check-semantics-manifest.py` must pass.
- Wall/crash: each terminal has `evidence/runs/<task>/exit-eval.json` with
  schema `rhoai3.exit-eval/v1`; `apply-wall-requeue-policy.py` exit 2 is the
  hard ceiling (block, do not requeue) and must not be read as a soft pass.
- Conformance lint passes for this skill.

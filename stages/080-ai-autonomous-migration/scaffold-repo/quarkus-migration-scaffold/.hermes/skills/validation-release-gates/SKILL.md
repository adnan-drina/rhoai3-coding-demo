---
name: validation-release-gates
description: >
  AD-H §18 / §18.0 validation and release gates — phase required_checks matrix,
  provisional vs full ACCEPT, kill-ratio pending_threshold, verdict routing,
  factory↔M5 full ACCEPT oracle. Use for M4/M5 validator seats and harness-validate.
---

# Validation and release gates (AD-H §18 / §18.0)

## Contracts

- `migration/contracts/validation-release-gates.md`
- `migration/schemas/verdict.md`
- Phase `required_checks` + `accept_kind`: `.hermes/phase-dispatch.yaml`

**§18.0:** M4 verdict = literal `PROVISIONAL_ACCEPT` (never ship); M5 = `ACCEPT`
(G-4); shared-substrate reopen = closure ∩ implicated; kill-ratio `PASS`
forbidden until threshold pinned — use `pending_threshold` or typed waiver.

## Checks

```bash
# Assert phase-dispatch matrix matches §18 (M3/M4/M5)
python3 "${HERMES_SKILL_DIR}/scripts/check-phase-matrix.py" /projects/modernized

# Print checklist for a phase
python3 "${HERMES_SKILL_DIR}/scripts/check-phase-matrix.py" /projects/modernized --print M4

# Verdict routing + §18.0 composition
python3 "${HERMES_SKILL_DIR}/scripts/check-verdict-routing.py" /projects/modernized

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
python3 "${HERMES_SKILL_DIR}/../domain-gates/scripts/check-product-tests.py" /projects/modernized

# S-010 Class A — assertj-core + rest-assured in pom (harness-owned toolchain)
python3 "${HERMES_SKILL_DIR}/scripts/check-test-toolchain.py" /projects/modernized

# Architect E-110403Z / E-121300Z — wall exit-eval + soft K requeue policy
python3 "${HERMES_SKILL_DIR}/scripts/evaluate-exit-criteria.py" /projects/modernized \
  --body migration/bodies/m3-s-010.json --task-id t_xxx --trigger timed_out
python3 "${HERMES_SKILL_DIR}/scripts/check-wall-exit-eval.py" /projects/modernized \
  --task-id t_xxx --trigger timed_out --require-test-compile
python3 "${HERMES_SKILL_DIR}/scripts/apply-wall-requeue-policy.py" /projects/modernized \
  --task-id t_xxx --body migration/bodies/m3-s-010.json --k-soft 1

# Architect E-20260810T142650Z — crash requeue ceiling (does not spend wall soft-K)
python3 "${HERMES_SKILL_DIR}/scripts/apply-crash-requeue-policy.py" /projects/modernized \
  --task-id t_xxx --k-crash 1 --cause harness_fault --stamp
```

Contracts: `migration/contracts/workspace-recovery.md`,
`migration/contracts/runnable-db-security.md`,
`migration/contracts/product-tests.md`,
`migration/contracts/test-toolchain.md`,
`migration/contracts/wall-exit-eval.md`,
`migration/contracts/crash-requeue.md`.

Domain-gate oracles (G-1…G-4) remain authoritative; this skill does not replace them.

## M4 floor runner (R-HX.9 Phase-2)

Minimum ordered runner for Phase-3 dual-arm verify — **not** full AD-010.

Contract: `migration/contracts/m4-floor-runner.md`  
Schema: `migration/schemas/gate-receipt.md`

```bash
bash "${HERMES_SKILL_DIR}/scripts/run-m4-floor.sh" /path/to/frozen-modernized
python3 "${HERMES_SKILL_DIR}/scripts/check-m4-floor-receipts.py" \
  /path/to/frozen-modernized/migration/receipts/m4-floor/<run-id>
# dry fixtures
python3 "${HERMES_SKILL_DIR}/scripts/check-m4-floor-receipts.py" \
  /projects/modernized/migration/fixtures/m4-floor/known-good
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

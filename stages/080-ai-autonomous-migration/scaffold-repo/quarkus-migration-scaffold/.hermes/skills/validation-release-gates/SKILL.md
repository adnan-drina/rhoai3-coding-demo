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
```

Domain-gate oracles (G-1…G-4) remain authoritative; this skill does not replace them.

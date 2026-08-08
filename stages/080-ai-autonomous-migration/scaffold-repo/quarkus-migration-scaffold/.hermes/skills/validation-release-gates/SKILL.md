---
name: validation-release-gates
description: >
  AD-H §18 validation and release gates — phase required_checks matrix,
  cheap verdict routing (INCONCLUSIVE never ships), preflight checklist print.
  Use for M4/M5 validator seats and harness-validate.
---

# Validation and release gates (AD-H §18)

## Contracts

- `migration/contracts/validation-release-gates.md`
- Phase `required_checks`: `.hermes/phase-dispatch.yaml`

## Checks

```bash
# Assert phase-dispatch matrix matches §18 (M3/M4/M5)
python3 "${HERMES_SKILL_DIR}/scripts/check-phase-matrix.py" /projects/modernized

# Print checklist for a phase
python3 "${HERMES_SKILL_DIR}/scripts/check-phase-matrix.py" /projects/modernized --print M4

# Verdict routing: refuse INCONCLUSIVE-as-ship / wrong routing class
python3 "${HERMES_SKILL_DIR}/scripts/check-verdict-routing.py" /projects/modernized

# Factory must not contradict M5 ACCEPT (required oracle)
python3 "${HERMES_SKILL_DIR}/scripts/check-factory-m5.py" /projects/modernized
```

Domain-gate oracles (G-1…G-4) remain authoritative; this skill does not replace them.

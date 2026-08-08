---
name: harness-validate
description: >
  Specimen-free harness validation entrypoint: scaffold invariants, SDD
  readiness, domain-gate admission fixtures, mta-findings schema, inventory
  smoke, role-authority acks/writes. Use before trusting a workspace or after
  gate/toolchain changes.
---

# Harness validate

## Procedure

From the modernized project root:

```bash
bash "${HERMES_SKILL_DIR}/scripts/validate.sh"
```

Or, with skills on `external_dirs`, load this skill and run the script above.
Does **not** require a provisioned specimen.

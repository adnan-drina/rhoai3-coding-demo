---
name: auditability-repeatability
description: >
  AD-H §19 generation provenance lint — fail closed on missing
  worker_session_id / mandatory fields for non-trivial IMPLEMENT; derive apply
  log named in artifacts[]. Idle when no IMPLEMENT provenance exists.
---

# Auditability and repeatability (AD-H §19)

## Contracts

- `migration/contracts/auditability-repeatability.md`
- `migration/schemas/generation-provenance.md`

## Checks

```bash
python3 "${HERMES_SKILL_DIR}/scripts/check-provenance.py" /projects/modernized
```

Looks under `migration/provenance/*.json` and task JSON `provenance` /
`metadata` / `completion_metadata` fields.

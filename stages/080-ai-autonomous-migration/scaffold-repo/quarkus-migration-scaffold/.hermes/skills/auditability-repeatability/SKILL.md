---
name: auditability-repeatability
description: >
  AD-H §19 generation provenance lint + reconstruct-from-commit — fail closed
  on missing worker_session_id / mandatory fields for non-trivial IMPLEMENT;
  derive apply log named in artifacts[]. Reconstruct packet/loci/SOUL/skills/
  session/gates/approval from any IMPLEMENT commit or refuse. Idle lint when
  no IMPLEMENT provenance exists.
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

## Reconstruction (plan #6 / AD-H §19.1)

From any IMPLEMENT commit (subject carries `task_id`), rebuild packet, loci,
skill/SOUL tips, session, gates, and approval — or **fail closed**:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/reconstruct-from-commit.py" \
  /projects/modernized [<commit-ish>] -o /tmp/reconstruct.json
```

Missing `worker_session_id`, unresolved session store, non-git-sha
`skill_tips`, missing acks, or missing gate verdict → exit 1. Never invent.

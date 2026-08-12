---
name: auditability-repeatability
description: Prove auditability and repeatability
version: 1.1.0
author: rhoai3-harness-team
license: Apache-2.0
platforms: [linux]
metadata:
  hermes:
    tags:
    - harness
    - orchestration
    category: harness
---
## When to Use

Use this skill when its name matches the active phase or gate.


# Auditability and repeatability (AD-H §19)

## Contracts

- `migration/contracts/auditability-repeatability.md`
- `migration/schemas/generation-provenance.md`

## Procedure

Run the checks below.

## Checks

```bash
python3 "${HERMES_SKILL_DIR}/scripts/check-provenance.py" /projects/modernized

# Architect E-111424Z — refuse body digest drift after dispatch
python3 "${HERMES_SKILL_DIR}/scripts/check-body-digest-match.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/check-body-digest-match.py" /projects/modernized \
  --body migration/bodies/m3-s-010.json --expect <card-digest>

# AD-H §16.9 / AR-4.3 — body digest stamp + run journal pre/post digests
python3 "${HERMES_SKILL_DIR}/scripts/stamp-body-digest.py" \
  /projects/modernized/migration/bodies/m3-s-010.json
python3 "${HERMES_SKILL_DIR}/scripts/check-run-digests.py" /projects/modernized

# S-010 Class A #3 — implementer checkpoint / resume seam
python3 "${HERMES_SKILL_DIR}/scripts/init-implementer-checkpoint.py" \
  /projects/modernized/migration/bodies/m3-s-010.json --task-id t_example \
  --root /projects/modernized
# src/test stamp runs scoped test-compile gate (REFUSE if in-scope red)
python3 "${HERMES_SKILL_DIR}/scripts/run-scoped-compile-gate.py" /projects/modernized \
  --task-id t_example --body migration/bodies/m3-s-010.json --goal test-compile
python3 "${HERMES_SKILL_DIR}/scripts/stamp-implementer-checkpoint.py" \
  /projects/modernized/migration/runs/t_example/checkpoint.json \
  --body /projects/modernized/migration/bodies/m3-s-010.json \
  --completed src/test/java/com/demo/rest/OwnerRestControllerTests.java
# Harness-driven catch-up when stamp was skipped (Deputy E-121112Z)
python3 "${HERMES_SKILL_DIR}/scripts/check-test-write-checkpoint-lag.py" \
  /projects/modernized/migration/runs/t_example/checkpoint.json --root /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/sync-checkpoint-from-test-writes.py" \
  /projects/modernized/migration/runs/t_example/checkpoint.json --root /projects/modernized \
  --body /projects/modernized/migration/bodies/m3-s-010.json
python3 "${HERMES_SKILL_DIR}/scripts/check-implementer-checkpoint.py" \
  /projects/modernized/migration/runs/t_example/checkpoint.json
```

Looks under `migration/provenance/*.json` and task JSON `provenance` /
`metadata` / `completion_metadata` fields. Run journals: `migration/runs/`
(`migration/schemas/run-journal.md`). Checkpoints:
`migration/schemas/implementer-checkpoint.md` /
`migration/contracts/implementer-checkpoint.md`.

## Reconstruction (plan #6 / AD-H §19.1)

From any IMPLEMENT commit (subject carries `task_id`), rebuild packet, loci,
skill/SOUL tips, session, gates, and approval — or **fail closed**:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/reconstruct-from-commit.py" \
  /projects/modernized [<commit-ish>] -o /tmp/reconstruct.json
```

Missing `worker_session_id`, unresolved session store, non-git-sha
`skill_tips`, missing acks, or missing gate verdict → exit 1. Never invent.


## Verification

- Scripts under `scripts/` exit 0 on a healthy seat.
- Conformance lint passes for this skill.

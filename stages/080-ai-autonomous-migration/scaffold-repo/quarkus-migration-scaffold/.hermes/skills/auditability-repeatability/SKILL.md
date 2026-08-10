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
# src/test stamp runs mvn test-compile gate (REFUSE if red)
python3 "${HERMES_SKILL_DIR}/scripts/run-test-compile-gate.py" /projects/modernized \
  --task-id t_example --paths src/test/java/com/demo/rest/OwnerRestControllerTests.java
python3 "${HERMES_SKILL_DIR}/scripts/stamp-implementer-checkpoint.py" \
  /projects/modernized/migration/runs/t_example/checkpoint.json \
  --completed src/test/java/com/demo/rest/OwnerRestControllerTests.java
# Harness-driven catch-up when stamp was skipped (Deputy E-121112Z)
python3 "${HERMES_SKILL_DIR}/scripts/check-test-write-checkpoint-lag.py" \
  /projects/modernized/migration/runs/t_example/checkpoint.json --root /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/sync-checkpoint-from-test-writes.py" \
  /projects/modernized/migration/runs/t_example/checkpoint.json --root /projects/modernized
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

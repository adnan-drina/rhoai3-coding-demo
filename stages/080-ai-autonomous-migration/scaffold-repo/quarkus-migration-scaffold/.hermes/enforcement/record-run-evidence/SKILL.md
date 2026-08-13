---
name: record-run-evidence
description: Prove an M3 run replayable before complete or resume — provenance, body digests, checkpoint
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; git for commit audits
metadata:
  author: rhoai3-harness-team
  version: "1.2.0"
  hermes:
    tags:
    - harness
    - orchestration
    category: harness
    kind: enforcement
---
## When to Use

- An M3 implementer card is about to `kanban_complete` — provenance,
  body digest and checkpoint must be proven before the claim lands.
- Resuming a requeued / re-dispatched M3 task: read `next` from
  `evidence/runs/<task_id>/checkpoint.json` instead of cold re-walking
  operands already marked `completed`.
- After a destination write under `src/test/**` — the stamp runs a scoped
  test-compile gate and REFUSEs on in-scope red.
- Auditing a shipped commit: rebuild packet · loci · SOUL/skill tips ·
  session · gates · approval from the commit subject alone.
- Whether the *text* cites a brief and a legacy locus is `ground-in-harvest`.
  This skill proves the *run* is replayable — digests, session, resume state.

# Auditability and repeatability (AD-H §19)

## Contracts

- `governance/contracts/auditability-repeatability.md`
- `governance/contracts/body-immutability.md`
- `governance/contracts/implementer-checkpoint.md`
- `governance/schemas/generation-provenance.md`, `run-journal.md`,
  `implementer-checkpoint.md`

## Procedure

1. **Stamp the body digest before create/dispatch.** Writes
   `<body>.json.sha256.json` (`rhoai3.body-digest/v1`) and echoes the 64-hex
   digest on the last stdout line.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/stamp-body-digest.py" \
  /projects/modernized/evidence/bodies/m3-s-010.json
```

2. **Refuse body drift after dispatch.** With `--body` alone the check is
   scoped to that body's own sidecar (parked siblings must not fail it);
   with `--expect <card-digest>` it compares against the card.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/check-body-digest-match.py" /projects/modernized \
  --body evidence/bodies/m3-s-010.json
python3 "${HERMES_SKILL_DIR}/scripts/assert-card-body-digest-match.py" /projects/modernized \
  --task-id t_example --body evidence/bodies/m3-s-010.json
```

3. **Init the resume seam before the first destination edit.** `work_list`
   is derived from the body's `files_writable` (else `files_in_scope`),
   `src/`-relative dest paths only.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/init-implementer-checkpoint.py" \
  /projects/modernized/evidence/bodies/m3-s-010.json --task-id t_example \
  --root /projects/modernized
```

4. **Gate then stamp after each write.** A `src/test/**` operand triggers the
   scoped gate automatically; OOS-only errors pass, in-scope errors REFUSE.
   `--skip-test-compile-gate` is fixture-only.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/run-scoped-compile-gate.py" /projects/modernized \
  --task-id t_example --body evidence/bodies/m3-s-010.json --goal test-compile
python3 "${HERMES_SKILL_DIR}/scripts/stamp-implementer-checkpoint.py" \
  /projects/modernized/evidence/runs/t_example/checkpoint.json \
  --body /projects/modernized/evidence/bodies/m3-s-010.json \
  --completed src/test/java/com/example/rest/SomeResourceTest.java
```

5. **Catch skipped stamps.** Voluntary stamping decays — detect the lag, then
   let the harness gate-and-stamp it.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/check-test-write-checkpoint-lag.py" \
  /projects/modernized/evidence/runs/t_example/checkpoint.json --root /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/sync-checkpoint-from-test-writes.py" \
  /projects/modernized/evidence/runs/t_example/checkpoint.json --root /projects/modernized \
  --body /projects/modernized/evidence/bodies/m3-s-010.json
```

6. **Verify before completing.** Checkpoint shape + run-journal / sidecar
   digests + provenance fields.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/check-implementer-checkpoint.py" \
  /projects/modernized/evidence/runs/t_example/checkpoint.json
python3 "${HERMES_SKILL_DIR}/scripts/check-run-digests.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/check-provenance.py" /projects/modernized
```

`check-provenance.py` reads `evidence/provenance/*.json` plus the
`provenance` / `metadata` / `completion_metadata` fields of
`evidence/tasks/*.json` and `evidence/kanban/*.json`. It requires
`task_id`, `task_run_id`, `worker_session_id`, `soul_path` + `soul_sha`,
`skill_tips`, `model_id`, and `citations{brief_or_story_id, legacy_locus}`.
`soul_sha` is re-hashed against the **loaded** SOUL path
(`resolve_loaded_soul.py`: `$HERMES_HOME` → `~/.hermes` → repo home → repo).
`model_id: unknown` needs `model_id_gap: true`.

## Reconstruction (AD-H §19.1)

From any IMPLEMENT commit (subject carries `t_<hex>`), rebuild every mandatory
link — or **fail closed**:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/reconstruct-from-commit.py" \
  /projects/modernized [<commit-ish>] -o /tmp/reconstruct.json
```

Missing `worker_session_id`, unresolved session store, non-git-sha
`skill_tips`, `soul_sha` mismatch vs provenance, no gate verdict, or no ack →
`verdict: REFUSE`, exit 1. Never invent a session id, ack, or gate row.

## Verification

- `evidence/runs/<task_id>/checkpoint.json` carries schema
  `rhoai3.implementer-checkpoint/v1`, `completed ⊆ work_list` with no
  duplicates, 64-hex `body_sha256`, and `next` equal to the first uncompleted
  entry — `check-implementer-checkpoint.py` recomputes `next` and exits 1 on drift.
- `run-scoped-compile-gate.py` wrote
  `evidence/runs/<task_id>/scoped-test-compile-gate.json` with `"ok": true`
  and empty `in_scope_errors`.
- `<body>.json.sha256.json` exists and its `body_sha256` equals sha256 of the
  live body; `--body` without a sidecar is a REFUSE, not a skip.
- **Silent-failure catch:** a green stamp proves nothing if stamping was
  skipped. `check-test-write-checkpoint-lag.py` must print
  `OK: no src/test checkpoint lag` — it exits 1 whenever a `src/test/**`
  work_list path exists on disk but is unstamped.
- `check-provenance.py` prints `OK: … (N artifact(s))` with N ≥ 1. The
  `§19 lint idle` line means it found nothing to check — treat as unproven.
- `reconstruct-from-commit.py` emits `"verdict": "ACCEPT"` with every
  `mandatory_ok` key true and `gaps: []`; any gap ⇒ exit 1.

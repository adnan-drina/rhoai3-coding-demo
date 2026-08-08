# Kanban `body` schema (W2 §6.1)

**Status:** binding · mirrors Architect §6.1  
**Lint:** `.hermes/skills/sdd-readiness/scripts/check-kanban-body.py`

Typed object only (JSON under `migration/tasks/*.json` field `body`, or
standalone `migration/bodies/*.json`). Free prose as the whole body → refuse.

## Shared shape

| Field | Type | Rule |
|-------|------|------|
| `task_id` | string | §7.5 correlation |
| `role` | string | AD-H §16 role |
| `phase` | `M1`…`M5` \| `factory` | |
| `refs` | list of `{ key, path, sha256 }` | digest-anchored only |
| `identity` | object | `story_id` / `brief_id` / `ac_ids` as phase requires |
| `files_in_scope` | list | **M3 required non-empty** |

**Forbidden in body:** inline findings blobs, pasted file contents, derived
analysis prose as authority.

## Required `refs[].key` by phase

| Phase | Required keys (min) | Also allowed |
|-------|---------------------|--------------|
| M1 | `harvest_referent` | `legacy_at_3_manifest` |
| M2 | `mta_findings`, `m1_findings_ack` | `entry_point_inventory`, `brief_draft` |
| M3 | `brief_identity_ack`, `legacy_locus` | `spec_path`, `plan_path`, `derive_apply_log` |
| M4 | `story_tip` | `g1_fixture`, `g2_fixture` |
| M5 | `m4_verdict`, `mta_rescan_input` | `g3_baseline`, `g4_inventory` |
| factory | `m5_accept` | — |

## Failure codes (print verbatim)

| Code | Template |
|------|----------|
| `BODY_SCHEMA` | `BODY_SCHEMA: body must be typed object with task_id, role, phase, refs[]` |
| `BODY_INLINE` | `BODY_INLINE: body must not carry derived content (digest refs only)` |
| `BODY_REF_MISSING` | `BODY_REF_MISSING: phase={phase} missing ref key={key}` |
| `BODY_REF_DIGEST` | `BODY_REF_DIGEST: key={key} path={path} expected={sha} actual={sha_or_error}` |
| `BODY_REF_UNKNOWN` | `BODY_REF_UNKNOWN: key={key} not in phase vocabulary` |
| `BODY_SCOPE` | `BODY_SCOPE: M3 requires non-empty files_in_scope` |

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
| `files_in_scope` | list | **M3 required non-empty** — see dual-path rule below |
| `exit_criteria` | list of objects | **M3/M4/M5 required non-empty** — falsifiable done-when |

**M3 `files_in_scope` dual-path (Deputy `E-20260809T220100Z`):** each
legacy/referent path must be paired with its destination write path (same list,
legacy then dest, or both present). Legacy-only lists cannot detect out-of-bounds
writes. PetClinic map: `/projects/.derived/legacy-at-3/…` →
`/projects/modernized/…`, and `org/springframework/samples/petclinic` → `com/demo`
under `src/{main,test}/java`.

Each `exit_criteria[]` item is an object with a short `check` id and either:
- `{ "check", "cmd", "expect" }` — shell command (e.g. `expect: "rc=0"`), or
- `{ "check", "assert" }` — named assertion the worker must verify before
  `kanban_complete` (e.g. scope / residue).

**M3 required check id `skills` (AD-002D):** assert consult via `skill_view` (or
equivalent) for ≥1 phase skill, **or** typed `skills_unused:<reason>` in the
completion comment. Silence is not a typed negative.

**Optional `runtime_budget_sec` (AD-010 §3b):** integer seconds when
`effort_class` is high. Create-helper passes it as `--max-runtime`. Do **not**
raise the phase-wide default from one sample.

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
| `BODY_SCOPE_DEST` | `BODY_SCOPE_DEST: M3 files_in_scope needs destination paths (not legacy-only)` |
| `BODY_EXIT` | `BODY_EXIT: phase={phase} requires non-empty exit_criteria[]` |

# Auditability and repeatability

**Status:** binding for migration workspace · mirrors **AD-H §19**
**Basis:** AD-H §19; forks
(`source-analysis/ad-challenge-pass/20260808-adh-19-forks.md`)
**Placement:** this golden scaffold only (consumed in `/projects/modernized`).

Cross-refs: AD-H §7.5, §16–§18, W2 §6 digests, W2 §12.3 derive apply log,
`governance/schemas/generation-provenance.md`.

## Reconstruction (task-id join)

Five surfaces: Kanban · Hermes sessions/logs · git · gate results · run report.
Every surface carries **task id**. Start at an IMPLEMENT commit → recover
legacy tip, MTA evidence, derive RULES/apply log, brief/packet, provenance,
tests/gates.

## Mandatory provenance (non-trivial IMPLEMENT)

| Field | Rule |
|-------|------|
| `task_id` | Commit subject |
| `task_run_id` | Hermes `task_runs` id for this execution — **fail closed** if missing |
| `worker_session_id` | Hermes-stamped on `kanban_complete` — **fail closed** if missing |
| `soul_sha` + `soul_path` | sha256 of the **loaded** SOUL (`$HERMES_HOME` / `~/.hermes` first) |
| `skill_tips` | name→git sha for phase `skills[]` preload |
| §17 citations | brief/story + legacy locus |
| `model_id` | config / `model_override` when present; `unknown` + `model_id_gap: true` only if neither readable — gap ≠ full reconstruction |

**Deferred:** `maas_endpoint_fingerprint`, `prompt_bundle_id`.

## Homes (no equal dual-write)

| Surface | Role |
|---------|------|
| Kanban completion `metadata` | **Authoritative** structured provenance |
| git commit subject | `task_id` only |
| `evidence/provenance/<task_id>.json` | Optional export from Kanban (one direction); path in `artifacts[]` |

## Digests vs approvals

Digests / hashes prove loaded inputs. Approvals live in `evidence/acks/` and
`mta-exception` rationale — digests do **not** replace acks.

## Early metric

**Unsupported claims** (§17) → refuse / `blocked`. No second threshold here.
Secondary: failed validation, rework, task-order reversals, human overrides.

## Enforcement

| Piece | Path |
|-------|------|
| Provenance schema | `governance/schemas/generation-provenance.md` |
| Cheap lint | `.hermes/enforcement/record-run-evidence/scripts/check-provenance.py` |
| Reconstruct | `.hermes/enforcement/record-run-evidence/scripts/reconstruct-from-commit.py` |
| Wired into | `validate-contracts` (path-invoke); create/complete harness — **not** M3 `skills[]` |

```bash
python3 .hermes/enforcement/record-run-evidence/scripts/check-provenance.py .
python3 .hermes/enforcement/record-run-evidence/scripts/reconstruct-from-commit.py . [<commit>] -o /tmp/reconstruct.json
```

Derive apply log must appear in `artifacts[]` when `derive-legacy-boot3`
`derive_apply_log` is in play (W2 §12.3).

**Fail closed:** unlinkable IMPLEMENT commit, missing `worker_session_id`,
unresolved session store, narrative `skill_tips` without git sha, missing
gate verdict, or missing required acks → reconstruction `REFUSE` (exit 1).

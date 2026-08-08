# Auditability and repeatability

**Status:** binding for migration workspace · mirrors **AD-H §19**  
**Sources:** Architect AD-H §19; Research forks `E-20260808T074820Z`
(`source-analysis/ad-challenge-pass/20260808-adh-19-forks.md`)  
**Placement:** this golden scaffold only (consumed in `/projects/modernized`).

Cross-refs: AD-H §7.5, §16–§18, W2 §6 digests, W2 §12.3 derive apply log,
`migration/schemas/generation-provenance.md`.

## Reconstruction (task-id join)

Five surfaces: Kanban · Hermes sessions/logs · git · gate results · run report.
Every surface carries **task id**. Start at an IMPLEMENT commit → recover
legacy tip, MTA evidence, derive RULES/apply log, brief/packet, provenance,
tests/gates.

## Mandatory provenance (non-trivial IMPLEMENT)

| Field | Rule |
|-------|------|
| `task_id` | Commit subject |
| `worker_session_id` | Hermes-stamped on `kanban_complete` — **fail closed** if missing |
| `soul_sha` | sha256 of `.hermes/SOUL.md` at commit |
| `skill_tips` | name→git sha for phase `skills[]` preload |
| §17 citations | brief/story + legacy locus |
| `model_id` | config / `model_override` when present; `unknown` + `model_id_gap: true` only if neither readable — gap ≠ full reconstruction |

**Deferred:** `maas_endpoint_fingerprint`, `prompt_bundle_id`.

## Homes (no equal dual-write)

| Surface | Role |
|---------|------|
| Kanban completion `metadata` | **Authoritative** structured provenance |
| git commit subject | `task_id` only |
| `migration/provenance/<task_id>.json` | Optional export from Kanban (one direction); path in `artifacts[]` |

## Digests vs approvals

Digests / hashes prove loaded inputs. Approvals live in `migration/acks/` and
`mta-exception` rationale — digests do **not** replace acks.

## Early metric

**Unsupported claims** (§17) → refuse / `blocked`. No second threshold here.
Secondary: failed validation, rework, task-order reversals, human overrides.

## Enforcement (Lead)

| Piece | Path |
|-------|------|
| Provenance schema | `migration/schemas/generation-provenance.md` |
| Cheap lint | `.hermes/skills/auditability-repeatability/scripts/check-provenance.py` |
| Wired into | `harness-validate`; M3 `skills[]` |

```bash
python3 .hermes/skills/auditability-repeatability/scripts/check-provenance.py .
```

Derive apply log must appear in `artifacts[]` when `derive-legacy-boot3` /
`derive_apply_log` is in play (W2 §12.3).

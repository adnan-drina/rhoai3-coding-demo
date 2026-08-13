# Migration ack schema (AD-H §16.3)

**Status:** stub — bind when phase advance checks land  
**Home:** `evidence/acks/<ack_type>.ack.yaml` (or `.ack.json`)

Human checkpoints are **ack artifacts**, not Hermes interactive approvals.

## Creation-time body refs (Deputy `E-20260811T131200Z`)

M2b `create-m3-implementer.sh` runs **before** Operator writes
`brief-identity*.ack.yaml`. M3 bodies therefore **MUST** carry:

```json
{"key":"brief_identity_ack","path":"evidence/acks/brief-identity-<story>.ack.yaml","sha256":"pending"}
```

`sha256: "pending"` is the only typed creation-time deferral (see
`kanban-body.md`). Substituting `partition.json` (or any other extant file) as
the ack digest is a schema improvisation — refuse on next create. When the
Operator ack lands, first-implement (or Lead amend) replaces `pending` with the
real 64-hex digest of that ack file.

## Required fields

| Field | Type | Rule |
|-------|------|------|
| `kind` | string | always `migration-ack` |
| `ack_type` | string | `m1-findings` \| `brief-identity` \| (future typed acks) |
| `status` | string | `acknowledged` (only accepted value for advance) |
| `acknowledged_by` | string | **Human / authenticated external signer** — **not** worker roles (`planner`, `implementer`, `default`, …) (AR-1.1) |
| `acknowledged_at` | string | ISO-8601 UTC |
| `task_id` | string | **Required** Kanban task id binding the grant (AR-1.1) |
| `artifact_digests` | object/list | **Required** immutable digests of brief/plan/findings (AR-1.1) |
| `artifact_refs` | list | Paths covered; prefer digest-bearing entries (`sha256`) |
| `notes` | string | optional |

Prefer `*.ack.yaml` / `*.ack.json`. Bare `evidence/acks/*.json` self-grants
are **refused** by `check-ack-authority.py`.

## Examples

`evidence/acks/m1-findings.ack.yaml`:

```yaml
kind: migration-ack
ack_type: m1-findings
status: acknowledged
acknowledged_by: Operator
acknowledged_at: 2026-08-08T00:00:00Z
artifact_refs:
  - evidence/mta-findings.json
  - evidence/entry-point-inventory.json
notes: "Exceptions set empty; open Q-* none"
```

`evidence/acks/brief-identity.ack.yaml` (per story — may use
`brief-identity-<story_id>.ack.yaml`):

```yaml
kind: migration-ack
ack_type: brief-identity
status: acknowledged
acknowledged_by: Operator
acknowledged_at: 2026-08-08T00:00:00Z
artifact_refs:
  - story_id: S-001
  - evidence/briefs/S-001.md
notes: "Non-Goals + AC set accepted"
```

## Fail closed

Skill `enforce-authority-boundary` refuses phase advance when
`.hermes/phase-dispatch.yaml` `requires_acks` are missing or not
`status: acknowledged`.

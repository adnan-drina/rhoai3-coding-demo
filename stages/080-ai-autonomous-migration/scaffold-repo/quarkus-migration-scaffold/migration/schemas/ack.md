# Migration ack schema (AD-H §16.3)

**Status:** stub — bind when phase advance checks land  
**Home:** `migration/acks/<ack_type>.ack.yaml` (or `.ack.json`)

Human checkpoints are **ack artifacts**, not Hermes interactive approvals.

## Required fields

| Field | Type | Rule |
|-------|------|------|
| `kind` | string | always `migration-ack` |
| `ack_type` | string | `m1-findings` \| `brief-identity` \| (future typed acks) |
| `status` | string | `acknowledged` (only accepted value for advance) |
| `acknowledged_by` | string | Human identity / role (Operator, steerer, …) |
| `acknowledged_at` | string | ISO-8601 UTC |
| `artifact_refs` | list | Digests/paths covered (findings file, brief id, …) |
| `notes` | string | optional |

## Examples

`migration/acks/m1-findings.ack.yaml`:

```yaml
kind: migration-ack
ack_type: m1-findings
status: acknowledged
acknowledged_by: Operator
acknowledged_at: 2026-08-08T00:00:00Z
artifact_refs:
  - migration/mta-findings.json
  - migration/entry-point-inventory.json
notes: "Exceptions set empty; open Q-* none"
```

`migration/acks/brief-identity.ack.yaml` (per story — may use
`brief-identity-<story_id>.ack.yaml`):

```yaml
kind: migration-ack
ack_type: brief-identity
status: acknowledged
acknowledged_by: Operator
acknowledged_at: 2026-08-08T00:00:00Z
artifact_refs:
  - story_id: S-001
  - migration/briefs/S-001.md
notes: "Non-Goals + AC set accepted"
```

## Fail closed

Skill `role-authority` refuses phase advance when
`.hermes/phase-dispatch.yaml` `requires_acks` are missing or not
`status: acknowledged`.

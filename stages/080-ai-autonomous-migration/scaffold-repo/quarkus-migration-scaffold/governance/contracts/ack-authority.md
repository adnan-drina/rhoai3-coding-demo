# ACK + comment authority (AD-H §16.5 / AR-1.1 / AR-1.2)

**Status:** binding proving-min · extends F2 write fence
**Basis:** in-tree harness obligations (sibling contracts + skills).

## AR-1.1 — Self-ACK refuse

- Worker roles (`planner`, `implementer`, …) **MUST NOT** be `acknowledged_by`
- Required: `task_id` + `artifact_digests` (or digest-bearing `artifact_refs`)
- Bare `evidence/acks/*.json` grants without `.ack.` naming are forgeable — refuse
- Live `brief-identity.json` with `acknowledged_by: planner` is **not** stage authority
- **Creation-time M3 bodies** may cite `brief_identity_ack` with
 `sha256: "pending"` and the intended future ack path — that is **not** a
 self-ACK; phase advance still requires a real human ack artifact
 (`kanban-body.md`)

```bash
python3 .hermes/enforcement/enforce-authority-boundary/scripts/check-ack-authority.py .
```

## AR-1.2 — Comments ≠ authority

- `default` / worker comments claiming `OVERRIDE (steward)` **MUST NOT** drive dispatch
- Control-flow changes use `governance/schemas/typed-revision.md` envelopes only

```bash
python3 .hermes/enforcement/enforce-authority-boundary/scripts/check-comment-authority.py .
```

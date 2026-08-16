# Ack artifact (AR-1.1)

Operator/Lead stage-advance grants live in `evidence/acks/*.ack.yaml`
(or `*.ack.json`). Workers do not author these files.

Required fields on an `acknowledged` grant:

| Field | Rule |
|---|---|
| `kind` | `migration-ack` |
| `ack_type` | matches the phase `requires_acks` name (`m1-findings`, `brief-identity`, …) |
| `status` | `acknowledged` |
| `acknowledged_by` | human role (`Operator`, `Lead`, …) — never a worker name |
| `task_id` | the Kanban card the grant is about |
| `artifact_digests` | map of artifact → sha256 **or** `artifact_refs` entries with `sha256` |

`artifact_digests` may be an inline flow map **or** a block mapping.
`check-ack-authority.py` accepts both (Deputy `E-20260816T173510Z`: a
line-scrape treated a block mapping as empty).

Do not copy live acknowledged acks with real operator names into the
golden scaffold. Placeholders belong in `evidence/acks/README.md`.

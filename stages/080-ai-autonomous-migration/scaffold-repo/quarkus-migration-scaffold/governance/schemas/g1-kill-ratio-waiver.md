# `g1-kill-ratio-waiver` (typed M5 alternate path)

**Status:** binding · plan #8 / AD-H §18.0¶5  
**Home:** `evidence/acks/g1-kill-ratio-waiver-<story_id>.ack.yaml`

Use **only** when live PIT cannot pin a kill-ratio line, or when measured
ratio cannot meet the pin and Operator/deputy accepts the residue. This is
the **sole** alternate M5 path — never a silent skip, never a folklore %.

## Required fields

| Field | Rule |
|-------|------|
| `story_id` | Story this waiver covers |
| `authority` | `Operator` or `Deputy` (named) |
| `rationale` | Why pin path is unavailable or waived |
| `re_open_trigger` | What measurement retires the waiver |
| `expiry` | UTC date or `demo-end` |

## Effect

M5 may proceed with `g1_kill_ratio: waived` **only** when this ack exists and
validates. Digests / gate green do **not** substitute.

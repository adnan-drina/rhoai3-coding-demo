# Story partition artifact (Architect E-20260810T144540Z / R-M2.2)

**Status:** binding proving-min  
**Home:** `evidence/briefs/partition.json` (write-once seed; edit in place)

## Rule

Before freeform re-partition essays or Spec Kit slash-commands beyond the first
hard-invoke, write a durable partition. After this file exists, **do not** re-list
the full story set in Reasoning — edit the file.

## Required fields (`rhoai3.partition/v1`)

| Field | Type | Rule |
|-------|------|------|
| `schema` | string | `rhoai3.partition/v1` |
| `stories` | array | Each: `story_id`, `title`, `layer` (foundation\|model\|repo\|service\|rest\|test\|…), optional `files` / `rules` / `endpoints` |
| `ordering_basis` | string | Cite `sdd-ordering.md` / `story-sizing.md` |
| `written_at` | string | ISO-8601 UTC |
| `mta_oos` / `findings_oos` | array | optional typed out-of-scope MTA rule ids (partition-coverage gate) |

Prefer Spec Kit `spec.md` as the next artifact after partition (R-M2.3).

**M2a exit gate:** `check-partition-coverage.py` must be **VALID**
(`governance/contracts/partition-coverage.md`). Story-count variance is allowed
only when the gate passes.

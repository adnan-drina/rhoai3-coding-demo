# Typed revision envelope (AD-H §16.5 / AR-1.2)

**Status:** binding for authority changes · **not** Kanban free-text comments  
**Home:** `evidence/authority/typed-revisions/<id>.json`

Kanban comments are **not** executable. Scope/HOLD/OVERRIDE changes require
this envelope from an authenticated non-worker role.

## Required fields

| Field | Rule |
|-------|------|
| `kind` | `typed-revision` |
| `revision_id` | opaque id |
| `task_id` | Kanban task id |
| `authored_by` | Human/authenticated role — **not** `default` / worker roles |
| `authored_at` | ISO-8601 UTC |
| `change_class` | `hold` \| `unpark` \| `scope` \| `budget` \| `override` |
| `payload` | structured fields only (no prose-as-control) |
| `supersedes_comment` | optional prior comment id being replaced |

Worker-authored or missing `authored_by` → refuse.

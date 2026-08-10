# Schema: `rhoai3.implementer-checkpoint/v1` (S-010 Class A #3)

Per-task seam under `migration/runs/<task_id>/checkpoint.json`.

```json
{
  "schema": "rhoai3.implementer-checkpoint/v1",
  "task_id": "t_…",
  "body_path": "migration/bodies/m3-s-010.json",
  "body_sha256": "…",
  "work_list": [
    "src/test/java/com/demo/rest/OwnerRestControllerTests.java"
  ],
  "completed": [],
  "next": "src/test/java/com/demo/rest/OwnerRestControllerTests.java",
  "updated_at": "RFC3339Z",
  "notes": "optional"
}
```

## Invariants

- `work_list` = dest paths still owed (from `files_in_scope` / writable set).
- `completed` ⊆ `work_list` ∪ originally listed dests; no duplicates.
- `next` is first incomplete path, or `null` when done.
- Retries / re-dispatch **MUST** load checkpoint before new writes and resume
  at `next` (not cold re-walk). Body digest must match or REFUSE.

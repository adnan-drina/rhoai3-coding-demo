# Schema: `rhoai3.exit-eval/v1` (wall-as-terminal)

```json
{
  "schema": "rhoai3.exit-eval/v1",
  "task_id": "t_xxx",
  "body_path": "evidence/bodies/m3-s-010.json",
  "body_sha256": "<hex>",
  "trigger": "timed_out",
  "evaluated_at": "2026-08-10T11:00:00Z",
  "results": [
    {"check": "test_compile", "kind": "cmd", "rc": 1, "ok": false, "cmd": "mvn -q test-compile"},
    {"check": "scope", "kind": "assert", "ok": null, "status": "unevaluated_assert"}
  ],
  "cmd_failed": ["test_compile"],
  "overall_ok": false
}
```

| Field | Rule |
|-------|------|
| `trigger` | `timed_out` \| `timeout_kill` \| `gave_up` \| `complete` \| `blocked` |
| `results[].kind` | `cmd` \| `assert` |
| `overall_ok` | true iff every `cmd` result has `ok=true` |

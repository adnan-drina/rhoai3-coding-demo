# Schema: `rhoai3.run-journal/v1` (AD-H §16.9 / AR-4.3)

Per-attempt journal under `evidence/runs/<task_id>-<run_id>.json`.

```json
{
  "schema": "rhoai3.run-journal/v1",
  "task_id": "t_…",
  "run_id": "1",
  "body_path": "evidence/bodies/m3-s-010.json",
  "body_sha256": "…",
  "body_revision": "optional git tip or monotonic int",
  "pre_tree_sha256": "…",
  "post_tree_sha256": "…",
  "changed_files": [
    { "path": "src/main/java/…", "sha256": "…" }
  ],
  "recorded_at": "RFC3339Z"
}
```

## Invariants

- Worker **MUST** verify `body_sha256` matches `body_path` before first edit.
- Retries **MUST** reuse the same `body_sha256` or REFUSE.
- **Immutability (Architect E-111424Z):** dispatched body bytes MUST NOT change;
  use `check-body-digest-match.py` — see `body-immutability.md`.
- `pre_tree_sha256` / `post_tree_sha256` cover the write-set (incl. untracked).
- Create helper stamps body digest at create time (`stamp-body-digest.py`).

```bash
python3 .hermes/enforcement/record-run-evidence/scripts/stamp-body-digest.py \
  evidence/bodies/m3-s-010.json
python3 .hermes/enforcement/record-run-evidence/scripts/check-run-digests.py .
```

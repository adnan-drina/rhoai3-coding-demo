# `generation-provenance` (Kanban completion metadata)

**Status:** binding · lint `.hermes/enforcement/record-run-evidence/scripts/check-provenance.py`  
**Home:** Hermes Kanban task-run `metadata` on IMPLEMENT complete (authoritative).
Optional export: `evidence/provenance/<task_id>.json` generated **from** that
metadata (AD-H §19.3).

**Amended 2026-08-09** — Architect `E-20260809T113120Z` / AD-H §19.1–§19.2:
loaded-path `soul_sha` + `soul_path`; correlation key includes `task_run_id`.

## Correlation key (audit join)

`campaign_id` + `task_id` + `task_run_id` + `worker_session_id`

`task_id` alone is **insufficient** when multiple `task_runs` exist.

## Required fields (non-trivial IMPLEMENT)

| Field | Type | Rule |
|-------|------|------|
| `task_id` | string | Matches Kanban task id / commit subject |
| `task_run_id` | string | Hermes `task_runs` row for **this** execution — fail closed |
| `campaign_id` | string | Recommended; warn if absent |
| `worker_session_id` | string | Hermes-stamped; fail closed if absent |
| `soul_sha` | string | sha256 of the **loaded** SOUL bytes |
| `soul_path` | string | Absolute path that was hashed (must be the path Hermes loaded) |
| `skill_tips` | object | map skill name → git tree sha (phase preload) |
| `model_id` | string | config / override when present; else `unknown` |
| `model_id_gap` | bool | required `true` when `model_id` is `unknown` |
| `citations` | object | §17: `brief_or_story_id`, `legacy_locus` |

### Loaded-path rule (`soul_sha` / `soul_path`)

Resolve via `resolve_loaded_soul.py`:

1. `$HERMES_HOME/SOUL.md`
2. `~/.hermes/SOUL.md`
3. `<repo>/.hermes/home/SOUL.md`
4. `<repo>/.hermes/SOUL.md` **only if** none of the above exist

Hashing an unread project copy while the worker loaded `~/.hermes/SOUL.md` is a
P0 integrity failure.

## Optional / deferred

| Field | Notes |
|-------|-------|
| `artifacts` | list of paths (incl. derive apply log, provenance export) |
| `maas_endpoint_fingerprint` | deferred — open measurement |
| `prompt_bundle_id` | deferred — session store is trajectory home |

## Example (Kanban metadata fragment)

```json
{
  "campaign_id": "petclinic-rest-v10-refac",
  "task_id": "t_…",
  "task_run_id": "1",
  "worker_session_id": "sess_…",
  "soul_path": "/projects/modernized/.hermes/home/SOUL.md",
  "soul_sha": "…",
  "skill_tips": {
    "ground-in-harvest": "abc1234",
    "spring-to-quarkus-patterns": "def5678"
  },
  "model_id": "qwen3-6-27b",
  "citations": {
    "brief_or_story_id": "S-001",
    "legacy_locus": "src/main/java/…/CartService.java:40-88"
  }
}
```

Secrets must never appear in metadata.

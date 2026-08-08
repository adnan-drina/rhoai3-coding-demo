# `generation-provenance` (Kanban completion metadata)

**Status:** binding · lint `.hermes/skills/auditability-repeatability/scripts/check-provenance.py`  
**Home:** Hermes Kanban task-run `metadata` on IMPLEMENT complete (authoritative).
Optional export: `migration/provenance/<task_id>.json` generated **from** that
metadata (AD-H §19.3).

## Required fields (non-trivial IMPLEMENT)

| Field | Type | Rule |
|-------|------|------|
| `task_id` | string | Matches Kanban task id / commit subject |
| `worker_session_id` | string | Hermes-stamped; fail closed if absent |
| `soul_sha` | string | sha256 of `.hermes/SOUL.md` |
| `skill_tips` | object | map skill name → git tree sha (phase preload) |
| `model_id` | string | config / override when present; else `unknown` |
| `model_id_gap` | bool | required `true` when `model_id` is `unknown` |
| `citations` | object | §17: `brief_or_story_id`, `legacy_locus` |

## Optional / deferred

| Field | Notes |
|-------|-------|
| `artifacts` | list of paths (incl. derive apply log, provenance export) |
| `maas_endpoint_fingerprint` | deferred — open measurement |
| `prompt_bundle_id` | deferred — session store is trajectory home |

## Example (Kanban metadata fragment)

```json
{
  "worker_session_id": "sess_…",
  "soul_sha": "…",
  "skill_tips": {
    "grounded-generation": "abc1234",
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

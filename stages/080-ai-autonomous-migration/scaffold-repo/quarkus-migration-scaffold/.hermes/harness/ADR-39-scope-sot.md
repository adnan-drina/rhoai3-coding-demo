# ADR-39 — Story membership scope SoT (W4-617)

**Status:** accepted (operator architectural-completeness bar)  
**Supersedes as enforcement:** roadmap `- scope:` prose for `plan-lint --story-scope`  
**Related:** ADR-34 (model.stories[] membership), ADR-41/42 (`task_contract`), O-SCOPESOT, O-SCOPEVIEW  
**Partial lands that do NOT close the class:** re-syncing roadmap after re-derive (`O-M2FILLSCOPECLUBBER` is defense-in-depth on the *view renderer* only)

## Problem

Story membership was stored twice:

| Store | Role (wrong) | Writer |
|-------|----------------|--------|
| `model.stories[].units` | typed partition | `schedule_ranks` / `assign_stories` |
| `roadmap.md` `- scope:` | **also used for enforcement** | M2 seat / `m2-compose` |

`plan-lint --story-scope` and outer-loop took the prose line. A correct re-partition moved `EntityUtils` to S02 in the model while roadmap S05 still listed it → `O-M3TASKSCOPE` RED with both sides “working as designed.”

## Decision — one store, everything else a VIEW

1. **SoT:** `model.stories[].units` → `task_contract.story_scope(model, sid) -> list[legacy_path]`.
2. **Enforcement:** outer-loop sets `SCOPE` from `python3 task_contract.py story-scope --sid S0N` before every `plan-lint` / packet use. Empty typed scope → `fail_run` (no prose fallback).
3. **VIEW:** roadmap `- scope:` is rendered for humans (and brief quality). `roadmap-lint` `LINT:O-SCOPEVIEW` asserts unit-path set equality with `story_scope()`.
4. **Renderer hygiene (defense in depth):** `m2-compose` must not layer-fold typed unit paths onto another story when filling the VIEW (`O-M2FILLSCOPECLUBBER`). That does **not** replace (1)–(3).
5. **Companions (membership, not PROFILE):** `profile_units` excludes `package-info.java` (no harvest/redesign role). Those units — and `pom`/`resources` coords — are still attached into `model.stories[].units` by `attach_companion_units` after graph partition (package-dir majority for package-info; layer-or-last for coords). Non-unit staging orphans (messages, api-docs, …) fold onto the last/deploy story VIEW only (`fold_staging_orphans`) — they are not a second membership store.

## Falsifier `F-scope-derived`

No harness path may use roadmap `- scope:` prose as the **enforcement** input for O-M3TASKSCOPE when `migration/model.json` has `stories[]`. Criterion:

- **Accept:** a Target genuinely outside the typed unit set still REDs.
- **Refuse:** re-derive moving a unit across stories cannot reproduce EntityUtils-style dual-store failure — outer scope follows the model without editing roadmap.

## Out of scope for this ADR (named, not deferred silently)

- Findings ownership prose (`- findings:`) → should likewise become a VIEW of unit findings (follow-on; same pattern).
- ADR-43 Phase 2 (run-journal for all `/tmp` progress paths) — separate package; heartbeat stale-progress guards remain interim.

## Review bar

Proposals that only say “re-render roadmap after re-derive” or “skip apply_staging_scope” without moving `--story-scope` to `story_scope()` are **partial solutions** and must Verdict HOLD (see `.agents/rules/stage-080-track-b.md` § Architectural completeness).

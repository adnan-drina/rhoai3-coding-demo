# Handover mint (A-4 / A-5 / A-8)

**Status:** binding · **Authority:** Architect `E-20260816T115106Z` (A-7/A-8
closed into one post-workflow script). **OBJECT spec-kit hooks** (V20-5:
advisory).

## What it is

After native `speckit` stops at `tasks`, the orchestrator runs
`scripts/handover-mint.py`. That is the only new harness. It:

1. Reads User-Story **phases** from `tasks.md` (one card per phase, not per
   task). `[P]` stays inside the card body as `phase_checklist`.
2. **Transcribes** parents from the `## Dependencies` section (native Spec Kit
   heading `## Dependencies & Execution Order` included). Per-story bullets
   (`**User Story 1 (Phase 3)**: Depends on Foundational`) are the contract;
   the old collective `**User Stories (Phase 3+)**` bullet still works.
   Polish accepts `all user stories` or `all desired user stories`.
3. Assigns file-granular ownership (A-5): each dest file has **exactly one
   owner**. `pom.xml` has a unique owner (earliest phase that named it).
   Native later-story **Extend** / **Add POST** lines do not re-claim those
   files. Any other overlap is a partition defect → refuse.
4. Checks HTTP endpoint coverage against M1 `evidence/entry-point-inventory.json`
   (Architect `E-20260816T193813Z` A-8). An inventory HTTP entry is covered
   when **any** of these hold: dest-file equality (same-stack shortcut);
   its `symbol` (`Class#method`) appears in the phase body; or its
   `http_path` is transcribed (`@Path("…")` or `GET /api/…`) and
   `http_method` is named (or the inventory method is empty). `{id}` and
   `{ownerId}` normalize to `{var}`; a transcribed prefix covers nested
   paths. Native Spec Kit writes JAX-RS `@Path("/owners")` plus `GET /`
   (no `GET /api/owners` token). The mint joins that class path to the
   inventory's shared servlet prefix (LCP of `http_path` values, e.g.
   `/api`) so `@Path("/owners")` covers `GET /api/owners`. **Do not**
   apply that prefix to `@Path("/")` (it would claim every `/api/…`
   route). Do **not** map `*RestController.java` → `*Resource.java` and
   do **not** infer `/api/owners` from a filename. Uncovered entries
   refuse (`endpoints_uncovered`). `endpoints_multi` is unreachable when
   write-sets are disjoint unless two phases transcribe the same route.
   Inventories without `http_method`/`http_path` stay uncovered unless
   symbol or dest-file match. Native US2 POST/PUT/DELETE lines that omit
   the class `@Path` stay uncovered unless they name a `symbol`.
5. Writes `evidence/briefs/partition.json` as a **receipt**
   (`source=handover-mint`, `stories[].story_id` unchanged for existing
   readers). Path-A authored partition as input is refused.
6. Assembles typed bodies (existing `assemble-m3-bodies-from-partition.py`)
   and mints with `--ensure-wave-holder` (creates a still-open blocked
   holder) or `--parent <wave_holder>`. **Do not `--parent` a done M2**
   (HKN-2 / `PARENT_DONE`).

The M2 worker does **not** `kanban_create` and does **not** author
`partition.json`.

## Worktrees

Sibling user-story cards (parent is Foundational only) are stamped
`workspace_kind=worktree`. Setup, Foundational, Polish, and stories that
depend on another user story stay `dir`. Assignment is recorded on the
receipt. Live parallel dispatch remains gated on a promotion-proof hold
status (0.4). Worktrees do **not** relax the unique `pom.xml` owner.

## Fail-closed

| Symptom | Refuse |
|---|---|
| No `## Dependencies` section | `DEPENDENCIES_MISSING` |
| File in two write-sets (not pom) | `FILE_OVERLAP` |
| HTTP entry point with no owner | `endpoints_uncovered` |
| User-story phase with no test-shaped AC | `PHASE_AC` (decomposition defect) |
| Path-A `partition.json` already on disk | `PATH_A_PARTITION` |
| FIS / dual-stack over cap | `BODY_SIZE` (R-V14.4 — split the phase, do not raise the wall) |
| `mint-m3-wave --parent` of a `done` card | `PARENT_DONE` (HKN-2) — use `--ensure-wave-holder` |

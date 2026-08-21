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
   heading `## Dependencies & Execution Order` included). Closed-vocabulary
   bullets (`**Setup**` / `**Foundational**` / `**User Story N**` /
   `**User Stories (Phase 3+)**`) still work. Native domain headings
   (`## Phase 1: Build Foundations`) mint as kind `phase` id `P1` — the
   heading **number**, not the title prose (Architect `E-20260817T013303Z`).
   `**Phase 7 (US1)**: Depends on Phases 2-6` transcribes onto `US1` as
   `[P2,…,P6]`. Do **not** require the word Foundational when native uses
   Phase-N lists (`192444Z` AMEND). Polish accepts `all user stories`,
   `all desired user stories`, or `all phases`.
3. Assigns file-granular write-sets and a unique `pom.xml` owner (the phase
   that **creates** it). Native later-story **Extend** / **Add POST, PUT,
   DELETE** / **Add … to pom.xml** lines stay on that later card. **S.10 /
   A-5 is one dest file, one in-flight card**, not one file per phase in
   `tasks.md`. Mint-time `FILE_OVERLAP` (global cross-phase disjointness)
   was the stricter invented check; it is dropped while serial (Architect
   `E-20260817T131858Z`). Restore a **runtime in-flight** overlap check
   when C-1(a) is claimed — not a mint-time scan of the whole artifact.
   Per-card `files_writable` still gates the fence.
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
   symbol or dest-file match. An `Add POST/PUT/DELETE` or `Extend` line that
   names a dest path already owned by an earlier phase **inherits that file's
   transcribed routes** (`@Path` / `GET /…` on the Create line) for A-8 only;
   methods come from the amend body (Architect `E-20260817T015216Z`). Write-set
   stays single-owner. This is **not** a RestController→Resource mapper and
   **not** inferring `/api/owners` from a filename with no `@Path` on the
   owner line.
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

## Oracle stamps

`stamp_oracles` uses one total `exit_for(operand_class, proves)` map
(V35-ORACLE-REST). Mixed `rest`+`test` **keep** `http_semantics`.
Test-only (no `rest` — polish) stamps `test_suite_runs` with
`cmd: mvn -q test`. Persistence-without-rest stamps `mapping_valid`
(`mvn -q test` when a proving test is in-set, else `mvn -q test-compile`
— compile is not a discriminating vehicle for that check).
`build_config` stamps `build_resolves`. Rest without a test path is
`ORACLE_UNMAPPED` / `PHASE_AC` — not a silent compile stamp. Unmapped
combinations refuse at assembly. Do **not** dest-rewrite a body to paper
over a missing ladder branch.

`stamp-body-dependencies.py` assigns inheritance-reachable unowned dest
twins onto the owning story's partition frame (Architect `E-20260819T165142Z`
/ V34-5), including simple names reached through `import pkg.*;`. Generated
types stamp `provider: generated` (dc66c244); they are not dest twins a
story Creates. M2 covers source type-inventory dest twins; generated
types require generator inputs owned (`GENERATOR_INPUTS`). V34-8 stamp +
assert-dependency-closure remains the backstop. Do **not**
grow this mint for that close. Do **not** dest-rewrite `tasks.md` to name
specimen types.

## Fail-closed

| Symptom | Refuse |
|---|---|
| No `## Dependencies` section | `DEPENDENCIES_MISSING` |
| Foundational whole-domain `*Service.java` | `T0_3_SERVICE` — split the facade per aggregate (not polish, not a user story, not foundational) |
| Cyclic import parent | `CYCLE_IMPORT` — parent the owning story, or split if whole-domain facade |
| File in two write-sets (not pom) | *not a mint refuse while serial* (`131858Z`); restore in-flight when C-1(a) is claimed |
| HTTP entry point with no owner | `endpoints_uncovered` |
| User-story phase with no Independent Test heading | `PHASE_AC` |
| User-story phase whose Independent Test is prose (no test path in write-set) | `ORACLE_UNMAPPED` / `PHASE_AC` when `rest` is in operand_class (V35-ORACLE-REST); do not stamp `build_resolves` |
| Path-A `partition.json` already on disk | `PATH_A_PARTITION` |
| FIS / dual-stack over cap | `BODY_SIZE` (R-V14.4 — split the phase, do not raise the wall) |
| `handover-mint.py --parent` of a `done` card | `PARENT_DONE` (HKN-2) — refused; holder session follows `mint-m3-hermes.md` |

The A-4/A-5 **PASS** contract is the captured attempt-2 `speckit.tasks` harvest
(`fixtures/handover/tasks.attempt-2-speckit.md`), not a hand-authored fixture.
`tasks.good.md` was deleted (Architect `E-20260817T082353Z` / Operator `E-20260817T120146Z`).
Named negatives remain `tasks.no-deps.md` (`DEPENDENCIES_MISSING`) and
`tasks.overlap.md` (must **not** `FILE_OVERLAP` while serial).

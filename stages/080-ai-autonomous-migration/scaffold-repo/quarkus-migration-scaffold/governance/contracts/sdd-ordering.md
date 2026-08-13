# SDD ordering contract (brief → spec → tasks → re-plan)

**Status:** binding for migration workspace · mirrors **AD-S §S.6**
**Basis:** plan / AD-S §S.6
**Placement:** this golden scaffold only (consumed in `/projects/modernized`).
Never `harness-refactoring/` authoring trees; never committed `.specify/`.

AD-S / Hermes / Kanban / `github/spec-kit` stand. Pattern-steals
(`pattern-steals.md`) cover readiness shapes; **this file** covers identity
carry-forward, implementation-graph layers, and re-plan authority.

## Brief identity → spec / stories / tasks

The **migration brief** is the M2 story packet (or typed equivalent) that feeds
`/speckit-specify` → plan → tasks → `kanban_create`.

### Carry unchanged (identity)

Copy or cite by stable ID — never paraphrase away:

| Field | Why |
|-------|-----|
| Story / unit IDs and in-scope / out-of-scope boundaries | SOUL scope discipline |
| `## Non-Goals` and forbid/preserve clauses | AD-S + no-invention |
| Acceptance criteria with stable IDs (`AC-*` / contract refs) and measurable outcomes | G-1/G-4 oracles |
| M1 finding / unit refs the brief claims (ids, rule labels) | Evidence chain |
| Anchored legacy excerpts / staging facts the brief asserts over | Facts travel |
| Open `Q-*` that remain unresolved | Block readiness until closed |
| Target-stack invariants in constitution / `AGENTS.md` | Project constants |

### May change downstream

HOW in `plan.md`, task split, `files_in_scope` **narrowing** within story scope,
parallel `[P]` markers, Kanban `body` packaging.

### Refuse

Expanding scope, dropping Non-Goals, rewriting AC meaning, inventing units not
in the brief/model.

## Implementation-graph ordering

Kanban `parents` / task `deps` encode edges. Build order (earlier before later):

1. **Build / module foundations** — POM/BOM, module layout, shared plugins
2. **Security foundations** — authn/authz, identity, TLS/secret wiring (before exposing APIs)
3. **Data / schema** — persistence, migrations, stored-shape config (before readers/writers)
4. **API / SPI contracts** — endpoints, CDI interfaces, events (before implementers and consumers)
5. **Test infrastructure** — characterization harness / fixtures for claimed ACs (before those IMPLEMENT tasks)
6. **Feature / port work** — HARVEST before REDESIGN; M1 conversion order (deps before dependents); no competing beans for one interface
7. **Surfaces last** — models → services → surfaces; deploy milestones only after contract + boot path exist

**Parallelism:** `[P]` / no-`parents` only when none of the above edges exist.
Story-level roadmap uses the same layering (`roadmap-lint` successor).

## Re-plan authority and retention

| Actor | May re-plan graph? | On missing dep / invalid assumption |
|-------|-------------------|-------------------------------------|
| IMPLEMENT worker | **No** | Stop; Kanban `blocked` with typed reason |
| M2 / PLAN owner | **Yes — task/plan graph only** | Re-emit plan/tasks → `kanban_create` under **same** brief identity |
| Spec / brief identity change | **Escalate** | Amend brief/spec (M2); then PLAN re-derives |

**Supersession (mandatory):** bump `plan_revision` (or dated
`migration/plans/` / git history); archive superseded Kanban tasks with
`superseded_by` / `supersedes`; never delete prior plan text from git;
`auto_decompose: false` stands.

## Enforcement

Cheap checks: skill `check-spec-readiness`
(`.hermes/skills/sdd/check-spec-readiness/scripts/check-ordering.py` via
`check-readiness.sh`) when task JSON / plan artifacts exist — identity refs,
refuse IMPLEMENT `replan`, require `plan_revision` on supersession. Full
roadmap/plan-lint successors ride M2/M3 schema work.

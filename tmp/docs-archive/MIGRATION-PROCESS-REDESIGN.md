# Migration process redesign: clear stages, auditable artifacts, incremental modernization

Status: DESIGN (2026-07-27) — for review before any harness refactor.
Decision driver: the process has accreted mechanism-by-mechanism across
five runs and is hard to track; and the current shape is effectively
big-bang (one plan for the whole app). This redesign restructures it
into sequential stages with explicit input/output artifacts, an
incremental no-big-bang roadmap, and a feedback loop at two levels —
orchestrated end-to-end by the Hermes agent once each stage is
individually validated.

Lineage: stage 070 concepts (AGENTS.md, skills, rules, spec-kit,
briefs) remain the foundation; stage 080 adds the supervisor, sensors,
MTA rule contracts, and the factory gate. Nothing here discards those —
it re-arranges them into a legible pipeline.

---

## 0. The process at a glance

```
        ┌────────────────────────────────────────────────────────────────┐
        │                        M1 ANALYZE                              │
        │  legacy code + rules → ground truth + architecture profile     │
        └────────────────────────────────────────────────────────────────┘
                                    │
        ┌────────────────────────────────────────────────────────────────┐
        │                        M2 SEQUENCE                             │
        │  ground truth → ordered modernization stories + briefs         │
        └────────────────────────────────────────────────────────────────┘
                                    │  (per story, in roadmap order)
              ┌─────────────────────┼───────────────────────┐
              ▼                     ▼                       ▼
        ┌───────────┐        ┌───────────┐          ┌────────────┐
        │ M3 SPECIFY│  ───►  │M4 IMPLEMENT│  ───►   │ M5 EVALUATE│
        │ spec-kit  │        │ guarded    │          │ gate+ship  │
        │ per story │        │ execution  │          │ +learn     │
        └───────────┘        └───────────┘          └─────┬──────┘
              ▲                                           │
              │            story-level learning loop      │
              └────────────── (retro → skills/briefs) ────┘
                                    │
                        next story from the roadmap
                        (roadmap itself revisable after each story)
```

Two feedback loops, explicitly:
- **Inner (within a story)**: sensors → fix sessions → gates. Exists
  today; unchanged.
- **Outer (across stories)**: M5's retro proposes changes to skills,
  rules, MAPPINGS, and the remaining briefs BEFORE the next story
  starts. Today's Phase F runs once at the end of a run; in this design
  it runs per story, so learning compounds inside a single migration.

---

## 1. M1 — ANALYZE (code & architecture analysis)

**Question answered**: *What is this application, what was it built to
do, and what must change?* Understanding first — the migration must
stay as close as possible to the original intent.

| | |
|---|---|
| **Inputs** | legacy repo (read-only); `migration.yaml` (analysis source/targets, preserve, forbidden, acceptance); platform rules `.hermes/rules/`; MAPPINGS rule-join table |
| **Outputs** (all committed, `M1 analyze:` prefix) | `migration/mta-findings.json` (raw, reproducible); `migration/findings-inventory.md` (per-rule: class, decided target, incident sites, preserve candidates); `migration/dependency-order.md` (import graph, fan-in/out, god nodes, conversion order, circular groups); `migration/architecture-profile.md` (**new**) |
| **Executed by** | supervisor scripts (deterministic parts) + ONE Hermes analyst session (architecture profile) |
| **Gate** | instrument tests for the scripts (exist); profile rubric-check: every claim cites file:line evidence; sections complete |

`architecture-profile.md` (the new artifact — the "original intent"
record) sections, each grounded in citations:
1. Purpose & domain — what the app does, for whom, core domain
   concepts.
2. Components & relationships — services/endpoints/models/config with
   the dependency graph (from dependency-order.md) interpreted:
   which classes form which component, what talks to what.
3. Integration surfaces — external services, env contracts, exposed
   APIs (the preserve-contract evidence).
4. Behavioral contract sources — legacy test inventory, assertion
   values that constitute the contract (the anti-fabrication anchor).
5. Modernization surface — findings summarized per component: what
   must change (mandatory), what should (optional), what to examine
   (potential).
6. Domain boundaries (monolith-class apps) — candidate seams for
   decomposition, from communities in the graph + domain reading.

Existing assets mapped: harness-owned kantra Phase A (done),
findings-inventory.py (done), dependency-order.py (done). New to
build: the analyst-session prompt + profile rubric.

## 2. M2 — SEQUENCE (modernization roadmap & stories)

**Question answered**: *In what order do we modernize, and what does
each increment contain?* Explicitly NOT big-bang: the roadmap breaks
the work into dependency-respecting increments — a service is
modernized model-first then service-then-endpoint; a monolith is
decomposed along domain boundaries (DDD), one bounded context at a
time.

| | |
|---|---|
| **Inputs** | all M1 outputs |
| **Outputs** (committed, `M2 sequence:` prefix) | `migration/roadmap.md` (ordered story list: scope, rationale, dependencies between stories, done-criteria per story); `migration/briefs/S01-<slug>.md` … (one brief per story) |
| **Executed by** | Hermes planner session(s) |
| **Gate** | **roadmap-lint** (new, deterministic): every mandatory finding owned by exactly ≥1 story; story order consistent with `dependency-order.md`; every `preserve:` item owned; every brief complete per template; no ceremonial stories (each story names code it changes) |

The **brief** is the stage 070 concept, upgraded: the self-contained
work order that starts a spec-kit cycle. `BRIEF-TEMPLATE.md` (new):
- Story goal + why now (position in the roadmap, dependency rationale)
- In scope: exact legacy classes/files (with key code excerpts inline)
- Out of scope: what later stories own
- Decided target shapes: the MAPPINGS rows that apply; recipe-executed
  rules already handled (recipe-log reference)
- Contracts: the preserve/forbidden/acceptance items THIS story owns;
  legacy assertion values to pin
- Done-criteria: buildable, sensors green, story-scoped acceptance

Sizing rule: a story is one spec-kit cycle a session can hold — for
the cart-class, 3–5 stories (models+characterization tests → services
→ REST surface+config → ship surface); for the monolith, one story
per bounded context plus a decomposition-seam story. The roadmap for a
simple app degenerates gracefully to few stories — same process, no
extra ceremony.

Honest note on "user stories": we rejected MigIQ/konveyor story layers
as ceremony (T-029 lesson: artifacts must change code or tests). These
stories are different in kind: they are the unit of iteration — they
scope, gate, and sequence real work, and each one runs its own
M3→M5 cycle. The T-029 rule still applies inside them.

Existing assets mapped: dependency-order feeds the sequencing;
PLANNING.md ordering rules move up a level (story order, then task
order within story). New to build: roadmap+brief authoring prompts,
BRIEF-TEMPLATE.md, roadmap-lint.py.

## 3. M3 — SPECIFY (spec-kit cycle per story)

**Question answered**: *Exactly what will this increment do, and how?*
Pure spec-kit, scoped to one story.

| | |
|---|---|
| **Inputs** | the story's brief; current state of the modernized repo (previous stories' output); MAPPINGS; skill PLANNING.md |
| **Outputs** (committed, `S<NN> spec:` prefix) | `specs/S<NN>-<slug>/spec.md` (behavioral contract for this increment, from brief + legacy tests), `plan.md` (target design), `tasks.md` (ordered tasks; rewrite before infer; characterization tests FIRST; recipe-executed rules excluded) |
| **Executed by** | Hermes planning session |
| **Gate** | plan-lint (exists) scoped per story: the story's assigned findings covered; dependency order within scope; design-in-packet; package identity; task hygiene rules |

Existing assets mapped: the whole current Phase B machinery + plan-lint
(needs a story-scope parameter: which findings this story owns comes
from the roadmap).

## 4. M4 — IMPLEMENT (guarded execution)

**Question answered**: *Build it, to corporate standard.* No wild-west:
every commit passes the sensors; judgment guided by skills/rules;
mechanical work done by recipes/scripts, not model sessions.

| | |
|---|---|
| **Inputs** | story `tasks.md`; skills (EXECUTION.md, MAPPINGS.md), AGENTS.md rules; sensors |
| **Outputs** | code + tests, one commit per task (`T-NNN:` prefix), run-log rows; sensor-green tree at every commit |
| **Executed by** | supervisor task loop → Hermes orchestrator sessions → OpenCode worker packets (R11 synchronous) |
| **Gates** | task sensor per commit; milestone sensor (verify + in-loop sonar) on config commits + every 3rd task; failure classification; mechanical commit closure; bounded fix sessions |

Existing assets mapped: unchanged — this is today's Phase C, scoped to
one story's tasks instead of the whole app's.

## 5. M5 — EVALUATE (verify, ship, learn)

**Question answered**: *Is this increment done, is it live, and what
did we learn before the next one?*

| | |
|---|---|
| **Inputs** | story done-criteria (brief); migration.yaml acceptance; sensors; factory |
| **Outputs** (committed) | preflight result; pipeline + quality-gate outcome; deployed increment; `migration/findings-delta.md` (re-analysis: findings shrinking story by story); `migration/run-log.md` story section; `migration/retro/S<NN>-proposals.md` (**per-story retro**) |
| **Executed by** | supervisor (preflight, ship loop, acceptance) + one Hermes retro session |
| **Gates** | pre-push preflight (full gate + boot); factory (build, sonar gate, deploy); story acceptance (done-criteria + app acceptance path for shipped surface); round budgets with continuation semantics |

The retro is the outer loop's engine: it reads the story's telemetry
and proposes concrete diffs to skills/rules/MAPPINGS **and to the
remaining briefs** (e.g. "story S03's brief should pin these assertion
values — S02 nearly fabricated them"). Proposals are propose-only;
operator merges; the next story starts with the lessons applied.
Roadmap revision is allowed here: re-order/split remaining stories
with a committed rationale.

Existing assets mapped: preflight/ship/acceptance/Phase F machinery —
re-scoped per story; findings-delta exists (Phase D) and becomes the
per-story progress metric.

---

## 6. Auditability model

- **Git is the audit trail**: every stage commits its artifacts with a
  stage prefix (`M1 analyze:`, `M2 sequence:`, `S03 spec:`, `T-014:`,
  `S03 ship:`, `S03 retro:`). `git log --oneline` reads as the process
  narrative.
- **Every model-made claim cites evidence** (file:line, finding id,
  test name) in its artifact; deterministic gates check structure so
  review effort goes to judgment, not format.
- **One contract file** (`migration.yaml`) carries the app-specific
  contracts; **one process doc** (`.hermes/skills/migration-harness/
  PROCESS.md`, new) states the stage I/O table above and is the single
  place a human starts reading.
- Supervisor phases map to stages: A→M1, B→M3 (per story), C→M4,
  D+E→M5(a-c), F→M5(e). The letters retire from docs once refactored.

## 7. What is genuinely new to build

| Piece | Stage | Size |
|---|---|---|
| Analyst session + `architecture-profile.md` rubric | M1 | prompt + rubric check |
| `BRIEF-TEMPLATE.md` + roadmap/brief authoring prompts | M2 | template + prompts |
| `roadmap-lint.py` | M2 | new instrument (+X1 tests) |
| plan-lint story-scoping (findings ownership parameter) | M3 | small change |
| Supervisor outer loop (stories from roadmap; per-story M3→M5; per-story retro) | all | the main refactor |
| PROCESS.md (the process contract) | — | doc |

Everything else already exists and slots in unchanged.

## 8. Validation plan — each stage proven alone before automation

Per the decision: no stage joins the autonomous loop until it has been
run standalone, its artifacts reviewed, and its gate tested.

| Step | What runs | Success looks like |
|---|---|---|
| **V1** | M1 standalone on cart legacy (analysis validation already in flight) + first analyst session | enriched findings verified (cloud-readiness/openjdk/demo rules); architecture-profile complete with citations; operator review |
| **V2** | M2 standalone on the cart (expect 3–5 stories) AND on the monolith legacy (expect domain-boundary stories) — the second is the real test of sequencing | roadmap-lint green; briefs judged self-sufficient (could a stage 070 human start from this brief alone?) |
| **V3** | One story (S01) through M3→M5 on round3, operator-monitored (deep-analysis protocol) | story ships; retro proposals sensible; findings-delta shows the story's slice resolved |
| **V4** | Supervisor outer loop automated; full autonomous round3 run (all stories) | end-to-end ship with per-story ledger; interventions ≤ run #2 |
| **V5** | The monolith, autonomous | the decomposition case works end-to-end |

Round3 is the V1–V4 vehicle — its fresh state is exactly what the
redesign needs.

## 9. Design decisions (user, 2026-07-27)

1. **Shipping: hybrid — deploy at milestones.** The roadmap marks which
   stories are deployable increments (`deploy: true` in the story
   entry); those run the full M5 ship (factory + deploy + acceptance);
   the rest stop at the factory quality gate. roadmap-lint requires at
   least one deployable story and that the LAST story deploys.
2. **Granularity: natural sizing, no floor.** The planner sizes
   stories purely from the dependency graph and session capacity;
   roadmap-lint enforces ordering, coverage, and brief completeness —
   never story count. A trivial app may legitimately be one story.
3. **Monolith: in-place now, extraction later.** Stage 080 demos
   in-place modularization along DDD seams (one repo, one deployment,
   stories per bounded context in dependency order). True service
   extraction of one exemplar context is a follow-up (BACKLOG).
4. **Graphify adopted for the M1 graph; NO human escalation**
   (2026-07-27, post-V3 evidence). Import-only analysis missed a
   same-package edge and caused S01's stub defect; V5's DDD
   story-cutting needs AST-grade edges and communities. Autonomy stays
   total: the fabrication-class response is autonomous
   revert-and-redispatch, never a human hold.

## 10. Graphify adoption plan (V5 pre-step)

1. **Source & license check**: locate the graphify CLI shipped with
   MigIQ (tree-sitter based, offline), vendor or install it into the
   workspace tooling (kantra-ensure pattern).
2. **Spike with a decisive test**: run it on BOTH legacy trees. Pass
   bar: (a) it captures the `ShoppingCart→ShoppingCartItem`
   same-package edge my import graph missed (the S01 regression case);
   (b) monolith communities align with the known domain boundaries.
   Fail either → extend `dependency-order.py` with same-package
   type-reference scanning instead and stop.
3. **Integration shape (downstream untouched)**: M1 runs graphify as a
   script step → `graph.json`; a converter emits
   `migration/dependency-order.md` in the EXISTING format (order, god
   nodes, circular groups — now edge-confidence-aware) plus
   `migration/communities.md` for M2's monolith story-cutting.
   `dependency-order.py` remains the zero-dependency fallback.
4. **Instrument tests**: fixture project with a same-package reference
   — the regression test S01 earned.
5. **Rollout**: V5 monolith mandatory; cart-class projects use
   whichever is present (auto-detect).

**Spike executed 2026-07-28 — PASS on both bars.** The public CLI
(`uv tool install graphifyy`, Graphify-Labs/graphify) ran fully
offline on the cart legacy (`graphify extract . --code-only`): 145
nodes, 319 edges, 9 communities from 16 files. (a) `graphify path
"ShoppingCart" "ShoppingCartItem"` → 1 hop, `references [EXTRACTED]` —
the exact same-package edge the import graph missed; (b) communities
align with the domain seams V3's roadmap chose manually (pricing core,
catalog client, REST surface, items, promo, tests, bootstrap).
Independently, `dependency-order.py` gained same-package simple-name
resolution (regression-tested), so the zero-dependency fallback no
longer has the S01 blind spot. Decision stands: graphify integration
lands with V5 (monolith communities are where it pays); V4 runs on
the fixed `dependency-order.py`.

## 11. Fabrication-class response — autonomous, no human gate

The story-scope sensor (V4 must-build) detects the proven signature
(e.g. a test-class task modifying `src/main`, or any commit touching
files outside the story's scope + tests). Response is deterministic
and autonomous: **revert the out-of-scope hunks, record the event
(KPI: scope_violation), and re-dispatch the session once with the
violated constraint stated verbatim in the packet.** Second violation
of the same task → task recorded as debt, loop continues. Broadened
`forbidden:` tripwires stay as the fast path; artifact-diff review
moves into the per-story retro prompt (the telemetry-only retro missed
all three fabrication arcs).

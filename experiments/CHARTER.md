# Harness Refactor — Experiment Charter

**Branch:** `harness-refactor` (worktree `/Users/adrina/Sandbox/rhoai3-harness-refactor`, base `0d53a27`)
**Operator directive (2026-08-07):** clean-slate rethink of the stage 080 approach end-to-end — harness, agents, skills, and the MTA / kantra / spec-kit / OpenRewrite configuration and integration. Test the spec-kit configuration as described in the reference blog to see what difference it makes, empirically rather than by argument.
**Reference guide:** https://loiane.com/2026/05/specs-driven-development-end-to-end-with-spring-boot-angular/
**Prior analysis:** `tmp/sdd-setup/analysis/SDD-E2E-ANALYSIS.md` (main tree) — findings F1–F5, reconfiguration package R1–R6. This branch is where its claims get *tested*, including the ones the operator wants to challenge.

## Ground rules

1. **Main is untouched.** Wave 5 (`petclinic-rest-v5`), Grok's in-flight landing, and the Track B driver tooling stay on `main`. Nothing on this branch syncs to a pod or workspace unless the operator explicitly says so.
2. **Experiments are comparative.** Every experiment runs against the same specimen and reports the same measures, so "what difference does it make" is a number, not an impression.
3. **Findings are banked as evidence, not as harness patches.** No fix lands on main from here; results feed a redesign decision first (this is the opposite of Track B's fix-and-rerun mandate, deliberately — this branch answers *design* questions, not *run* questions).
4. **Specimen-agnostic conclusions.** Petclinic values may appear in evidence; never in a design statement (standing rule).

## Baseline to beat (from the 2026-08-07 analysis)

| Measure | Current value |
|---|---|
| Fix-cycles per shipped story (wave trend) | 25 → 286 → 1277 → 739 |
| Wave-2 six-tuple (last graded E2E) | 51 sessions / 15 esc / 49 corrections / 9 wedges / 6 dead / 60.7% |
| Worker write rate (W4R7) | 26% |
| Harness size | 47,196 LOC, 664 O-* guards, 832 instruments |
| Open bank | ~125 ⬜, flat five days |

## Experiment matrix (proposed — operator prunes/reorders)

### E1 — Blog-faithful SDD on a migration story
Configure the workflow exactly as the guide prescribes (phases 1–10: onboard → wire-harness → spec → spec-review → design → plan → build per task → validate → review → close), with a `.specs/{DATE}-{FEATURE}/01…08` dossier and its TDD state file, on **one bounded migration story** (e.g. the vet REST surface). The spec is *authored* and holds authority — i.e., the exact model the analysis argued against. Honest test, run honestly.
- **Question:** on migration work, does authored-spec authority hold, or does it drift from legacy behavior — and at what cost in seats/wall-clock/defects vs the harness baseline?
- **Open config decision:** runtime for the command set — the guide assumes Claude Code (`.claude/` commands/agents/skills); our stack is OpenCode/Qwen + Hermes. Options: (a) Claude Code as in the guide (faithful replication, different model class), (b) port the command set to OpenCode (same seats as production, less faithful), (c) both, small scale.

### E2 — Upstream spec-kit, configured properly
The 080 scaffold's vendored spec-kit was never wired in. Before deleting it (analysis R1), give it a fair trial: initialize a real spec-kit flow (`/speckit.constitution` → `specify` → `plan` → `tasks` → `implement`) with a constitution written for migration work, on the same story as E1.
- **Question:** does a *configured* spec-kit (constitution + clarify/analyze gates) behave differently from the inert copy that seeded W4-576? Where does its greenfield assumption bind?

### E3 — MTA / kantra integration review
Current contract: one-shot kantra at M1 (targets `[quarkus, jakarta-ee9, cloud-readiness, openjdk17]`, no `--source`, profile-driven rules), re-run at M5 for the findings delta.
- Review: analysis profiles and custom rulesets; source-only vs binary coverage; **incremental analysis** during M4 (KAI's analyzer-RPC pattern — per-file incident cache, `included_paths` re-analysis) vs our milestone-only re-runs; whether findings→task ownership (K1) survives a redesign.
- **Question:** should analysis be a *continuous sensor* in the inner loop rather than a bookend?

### E4 — OpenRewrite as mechanical prepass
Upstream has ~62 Spring→Quarkus recipes (G3/G4 finding, never landed). Configure a prepass: MAPPINGS → `rewrite.yml`, run before any LLM seat, measure the % of kantra incidents resolved purely mechanically.
- **Question:** how much of the migration is computation wearing an inference costume? Every mechanically-resolved incident is a seat never spent and a guard never needed.

### E5 — Minimal harness rebuild (model-driven core, typed end-to-end)
Green-field the harness keeping only the proven core patterns (typed model + task_contract vocabulary, task_lifecycle state machine, completion_authority verdicts, write-inversion seats) with the analysis's R2/R3 applied from day one: M4 reads the model, one completion writer, typed run journal instead of `/tmp`. Hard budget: target < 5,000 LOC; a new guard lands only with its instrument and a named subsumption target.
- **Question:** with the dual-store disease designed out from the start, what does the guard count converge to — and does the six-tuple beat the baseline?

## Sequencing note

E3 + E4 are input reviews (what does the machine know before any agent runs); E1 + E2 are authority-model tests; E5 is the synthesis. A sensible order is E4 → E3 → E1/E2 (parallel, same story) → E5, because the prepass and analysis results change how big the story even is by the time an agent sees it. Operator decides.

## Decisions (operator, 2026-08-07)

| # | Decision | Resolution |
|---|---|---|
| D1 | E1 runtime | **Port the blog workflow to our stack** (OpenCode/Qwen seats; command set as OpenCode commands) |
| D2 | Specimen + story for E1/E2 | **petclinic vet REST surface** (frozen fork `adnan-drina/spring-petclinic-rest-legacy` @ `517a399` = v2.6.2) |
| D3 | Experiment order | Proposed sequence stands: **E4 → E3 → E1/E2 (parallel, same story) → E5** |
| D4 | Review flow on this branch | **Operator + Claude only until results are in** — no Wave-5 doc filings, no Grok/Opus loop |

— Claude Fable 5, 2026-08-07

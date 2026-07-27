# MigIQ analysis — what it does, what we adopt, what we reject

> **Verdict update (2026-07-27, post-V3):** the "graphify CLI rejected"
> call below is REVERSED — V3 proved import-only analysis misses
> same-package edges, and V5's DDD story-cutting needs AST edges and
> communities. Adoption plan: MIGRATION-PROCESS-REDESIGN.md §10. The
> parallel-subagent and checkbox-state rejections were instead
> vindicated by V3's two-writer incidents.

Analyzed 2026-07-27 from the clone in `tmp/migIQ` (v0.2.2, sshaaf/migIQ).
Read in full: README, AGENT.md, all 8 SKILL.md files (~5,800 lines), the
evals framework, test-validator.sh.

## What MigIQ is

An npm-installable set of Claude Code skills plus an agent definition
that orchestrates migrations in 5 phases:

1. **mig-graphify** — builds a tree-sitter knowledge graph of the
   codebase (nodes/edges/communities; edges tagged
   EXTRACTED/INFERRED/AMBIGUOUS); analysis reasons over fan-in/fan-out,
   god nodes, circular dependencies, and community structure to derive
   migration order and risk.
2. **mig-prompt-builder** — interactive requirements gathering into one
   standardized `migration-prompt.md` (spec + design + constraints).
3. **mig-plan** — checkbox `tasks.md` (task groups with mandatory
   test/containerize/deploy/doc subtasks) + `UserStory.md` (stories
   with acceptance criteria, priority, dependencies).
4. **mig-execute** — parses stories/tasks, builds a dependency graph,
   spawns parallel subagents (≤10) for independent subtasks, tracks
   progress by rewriting checkboxes, and **pauses on any failure to
   present the user 2–4 remedy options with risk/time estimates**.
5. **migiq** — the orchestrator skill; final stakeholder
   MIGRATION_REPORT.md with executive summary.

Per-skill `evals/` directories define prompt + assertions
(`evals.json`), a grading script, and benchmark aggregation with token
counts. `test-validator.sh` checks per-phase artifact presence.

## Honest comparison with our stage 080 harness

Fundamentally different postures. MigIQ is **interactive-first**: even
its "autonomous" agent presents plans for approval and stops on every
failure to ask the user ("wait for user decision — don't guess").
Progress state is markdown checkboxes; there is no git-commit ledger,
no CI/factory integration, no quality gate, no deterministic lint, no
failure classification, no anti-fabrication contract, and no
enforcement behind its example claims ("87% coverage" appears in a
sample transcript with no machinery producing it). Our harness is the
inverse: autonomous convergence against deterministic gates
(plan-lint, task/milestone/preflight sensors, the factory), a
git-commit ledger for resume, process-failure classification, and
tested instruments.

What MigIQ has that we genuinely lack:

| MigIQ idea | Assessment |
|---|---|
| **Dependency-graph analysis driving task order** (fan-in/fan-out, god nodes, leaf-first sequencing) | **ADOPT.** Our Phase A is MTA findings only — rule violations, no structure. Cart run #2's worst plan defect was exactly a sequencing flaw (files harvested before their dependencies, 3 red commits). A deterministic dependency analysis in Phase A gives the planner the order instead of hoping it infers one. |
| **Characterization tests FIRST, prioritized by graph centrality** (mig-test-gen Pattern 1: pin god-node behavior before touching it) | **ADOPT.** We derived this lesson the hard way twice (legacy assertions are the contract; the coverage gap existed because tests came last). Codifying tests-early with fan-in priority kills two failure classes at planning time. |
| **Stakeholder-grade final report** (executive summary, journey, deliverables) | **ADOPT (light).** Our run-report is telemetry. One executive-summary block makes it demo- and stakeholder-readable. |
| Per-skill evals with graded assertions + token benchmarks | Partial — our X1 suite covers deterministic instruments; model-facing skill evals are what our monitored runs already do with richer evidence. Revisit if we ever ship the harness as a product. |
| Standardized migration-prompt.md | Covered — `migration.yaml` (preserve/forbidden/acceptance) + AGENTS.md are our machine-checked equivalent, which is stronger than prose. |

What we reject, with reasons:

- **Parallel subagent execution.** Our worker forensics showed the
  OpenCode `task` subagent kills its parent session deterministically;
  and MigIQ's parallel writers share one tree with no two-writer
  protection — a race our commit-per-task ledger exists to prevent.
- **Pause-and-ask failure handling.** Opposite of the stage 080 goal;
  our classified fix loops + bounded budgets replace the human in that
  loop, and run #2 shipped on that design.
- **The graphify CLI itself.** The *idea* is adopted; the npm/tree-sitter
  tool is not — for Java a deterministic import-graph script gives us
  fan-in/fan-out and ordering with zero new runtime dependencies.
- **The UserStory layer.** For an autonomous run it is ceremony between
  the plan and the code — the same class as run #2's "final commit"
  task (a lesson we already codified: every task changes code or tests).

## One nuance on ordering direction

MigIQ (strangler/incremental context) migrates **leaf nodes first**
(nothing depends on them, safe to move). Our context is a single-shot
rewrite where the tree must COMPILE at every commit — so the correct
order is **dependencies before dependents** (utilities and models
first, endpoints last). Same graph, opposite traversal; our
`dependency-order.py` emits the compile-safe order and flags god nodes
for characterization-test priority rather than for deferral.

## Adopted implementation (this commit)

1. `.hermes/harness/dependency-order.py` — deterministic Java
   import-graph analysis of the legacy tree: per-class fan-in/fan-out,
   god nodes, and a dependencies-first conversion order. Runs in
   Phase A (supervisor script step); output committed as
   `migration/dependency-order.md`.
2. PLANNING.md — conversion tasks must follow the dependency order;
   god nodes get characterization tests pinning legacy behavior BEFORE
   their conversion task; test tasks land early, not as a tail.
3. `write_run_report` — executive-summary block (source → target,
   findings delta, gate numbers, route) ahead of the telemetry.

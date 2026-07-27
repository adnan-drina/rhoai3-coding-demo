# M2 SEQUENCE — the modernization roadmap and its briefs

You are turning the M1 outputs into an ordered, incremental
modernization plan: `migration/roadmap.md` plus one brief per story
under `migration/briefs/`. NO BIG BANG: each story is an increment that
leaves the repository buildable, sensor-green, and closer to done.

## Inputs (read all four before writing anything)

- `migration/architecture-profile.md` — what the app is; domain
  boundaries; contract sources
- `migration/dependency-order.md` — the conversion order the stories
  must respect (dependencies before dependents; circular groups stay
  together)
- `migration/findings-inventory.md` — every mandatory finding with its
  class; recipe-executed rules are ALREADY DONE (`migration/
  recipe-log.md`) — no story owns them
- `migration.yaml` — preserve/forbidden/acceptance contracts

## How to cut stories

1. **Follow the graph, not the file tree.** Story order = dependency
   order: models/utilities before services before surfaces. A story
   never modernizes a class whose project-internal dependencies are
   owned by a LATER story. Circular groups belong to one story.
2. **Contracts and characterization tests come first.** The first
   story that touches a component with a behavioral contract
   (architecture-profile §4) pins that contract — port the legacy
   tests / add characterization tests for the flagged gaps — before or
   within the story that changes the code.
3. **Domain seams for monolith-class apps** (profile §6): one story
   per bounded context, contexts ordered by their coupling direction;
   in-place modularization (no service extraction — that is a
   follow-up outside this migration).
4. **Natural sizing, no floor or ceiling by count**: a story is one
   spec-kit cycle a session can hold (≈ the packet-size spirit: a
   story's in-scope class list should fit ~10 files). A trivial app
   may be one story; do not pad.
5. **Deploy milestones**: mark `deploy: true` on stories whose end
   state is worth proving live (at minimum the LAST story; typically
   also the first story that leaves the app serving its API). Others
   stop at the factory quality gate.
6. **Every story changes code or tests.** No ceremonial stories
   (validation-only, commit-only, report-only) — the harness gates do
   the validating.

## Production-grade bar

Deploy stories ship production-grade, not merely migrated: the briefs for
stories that convert stateful services or REST surfaces name the
applicable "Production-grade defaults" shapes from MAPPINGS.md
(thread-safe singleton state, cache refresh-guard, read-only GET,
validation + error mapping, normalize-before-derive) as part of the
story's decided design. A post-ship semantic review should find nothing
structural. Hardening stories remain available for defects DISCOVERED
post-ship, but known defect classes are never deferred to one.

## Story classes

Most stories are **migration stories** (findings-driven, fidelity
first). The roadmap may also carry **hardening stories**: post-ship
quality work fed by the semantic code review of a deployed story —
concurrency correctness, validation and error mapping, cache/resource
policy, API idempotency — things the fidelity contract deliberately
preserved from the legacy and the rule-based gate cannot see. A
hardening story owns no MTA findings (`findings: -`); its brief cites
the review findings instead, and behavioral contracts still bind: the
pinned tests must stay green while the defect classes close.

## roadmap.md format (machine-parsed — roadmap-lint enforces this)

```markdown
# Modernization roadmap

## S01: <short title>
- scope: <comma-separated class/file list (project-relative)>
- findings: <comma-separated mandatory rule ids this story resolves>
- depends: - | S<NN>[, S<NN>...]
- deploy: true|false
- done: <one-sentence checkable done-criterion>
- rationale: <why this story, why now — cite dependency-order/profile>

## S02: ...
```

Every mandatory finding id from the inventory (except recipe-executed
ones) appears in exactly one story's `findings:`. Every `preserve:`
item is owned by the story whose scope carries its surface (name it in
that brief).

## Briefs (`migration/briefs/S<NN>-<slug>.md`)

One per story, following `BRIEF-TEMPLATE.md` in this directory. The
bar: **a competent developer (or a fresh session) could start the
story from the brief alone** — without re-reading the whole profile.
That means: real code excerpts from the legacy source (the actual
lines being modernized, quoted), the decided MAPPINGS shapes named,
the contract values spelled out (assertion numbers, env var names),
and the done-criteria concrete.

## Output contract

Verify yourself before committing:
`python3 .hermes/harness/roadmap-lint.py migration/roadmap.md migration/findings-inventory.md`
must exit 0. Commit everything in ONE commit, prefix `M2 sequence:`.

# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Standard | Agent Skills open standard (agentskills.io) |
| Version | no version marker on page |
| Chapter or page title | Optimizing skill descriptions |
| Source URL | https://agentskills.io/skill-creation/optimizing-descriptions |
| Source URL | https://agentskills.io/specification#description-field (1024-char limit) |
| Documentation category | Skill creation |
| Capture date | 2026-08-13 |
| Capture method | Reviewer-direct capture (maintainer-requested): page fetched in full; principles, query-design rules, thresholds, split ratios, loop steps, and the before/after example extracted verbatim |

## Captured Content

- Triggering mechanics: startup loads name + description only; body loads
  on match; the "agents only consult skills for tasks beyond what they
  handle alone" nuance.
- Writing principles: imperative, user-intent, pushy/explicit contexts,
  concise, 1024-char hard limit.
- Eval query design: ~20 queries (8-10 positive / 8-10 negative);
  variation axes (phrasing, explicitness, detail, complexity); near-miss
  negatives with worked weak-vs-strong examples; realism ingredients.
- Measurement: 3 runs per query, trigger rate, 0.5 threshold, scripted
  harness (bash + jq over the client's tool-call log), early-stop tip.
- Anti-overfitting: 60/40 train/validation, proportional mix, fixed
  split; train-only failure analysis.
- Optimization loop: five steps, ~5 iterations, generalize-don't-keyword,
  structural rewrite when stuck, select by validation pass rate, verify
  on 5-10 fresh queries.
- Before/after description example (CSV analyzer).

## Source Boundaries

Description authoring and trigger evals live here. Body content and
format → `agentskills-authoring`; output-quality evals →
`agentskills-evaluation`.

## Known Open Items

- The referenced `skill-creator` skill (github.com/anthropics/skills)
  automates this loop end-to-end — not evaluated here; a candidate tool
  if this project ever runs trigger evals at scale.
- The harness example is Claude Code-specific in its detection logic;
  adapting it to Cursor or other clients is undocumented.

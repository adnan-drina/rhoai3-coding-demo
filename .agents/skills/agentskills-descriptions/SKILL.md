---
name: agentskills-descriptions
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "agentskills"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Agent Skills Standard"
description: >
  Use when writing or revising the description field of any SKILL.md, or
  when a skill fires on the wrong prompts or fails to fire on the right
  ones. Covers the official agentskills.io guidance: imperative pushy
  phrasing, the 1024-character limit, trigger eval query sets, trigger
  rates, train/validation splits, and the optimization loop. Do NOT use
  for skill body content (use agentskills-authoring) or output quality
  (use agentskills-evaluation).
---

# Optimizing Skill Descriptions (official standard)

The description is the entire triggering mechanism. "A skill only helps
if it gets activated."

## Source Grounding

Official page (captured 2026-08-13, see `references/source-capture.md`):
https://agentskills.io/skill-creation/optimizing-descriptions

## Why it carries the whole burden

At startup agents load only each skill's `name` and `description` — "just
enough to decide when a skill might be relevant". The full body loads
only after a match. "If the description doesn't convey when the skill is
useful, the agent won't know to reach for it."

One documented nuance: "agents typically only consult skills for tasks
that require knowledge or capabilities beyond what they can handle
alone." A one-step request may not trigger even a perfectly matching
description — specialized knowledge, unfamiliar APIs, and
domain-specific workflows are where wording pays off.

## Writing principles

- **Imperative phrasing** — "Use this skill when…", not "This skill
  does…". The agent is deciding whether to act.
- **User intent, not implementation** — describe what the user is trying
  to achieve; the agent matches against the request, not your internals.
- **Err on the side of being pushy** — enumerate applicable contexts
  explicitly, including ones where the user doesn't name the domain
  ("even if they don't explicitly mention 'CSV' or 'analysis'").
- **Concise** — a few sentences to a short paragraph; hard limit **1024
  characters** (descriptions "tend to grow during optimization" — check
  after every revision).
- **State the boundary** — what the skill does *not* do, to keep
  near-miss prompts from false-triggering.

Documented before/after:

```yaml
# Before
description: Process CSV files.

# After
description: >
  Analyze CSV and tabular data files — compute summary statistics,
  add derived columns, generate charts, and clean messy data. Use this
  skill when the user has a CSV, TSV, or Excel file and wants to
  explore, transform, or visualize the data, even if they don't
  explicitly mention "CSV" or "analysis."
```

## Building a trigger eval set

Target **~20 realistic queries: 8-10 should-trigger, 8-10 should-not**,
stored with labels (`{"query": …, "should_trigger": true}`).

**Should-trigger** queries vary along four axes: phrasing (formal, casual,
typos), explicitness (names the domain vs. describes the need), detail
(terse vs. context-heavy), and complexity (single-step vs. multi-step
where the relevant task is buried). "The most useful should-trigger
queries are ones where the skill would help but the connection isn't
obvious from the query alone."

**Should-not-trigger** queries must be **near-misses** — sharing keywords
or concepts but needing something different. "Write a fibonacci
function" tests nothing; "I need to update the formulas in my Excel
budget spreadsheet" (shares 'spreadsheet', needs Excel editing) is a real
test.

**Realism**: include file paths, personal context ("my manager asked me
to…"), specific column/company names, casual language and typos.

## Measuring trigger rate

Model behavior is nondeterministic — run each query **3 times** and
compute a trigger rate (fraction of runs where the skill was invoked).
A should-trigger query passes above a **0.5** threshold; a
should-not-trigger query passes below it. 20 queries × 3 runs = 60
invocations, so script it (the source page ships a bash+jq harness using
the agent client's own tool-call log; adapt `check_triggered` to the
client). Stopping a run early once the outcome is clear cuts cost.

## Avoiding overfitting

Split the query set **~60% train / ~40% validation**, proportionally
mixed, shuffled once and kept **fixed across iterations**. Only train-set
failures may guide revisions; validation exists to prove generalization.

## The optimization loop

1. Evaluate on both sets.
2. Identify **train-set** failures only.
3. Revise: too narrow → broaden scope/context; too broad → add
   specificity and boundaries. "Avoid adding specific keywords from
   failed queries — that's overfitting. Instead, find the general
   category… and address that." If stuck after several passes, try a
   structurally different description rather than incremental tweaks.
   Re-check the 1024-char limit.
4. Repeat until train passes or gains stall — **five iterations is
   usually enough**.
5. **Select by validation pass rate** — "the best description may not be
   the last one you produced."

Then verify with 5-10 fresh, never-optimized queries as an honest check.

## Workflow

1. Draft the description with the five writing principles.
2. Build ~20 labeled queries with near-miss negatives; split 60/40.
3. Measure trigger rates (3 runs, 0.5 threshold).
4. Run the loop on train-set failures only; pick the best validation
   score; confirm on fresh queries.
5. If results won't improve after ~5 iterations, suspect the query set
   (too easy, too hard, mislabeled) before blaming the description.

## Validation

```shell
awk '/^description:/,/^[a-z-]+:/' .agents/skills/<name>/SKILL.md | wc -c   # ≤1024
skills-ref validate .agents/skills/<name>                                  # spec check
```

## Pitfalls

- Optimizing against all queries — guarantees overfitting; hold out a
  validation set.
- Keyword-stuffing failed queries instead of generalizing the concept.
- Weak negatives (obviously unrelated prompts) that prove nothing.
- Single-run judgments on nondeterministic behavior.
- Silently blowing past 1024 characters during iteration.
- Describing mechanics ("uses pdfplumber") instead of user intent.

## Related Skills

- `agentskills-authoring` — the body the description gates access to.
- `agentskills-evaluation` — once it triggers, prove it helps.

## References

- `references/source-capture.md`

---
name: agentskills-evaluation
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "agentskills"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Agent Skills Standard"
description: >
  Use when proving a skill actually improves agent output — before
  landing a substantial new skill, when iterating on one that
  underperforms, or when deciding whether a skill earns its context cost.
  Covers the official agentskills.io eval loop: test cases, with-skill vs
  without-skill baselines, assertions, evidence-based grading, benchmark
  deltas, and pattern analysis. Do NOT use for triggering accuracy (use
  agentskills-descriptions).
---

# Evaluating Skill Output Quality (official standard)

"You wrote a skill, tried it on a prompt, and it seemed to work. But does
it work reliably — across varied prompts, in edge cases, better than no
skill at all?"

## Source Grounding

Official page (captured 2026-08-13, see `references/source-capture.md`):
https://agentskills.io/skill-creation/evaluating-skills

## Test cases

Three parts: a **prompt** ("the kind of thing someone would actually
type"), an **expected output** (human-readable success description), and
optional **input files**. Stored in `evals/evals.json` inside the skill
directory.

Rules: **start with 2-3 cases** ("don't over-invest before you've seen
your first round of results"); vary phrasing, detail, and formality;
cover at least one edge case (malformed input, ambiguous instruction);
use realistic context — "prompts like 'process this data' are too vague
to test anything useful". Don't write pass/fail checks yet.

## Run against a baseline — always

"The core pattern is to run each test case twice: once **with the skill**
and once **without it** (or with a previous version)." Without a
baseline you cannot tell skill value from model capability. When
improving an existing skill, snapshot the old version and use it as the
baseline (`old_skill/` instead of `without_skill/`).

Each run starts with **clean context** — subagents give this naturally;
otherwise use a separate session per run. Record `timing.json`
(`total_tokens`, `duration_ms`) per run: "a skill that dramatically
improves output quality but triples token usage is a different trade-off
than one that's both better and cheaper."

Workspace layout (one directory per iteration):

```
<skill>-workspace/iteration-1/
├── eval-<case>/
│   ├── with_skill/{outputs,timing.json,grading.json}
│   └── without_skill/{outputs,timing.json,grading.json}
└── benchmark.json
```

## Assertions

Write them **after** the first run — "you often don't know what 'good'
looks like until the skill has run."

| Good | Weak |
|---|---|
| "The output file is valid JSON" (programmatically verifiable) | "The output is good" (too vague to grade) |
| "The bar chart has labeled axes" (specific, observable) | "Uses exactly the phrase 'Total Revenue: $X'" (too brittle) |
| "The report includes at least 3 recommendations" (countable) | — |

"Not everything needs an assertion" — style, visual design, and
whether output "feels right" belong to human review.

## Grading

Record PASS/FAIL **with evidence that quotes or references the output**,
not an opinion. Use scripts for mechanical checks (valid JSON, row
counts, file dimensions) — "more reliable than LLM judgment… and
reusable across iterations"; use an LLM for the rest.

Two principles: **require concrete evidence for a PASS** ("if an
assertion says 'includes a summary' and the output has a section titled
'Summary' with one vague sentence, that's a FAIL"), and **review the
assertions themselves** — flag ones that always pass, always fail, or
can't be checked.

For version comparisons, try **blind comparison**: an LLM judge scores
both outputs without knowing which version produced which.

## Benchmarks and pattern analysis

Aggregate per configuration into `benchmark.json` — pass rate, time, and
tokens with mean/stddev — plus a **delta**. "A skill that adds 13 seconds
but improves pass rate by 50 percentage points is probably worth it. A
skill that doubles token usage for a 2-point improvement might not be."

Then read past the averages:

- **Always passes in both configs** → remove/replace; it inflates the
  with-skill rate without showing value.
- **Always fails in both** → broken assertion, too-hard case, or wrong
  thing being checked.
- **Passes with skill, fails without** → where the skill earns its keep;
  understand *why*.
- **Inconsistent across runs (high stddev)** → flaky eval or ambiguous
  instructions; add examples/specificity.
- **Time/token outliers** → read the execution transcript for the
  bottleneck.

## Human review and iteration

A human reviewer "catch[es] issues you didn't anticipate… or spotting
problems that are hard to express as pass/fail checks". Record specific,
actionable feedback per case (`feedback.json`); empty means it looked
fine.

Improve using all three signals — failed assertions (specific gaps),
human feedback (broader quality), and execution transcripts (*why* it
went wrong) — handed to an LLM with the current `SKILL.md`, instructed
to: **generalize** beyond the test cases, **keep the skill lean**
("if pass rates plateau despite adding more rules, the skill may be
over-constrained — try removing instructions"), **explain the why**
rather than issuing rigid directives, and **bundle repeated work** into
`scripts/`.

Loop: propose → apply → rerun in `iteration-<N+1>/` → grade → aggregate →
human review → repeat. Stop when satisfied, when feedback is
consistently empty, or when improvements stall.

## Workflow

1. Write 2-3 realistic test cases in `evals/evals.json` (no assertions
   yet).
2. Run each with and without the skill, clean context, capturing timing.
3. Write assertions from what the first outputs revealed.
4. Grade with evidence; aggregate to `benchmark.json`; compute the delta.
5. Analyze patterns; fix broken assertions before the next iteration.
6. Human-review outputs; feed all three signals into a revision.
7. Repeat until gains stall — then decide honestly whether the skill
   earns its context cost.

## Pitfalls

- No baseline run — the most common way to "prove" a skill that adds
  nothing.
- Writing assertions before seeing outputs (guesses at what good means).
- Passing an assertion on a label rather than substance.
- Reusing dirty context between runs — leaks the development
  conversation into the result.
- Reading only aggregates and missing always-pass / always-fail
  assertions.
- Answering a plateau by adding more rules; over-constrained skills get
  worse, not better.
- Ignoring the token/time delta — a skill can be better and still not
  worth it.

## Related Skills

- `agentskills-authoring` — what to change when evals point at a gap.
- `agentskills-descriptions` — triggering accuracy (a different eval).

## References

- `references/source-capture.md`

# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Standard | Agent Skills open standard (agentskills.io) |
| Version | no version marker on page |
| Chapter or page title | Evaluating skill output quality |
| Source URL | https://agentskills.io/skill-creation/evaluating-skills |
| Documentation category | Skill creation |
| Capture date | 2026-08-13 |
| Capture method | Reviewer-direct capture (maintainer-requested): page fetched in full; test-case rules, workspace layout, assertion quality bar, grading principles, benchmark shape, pattern-analysis list, and the iteration loop extracted verbatim |

## Captured Content

- Test cases: prompt / expected output / optional files in
  `evals/evals.json`; start with 2-3; vary phrasing and detail; cover an
  edge case; realistic context; assertions deferred until after run 1.
- Baseline discipline: with_skill vs without_skill (or old_skill
  snapshot); clean context per run (subagents or separate sessions);
  `timing.json` with total_tokens + duration_ms.
- Workspace: `iteration-N/eval-<case>/{with_skill,without_skill}/…` plus
  `benchmark.json`.
- Assertions: good (verifiable, specific, countable) vs weak (vague,
  brittle); not everything needs one.
- Grading: PASS/FAIL with quoted evidence; scripts for mechanical checks;
  require concrete evidence; review the assertions themselves; blind
  comparison for version-vs-version.
- Benchmarks: per-config mean/stddev for pass rate, time, tokens, plus
  delta cost/benefit reasoning.
- Pattern analysis: always-pass, always-fail, passes-only-with-skill,
  high-stddev flakiness, time/token outliers.
- Human review (`feedback.json`, actionable not "looks bad") and the
  three-signal LLM-assisted revision (generalize, keep lean, explain the
  why, bundle repeated work).

## Source Boundaries

Output-quality evaluation lives here. Trigger-accuracy evaluation →
`agentskills-descriptions`; skill content and format →
`agentskills-authoring`.

## Known Open Items

- The `skill-creator` skill (github.com/anthropics/skills) automates much
  of this loop — not evaluated here.
- Guidance assumes a subagent-capable client for clean-context runs; the
  separate-session fallback is stated but not detailed.
- No stated minimum sample size for statistically meaningful stddev
  beyond "multiple runs per eval".

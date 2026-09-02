# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | no version marker on doc pages (family anchor: v0.20.0, 2026-08-03) |
| Chapter or page title | Persistent Goals (`/goal`) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/goals |
| Documentation category | Features (Automation) |
| Capture date | 2026-08-12 |
| Capture method | Reviewer-direct capture (maintainer-requested gap-fill): full-section verbatim extraction; cross-checked against the hermes-about capture's Goals-vs-Kanban comparison (verified verbatim earlier the same day) and the hermes-kanban capture's goal-mode-card facts — consistent |

## Captured Content

- Loop mechanics: post-turn judge (goal text + ~4 KB response → strict
  JSON `done|continue|wait`), deliberately conservative, fail-open on
  judge errors ("a broken judge never wedges progress"), user messages
  preempt.
- Command set: /goal set/status/pause/resume/clear; /subgoal
  add/list/remove; /goal draft; /goal gate add/list/remove/clear;
  /goal wait <pid> / unwait.
- Completion contracts: outcome, verification, constraints, boundaries,
  stop_when; draft-by-goal_judge (recommended) or inline field prefixes.
- Quality gates: deterministic shell command, exit 0 required, "run
  before the judge", git-fingerprint skip on unchanged workspace, 3
  retries / 5-min timeout default, auto-pause on exhaustion (inspired by
  Prime-Agent's bounded autonomous mode).
- Parking: judge `wait` verdict skips turns without consuming budget;
  wait_on_session / wait_on_pid / wait_for_seconds.
- Budget: goals.max_turns default 20; auto-pause message; resume resets
  the counter. Judge routing: auxiliary.goal_judge (~200 output
  tokens/turn).
- Judge-wrong handling: false negatives caught by budget; false
  positives rarer by design.
- Attribution: Ralph-loop pattern; user-facing design credited to Codex
  CLI 0.128.0 (Eric Traut, OpenAI); Hermes implementation independent.

## Source Boundaries

/goal loop mechanics live here. Board orchestration and `--goal` cards →
`hermes-kanban`; `goals.*`/`auxiliary.goal_judge` schema wiring →
`hermes-configuration`.

## Known Open Items

- Gate retry/timeout defaults (3 / 5 min) documented in prose only — no
  config-key names shown for overriding them.
- Whether `/goal` state survives session resume (`-c`) is not stated on
  the page — verify on a live seat before relying on it.

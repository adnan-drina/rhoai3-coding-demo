# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) — official optional skill documentation |
| Skill documented | one-three-one-rule v1.0.0, author Willard Moore, MIT, category communication, platforms linux/macos/windows, tags: communication, decision-making, proposals, trade-offs |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/skills/optional/communication/communication-one-three-one-rule |
| Documentation category | Optional Skills / Communication |
| Capture date | 2026-08-12 |
| Capture method | Reviewer-direct capture (single-page skill doc): structure, when-to-use/not, worked-example shape (retry-logic decision: three retry strategies, Option A recommended), and install command quoted from the live page |

## Captured Content

- The five-part structure: Problem (one sentence) → three Options with
  pros/cons → one Recommendation with reasoning → Definition of Done
  (verifiable) → Implementation Plan.
- Applicability rules (use for decisions with real trade-offs; not for
  obvious answers, debugging, or already-decided approaches).
- Install path: `hermes skills install
  official/communication/one-three-one-rule` (official trust tier — "no
  third-party warning panel", per the hermes-skills capture).

## Cross-references

- The stage 080 scaffold's skill-authoring law
  (`.hermes/skills/harness/skill-authoring/references/worked-example.md`)
  mirrors this same published skill as its authoring exemplar — this
  repo-level skill and the scaffold reference now share one official
  source.

## Known Open Items

- None — single self-contained page; recheck on recapture for version
  bumps beyond v1.0.0.

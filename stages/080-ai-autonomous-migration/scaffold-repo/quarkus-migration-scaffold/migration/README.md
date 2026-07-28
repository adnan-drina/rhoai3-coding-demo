# Migration artifacts (harness contract)

This directory is the harness's evidence trail. The Hermes orchestrator
(see `.hermes/skills/migration-harness/`) owns every file here; OpenCode
and humans read them.

| File | Written | Purpose |
|---|---|---|
| `mta-findings.json` | M1 ANALYZE | Ground truth: the MTA/kantra analysis of `/projects/legacy` (konveyor analyzer format). "Done" is defined against this baseline. |
| `mta-findings-after.json` | M5 EVALUATE | Re-analysis of the MIGRATED code. The before → after delta is the completion evidence. |
| `architecture-profile.md` | M1 ANALYZE | Components, integrations, behavioral contracts, seams — input to M2. |
| `roadmap.md`, `briefs/` | M2 SEQUENCE | Ordered stories and self-contained briefs. |
| `story-state.csv` | Outer loop | Per-story complete/failed ledger for resume after stop-on-failure. |
| `run-log.md` | M4 IMPLEMENT | One line per task: id, class, attempts, result, files touched. Retry clusters here are harness-improvement signals. |
| `debt.md` | On budget exhaustion | Tasks the loop could not complete within budget, with failure evidence. Empty is the goal, honest is the rule. |
| `retro-proposals.md` | Retro | Brief updates (outer loop may apply) + skill/harness proposals (human-only). |

The findings files are gitignored-in-legacy but committed HERE: they are
the migration's contract and audit trail, versioned with the code they
justify. `/tmp/rewrite-staging` (OpenRewrite scratch) is never committed.

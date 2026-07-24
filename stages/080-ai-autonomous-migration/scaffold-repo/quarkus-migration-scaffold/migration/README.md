# Migration artifacts (harness contract)

This directory is the harness's evidence trail. The Hermes orchestrator
(see `.hermes/skills/migration-harness/`) owns every file here; OpenCode
and humans read them.

| File | Written | Purpose |
|---|---|---|
| `mta-findings.json` | Phase A (normalize) | Ground truth: the MTA/kantra analysis of `/projects/legacy` (konveyor analyzer format). "Done" is defined against this baseline. |
| `mta-findings-after.json` | Phase D (final sensor) | Re-analysis of the MIGRATED code. The before → after delta is the completion evidence. |
| `run-log.md` | Phase C (after every task) | One line per task: id, class, attempts, result, files touched. Retry clusters here are harness-improvement signals. |
| `debt.md` | On budget exhaustion | Tasks the loop could not complete within budget, with failure evidence. Empty is the goal, honest is the rule. |

The findings files are gitignored-in-legacy but committed HERE: they are
the migration's contract and audit trail, versioned with the code they
justify. `/tmp/rewrite-staging` (OpenRewrite scratch) is never committed.

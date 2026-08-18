# Phase 5 run audit (observer)

Fail-open. **Never a gate.** Intervention count is a measurement.

## When

At card boundaries (create · claim · block · reclaim · complete) and at
end of run. Seat clock only — do not mix laptop timestamps.

## Snapshot

```bash
python3 .hermes/skills/harness/record-run-evidence/scripts/snapshot-run-audit.py \
  /projects/modernized --db "${HERMES_HOME}/kanban.db"
```

Writes `evidence/run-audit/<ts>.json`: dest-tree path → mtime + sha256
(skip `target/`, `.git/`), `git rev-parse HEAD` + last 5 commits, claim
windows from sqlite `task_runs` when `--db` is present. Session
`--windows-json` is retired (`075357Z`); live snapshots use `--db` only.
Published write-set **cache** under
`evidence/runtime/write-sets/<task_id>.json` is joined onto those windows
when present (forensics / attribution). The EX-3 fence does not read
that file for allow/deny.

## Analyze

```bash
python3 .hermes/skills/harness/record-run-evidence/scripts/analyze-run-audit.py \
  evidence/run-audit/<ts>.json --out evidence/run-audit/<ts>.findings.json
```

Checks:

1. Dest path mtime inside **no** claim window → `INTERVENTION`.
   Include-gate: `pom.xml`, `src/**`, plus dest files this seat has before
   those exist (`migration.yaml`, `AGENTS.md`, `devfile.yaml`, `k8s/`,
   `Containerfile`, `catalog-info.yaml`). Pass `--baseline <t0.json>` so
   provision-time files are not scored; t0-vs-self must be 0.
2. In-window dest write:
   - write-set **omit** (unpublished) → `UNATTRIBUTED`
   - write-set **`[]`** → `OOS_WRITE` (no worker dest writes)
   - write-set **populated** → `OOS_WRITE` if the path is not listed
3. `done` with no worker `kanban_complete` → `FORCED_TRANSITION`
4. `task_comments` whose author is not the card worker → `FOREIGN_COMMENT`

**Caller:** `snapshot-card-boundary.sh` from the M3 mint Procedure (`mint-m3-hermes.md`)
(create — Hermes has no create hook) and plugin
`.hermes/home/plugins/run-audit-boundary/` (`kanban_task_claimed` /
`completed` / `blocked`). Fail-open. Never a gate.

SR-8 `evidence/**` (and `.hermes/`) are harness-written and not dest
interventions. Same-window edits on a worker's own path are not
distinguishable — v19 repairs were out-of-window.

## Done-test

Touch a dest file with **no** claim windows. Analyzer reports one
`INTERVENTION` naming that path. `validate-contracts` runs this on a
temp tree.

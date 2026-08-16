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
windows from sqlite `task_runs` when the DB is present.

## Analyze

```bash
python3 .hermes/skills/harness/record-run-evidence/scripts/analyze-run-audit.py \
  evidence/run-audit/<ts>.json --out evidence/run-audit/<ts>.findings.json
```

Checks:

1. Dest `src/**` or `pom.xml` mtime inside **no** claim window → `INTERVENTION`
2. In-window but not in that card's `files_writable` → `OOS_WRITE`
3. `done` with no worker `kanban_complete` → `FORCED_TRANSITION`
4. `task_comments` whose author is not the card worker → `FOREIGN_COMMENT`

SR-8 `evidence/**` (and `.hermes/`) are harness-written and not dest
interventions. Same-window edits on a worker's own path are not
distinguishable — v19 repairs were out-of-window.

## Done-test

Touch a dest file with **no** claim windows. Analyzer reports one
`INTERVENTION` naming that path. `validate-contracts` runs this on a
temp tree.

# Phases A and B — ground truth and plan

## Contents
- Phase A — normalize ground truth
- Working with the findings file
- Phase B — plan (spec handoff)

## Phase A — normalize ground truth

The contract input is `migration/mta-findings.json` (konveyor analyzer
format: list of rulesets → `violations` keyed by rule id → `incidents`
with `uri`/`lineNumber`/`message`).

```bash
latest=$(ls -t /projects/legacy/.vscode/mta-core/analysis_*.json 2>/dev/null | head -1)
if [ -n "$latest" ]; then
  cp "$latest" /projects/modernized/migration/mta-findings.json
else
  # No IDE analysis available — produce ground truth with the kantra sensor
  kantra-ensure
  /tmp/kantra/kantra analyze -i /projects/legacy -o /tmp/kantra-baseline \
    --target quarkus --json-output --overwrite || true
  # kantra has a known bug marshaling the dependencies file: the command may
  # exit 1 even though the violations output.json is complete. Trust the file.
  cp /tmp/kantra-baseline/output.json /projects/modernized/migration/mta-findings.json
fi
```

### Working with the findings file — never read it whole

`mta-findings.json` is large (hundreds of KB). Reading it into context
wastes the budget and stalls the run. Always extract what you need with a
script, e.g.:

```bash
python3 - <<'PYEOF'
import json
d = json.load(open("/projects/modernized/migration/mta-findings.json"))
rows = []
for rs in d:
    for rid, v in (rs.get("violations") or {}).items():
        rows.append((rid, v.get("description", ""), len(v.get("incidents") or [])))
rows.sort(key=lambda r: -r[2])
print(f"{sum(1 for _ in rows)} violations, {sum(r[2] for r in rows)} incidents")
for rid, desc, n in rows:
    print(f"{n:4d}  {rid}  {desc[:70]}")
PYEOF
```

Read individual incidents (file/line/message) the same way — filtered by
rule id, never the full file.

## Phase B — plan (spec handoff)

Read the legacy code and `migration/mta-findings.json`, then write the
contract into the same layout stage 070 uses:

- `specs/<NNN-migration-slug>/spec.md` — observed legacy behavior + API
  contract (endpoints, data shapes, side effects), with legacy file paths
  as evidence.
- `specs/<NNN-migration-slug>/plan.md` — Quarkus mapping. Tag every item
  `rewrite` (mechanical: annotation/import/dependency swaps covered by
  OpenRewrite recipes) or `infer` (judgment: design, API shape, tests).
- `specs/<NNN-migration-slug>/tasks.md` — ordered checklist. Rewrite tasks
  before infer tasks. Every mandatory finding maps to at least one task;
  every task cites its finding rule ids.


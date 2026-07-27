# Phases A and B — ground truth and plan

Plans map findings to the DECIDED targets in [MAPPINGS.md](MAPPINGS.md) —
cite the catalog, do not re-derive architecture per run. `tasks.md` MUST
follow [TASKS-TEMPLATE.md](TASKS-TEMPLATE.md) — the supervisor's plan
lint bounces non-conforming plans.

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

The plan lint (`.hermes/harness/plan-lint.py`) enforces, deterministically:
task headings `#### T-NNN: title` (any heading depth 2–6; zero-padded
numeric ids, each used once); a `Class: rewrite|infer` marker per task;
all rewrite tasks before the first infer task; decided design content in
every infer body (file mappings/signatures/annotations); the legacy
user-facing surface (web UI / index page) covered by a task or
explicitly waived with a reason; every mandatory finding, every
migration.yaml `preserve:` item, and the migration.yaml
`acceptance.path` mapped to a task; and no `com.redhat.coolstore`
package targets (project root is `com.demo`).

**Phase A hands you a spec input bundle — consume it, do not re-derive
it** (docs/MTA-TO-SPEC-MAPPING.md):

- `migration/findings-inventory.md` — every mandatory finding already
  classified via the MAPPINGS rule-join: `recipe` rules are ALREADY
  EXECUTED (listed in `migration/recipe-log.md` — create NO tasks for
  them); `rewrite`/`infer` rules carry their decided target; OPEN
  DESIGN rows are where your judgment goes. Confirm the listed
  preserve-candidates against migration.yaml.
- `migration/staging/src` — legacy sources already recipe-transformed
  (e.g. jakarta imports). Harvest tasks pull from the staging tree,
  NOT from /projects/legacy.
- `migration/dependency-order.md` — the conversion order (below).

Your Phase B judgment budget belongs to: the behavioral contract (from
legacy tests + code reading — findings only say where to look) and the
OPEN DESIGN / infer shapes.

Ordering and test placement (MigIQ-derived, validated against cart
run #2's failures):

- **Conversion tasks follow `migration/dependency-order.md`** (Phase A
  emits it): dependencies before dependents — models and utilities
  first, endpoints last — so the tree compiles at every commit. Cart
  run #2's three red commits all came from harvesting dependents before
  their dependencies. Classes in a listed circular group convert in ONE
  task.
- **Characterization tests come EARLY, not as a tail.** Immediately
  after the mechanical rewrite tasks, one task ports the legacy test
  suite / pins legacy behavior (assertion values are the contract), and
  every god node flagged in dependency-order.md gets its
  characterization tests BEFORE its conversion task. This both feeds
  the 80% gate all run long and makes fabricated integrations fail
  tests at the introducing commit.

Two task-authoring constraints (from cart run #2):

- **Every task changes code or tests.** No ceremonial tasks ("final
  commit", "run validation", "prepare for gate") — commits happen per
  task and the gate runs in the factory; a task whose only product is a
  commit message or a report executes as an empty commit and wastes a
  session.
- **The plan's test tasks must be sized to the quality gate.** The
  factory fails new-code coverage < 80%; a tail that validates but never
  expands tests plans its own gate failure. Include explicit test tasks
  covering every migrated class (models and services included, not just
  endpoints).


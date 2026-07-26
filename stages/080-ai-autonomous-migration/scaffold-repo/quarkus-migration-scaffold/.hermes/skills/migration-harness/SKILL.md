---
name: migration-harness
description: Orchestrate the autonomous legacy-to-Quarkus migration loop — plan from MTA findings, dispatch rewrite tasks to OpenRewrite and infer tasks to OpenCode, run sensors after every task, respect the iteration budget; the factory pipeline is the merge authority.
---

# Migration harness runbook (Hermes orchestrator)

You are the harness orchestrator for this migration workspace. You own the
plan, the task queue, the sensor schedule, correction packets, and the
iteration budget. You do NOT write application code.

## Division of labor — hard rules

- **You (Hermes)** may write only under `specs/`, `migration/`, and the
  ephemeral scratch dir `/tmp/rewrite-staging`. Never edit files under
  `/projects/modernized/src` or `/projects/modernized/pom.xml` — code
  changes, including harvesting transformed files from the scratch dir,
  are delegated to OpenCode as tasks.
- **OpenCode** implements one bounded task at a time via `opencode run`.
  It never decides that the migration is complete — sensors and the
  findings baseline decide.
- **OpenRewrite** handles `Class: rewrite` tasks (deterministic
  transforms). You shell the Maven plugin on the scratch copy; OpenCode is
  not involved in rewrite execution.
- **The factory pipeline** (push → Maven build → SonarQube quality gate →
  image) is the ONLY merge authority. Never claim merge or deploy
  success — your final report ends at "pushed <sha>; the factory pipeline
  decides."

## Workspace layout

| Path | Rule |
|---|---|
| `/projects/legacy` | READ-ONLY migration input. Never modify. |
| `/projects/modernized` | Destination repo (this repo). Code changes only via OpenCode. |
| `/tmp/rewrite-staging` | Ephemeral scratch copy of legacy for OpenRewrite. Never committed anywhere. |

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

### Autonomous sessions never ask for consent

Harness runs are headless oneshots: nobody can answer a question you ask.
The operator's packet IS your standing authorization for everything inside
its scope — file edits, worker dispatches, builds, commits. If an action
is outside the packet's scope, do not ask — record it in
`migration/debt.md` and continue. Pausing to request confirmation ends
the session with the work undone.

### Scripting rule — terminal only, never execute_code

For ALL scripting (parsing findings, summarizing worker output, checking
reports) use the **terminal** tool with `python3 - <<'PYEOF' ... PYEOF`
heredocs, exactly as the examples in this skill do. Do NOT use the
execute_code tool: on this platform's models it is frequently emitted
with empty arguments, fails instantly, and burns the iteration budget.

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

## Task packet schema (Hermes → OpenCode)

```text
Task ID:        T-014
Class:          infer
Goal:           <one sentence>
Findings:       <rule ids this task resolves>
Constraints:    follow AGENTS.md and the repo skills; no scope creep
Inputs:         attached via -f (spec.md, tasks.md, touched files)
Acceptance:     <files expected to change>; mvn -q clean test passes
Out of scope:   <explicitly excluded work>
```

## Phase C — execution loop

For each task in `tasks.md`, in order:

**Class: rewrite** — scratch-transform procedure:

```bash
if [ ! -d /tmp/rewrite-staging ]; then
  mkdir -p /tmp/rewrite-staging
  tar -C /projects/legacy --exclude=.git --exclude=.vscode -cf - . \
    | tar -C /tmp/rewrite-staging -xf -
fi
cd /tmp/rewrite-staging
mvn -q -B org.openrewrite.maven:rewrite-maven-plugin:6.12.0:run \
  -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:3.12.0 \
  -Drewrite.activeRecipes=<recipe for this task>
```

The default mechanical set for this Java EE input is
`org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta`; the plan
may add further `rewrite-migrate-java` / Quarkus recipes per task. After
the recipes run, create a follow-up **infer** task for OpenCode to harvest:
"copy/adapt the transformed classes listed below from /tmp/rewrite-staging
into the scaffold structure" with explicit source and destination paths.

**Class: infer** — bounded worker run. The worker's JSON event stream is
huge (often hundreds of KB) — NEVER let it print to your terminal; it
would flood your context and wedge the run. Redirect to a file and read
only a scripted summary:

```bash
cd /projects/modernized
opencode run "<task packet>" \
  -m qwen27b/qwen3-6-27b --auto --format json \
  -f specs/<id>/spec.md -f specs/<id>/tasks.md -f AGENTS.md \
  > /tmp/oc-task.json 2>/tmp/oc-task.err; echo "worker exit: $?"
python3 - <<'PYEOF'
import json
texts, tools = [], []
for line in open("/tmp/oc-task.json"):
    line = line.strip()
    if not line: continue
    try: ev = json.loads(line)
    except ValueError: continue
    t = ev.get("type")
    if t == "text": texts.append(ev.get("text") or ev.get("part", {}).get("text", ""))
    elif t in ("tool", "tool_use"):
        info = ev.get("part", ev)
        tools.append(str(info.get("tool") or info.get("name") or "?"))
print("tool calls:", len(tools))
print("final text:", " ".join(texts)[-600:])
PYEOF
```

### Worker dispatch is synchronous — never background it

Run the `opencode run` command with a terminal timeout of at least 1800
seconds and WAIT for it to exit. NEVER launch it in the background, and
never end your turn while a worker is running: a headless session ends
the moment you stop calling tools — "I will wait for it to complete"
without a blocking tool call abandons the worker mid-task. If the
terminal returns while the worker is still running, poll in a loop
(`sleep 60` then check for the `opencode` process) until it exits before
doing anything else. Before dispatching, verify no worker is already
running.

### Packet size — one concern, bounded scope

A worker packet covers ONE concern and at most ~10 files or violation
sites. Split anything larger into sequential packets. Large single
packets push the worker (and you) into planning generations that outlast
client timeouts; small packets complete in minutes and retry cheaply.

### Packet content — the design is decided before dispatch

An infer packet carries the DECIDED target design: exact file mappings,
class and method signatures, annotations, and the architectural choices
already made in `plan.md` (e.g. "replace the JNDI lookup with `@Inject
ShippingService`", "REST resource at `/api/products` returning the DTO
shape below"). The worker implements decisions; it never makes them.
A packet that says "modernize X" without the target shape is a defective
packet — both worker budget exhaustions in the run-3 A/B were packets
that delegated the design along with the labor.

Then verify independently — check `git status --porcelain` for the
acceptance files. Never trust the worker's summary alone.

**Sensors after EVERY task (cheap → expensive):**

```bash
cd /projects/modernized
export JAVA_HOME="${JAVA_HOME_21:-$JAVA_HOME}" PATH="${JAVA_HOME}/bin:${PATH}"
# clean is non-negotiable: an incremental build can pass on stale
# target/ classes and hide missing dependencies the factory WILL catch
mvn -q clean test
```

If the task touched `pom.xml`, `application.properties`, or any other
build/runtime configuration, escalate the sensor to `mvn -q clean verify`:
the factory runs the full Quarkus package build, whose extension
processors enforce prod-mode requirements (e.g. Hibernate ORM demands a
configured default datasource) that `clean test` never exercises —
test-scoped fixes can still fail prod packaging.

**The factory quality gate is part of every task's acceptance.** SonarQube
fails the exit on: new-code coverage < 80%, any new violation, or > 3%
duplicated new lines. Consequences for task packets:

- Code-producing tasks (harvest included) must ship **unit tests with the
  code** — coverage debt is a gate failure, not a follow-up.
- Harvested legacy duplication (e.g. near-identical entity/DTO pairs) must
  be consolidated as part of the migration design, not copied through.
- Check locally before commit: `mvn -q clean verify` +
  the JaCoCo report (`target/jacoco-report/`) for new-class coverage.

On milestone boundaries (every 3–4 tasks), run a short inferential
self-eval: does the diff so far satisfy the spec sections it claims to?

**On sensor failure:** write a correction packet — the original packet
plus the exact failure output and the instruction "fix only this failure;
change nothing else" — and re-delegate. **Iteration budget: 2 attempts per
task** (original + one correction).

**Escalation valve (budget exhausted):** before recording debt, you MAY
implement the task directly with your own file tools — division of labor
is the default, not an invariant. If you escalate: keep the change
bounded to the task's findings, run the sensors yourself, start the
run-log row with `ESCALATED` (the supervisor counts escalations as a
packet-quality KPI), and note in the row why the packet failed the
worker. If you neither escalate nor finish, record the task in
`migration/debt.md` with the failure evidence and move on.

**After every task:** append one line to `migration/run-log.md`
(task id, class, attempts, result, files touched).

**NEVER commit with failing sensors.** A commit is the claim "this work
passed its sensors" — committing red is a runbook violation, worse than
reporting honest failure. If sensors are red and the budget is exhausted,
leave the tree uncommitted, record the failure evidence in
`migration/debt.md`, and report it. Coverage claims must be REAL numbers
read from the JaCoCo report, never inferences like "compilation success
indicates coverage".

## Phase D — final sensors + ship

1. Re-analysis of the MIGRATED code:

```bash
kantra-ensure
/tmp/kantra/kantra analyze -i /projects/modernized -o /tmp/kantra-after \
  --target quarkus --json-output --overwrite || true
cp /tmp/kantra-after/output.json /projects/modernized/migration/mta-findings-after.json
```

Done means the baseline findings are resolved (or waived in the spec) —
not "the agent says done."

2. `mvn -q clean verify` green.
3. Commit with a conventional message referencing the spec id. Under the
   supervisor, DO NOT push — the supervisor ships and drives Phase E.
4. Final report: tasks completed/deferred, debt entries, findings delta
   (before → after).

## Phase E — the factory gate loop (supervised)

The supervisor (`.hermes/harness/supervisor.sh`) owns shipping: it pushes,
watches the project PipelineRun (read-only RBAC is provisioned into every
project namespace), and on a SonarQube gate rejection exports the complete
new-code violation list to `/tmp/gate-violations.txt` (SonarQube allows
anonymous reads inside the cluster) and starts a **gate-correction
session** with you. In that session:

1. Read `/tmp/gate-violations.txt` with your file tools — rule, count,
   `file:line` sites, plus `DUPLICATION` lines per file.
2. Dispatch fixes to the worker in SMALL packets per the packet-size rule
   (group by rule, ≤ ~10 sites per packet, sequential). Duplication means
   consolidation — records, static factories — never suppression.
3. Semantics are inviolable: converting checks to `isEmpty()` and
   injection styles must preserve behavior exactly.
4. `mvn -q clean verify` green, JaCoCo coverage ≥ 80%, then ONE commit
   starting `Gate fix:` — the supervisor re-pushes and re-observes.

Budget: two gate rounds. A second rejection halts the run with the
violation list preserved for the retro — never bypass or water down the
gate.

## Stop conditions

| Condition | Action |
|---|---|
| All tasks done, sensors green, re-analysis clean | Phase D ship |
| Budget exhausted on a task | `migration/debt.md`, continue |
| Two consecutive full-suite failures after corrections | HALT: write run-log + debt, report, do not push, never bypass sensors |

## Model routing

Seats are split by evaluated strength: the **orchestrator** runs MiniMax
M2 (`custom:maas-m2`, 196K window) — selected in a full-migration A/B for
lean sessions, packet-size tolerance, and long-horizon loop reliability —
and the **worker** runs the governed local Qwen3.6 27B
(`qwen27b/qwen3-6-27b`), the strongest evaluated coding seat:

```bash
hermes chat --provider custom:maas-m2 --model minimax-m2 -q "..."
```

Trade-off (temporary): `maas-m2` is a direct external endpoint, so its
tokens do not appear on the platform's MaaS dashboard and are not
governed by cluster quotas — the RHOAI 3.4 gateway cannot stream external
models (fixed in 3.5, after which this routes through the gateway too).
The worker stays on the governed local model either way. All-local runs
(27B in both seats) work behind the supervisor's failure classification;
portal models with only 32K context (e.g. gpt-oss-120b) are not
orchestrator candidates: harness sessions routinely exceed 65K input
tokens.

## Cost discipline

Both you and OpenCode run on metered MaaS developer keys. Prefer `rewrite`
(deterministic, no inference cost) wherever the change is mechanical.
Keep worker prompts bounded — one task, explicit acceptance — so retries
stay cheap.

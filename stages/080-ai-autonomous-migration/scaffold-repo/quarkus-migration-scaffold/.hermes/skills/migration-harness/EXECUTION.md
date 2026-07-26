# Phase C — the execution loop

## Contents
- Task packet schema
- Phase C procedure (rewrite and infer tasks)
- Dispatch rules (synchronous, packet size, packet content)
- Sensors and quality-gate bars
- Budget, escalation valve, and debt policy

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


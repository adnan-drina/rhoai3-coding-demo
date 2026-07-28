# M4 — the execution loop

## Contents
- Task packet schema
- M4 procedure (rewrite and infer tasks)
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

## M4 — execution loop

### Batched rewrite sessions

The supervisor may dispatch several consecutive rewrite-class tasks in
ONE session. The contract does not relax: execute them in the listed
order, and finish each task with its own commit (its exact `T-0XX:`
prefix) before starting the next — never one combined commit. Every
per-task rule below applies to each task in the batch.

### Redesign classes are built to their target, not to legacy

For a REDESIGN class (service, endpoint, REST client, config — see
architecture-profile §7 and the brief), implement the §7 TARGET contract
from the first commit — not the legacy behavior. This is not "harden
later"; it IS the conversion.

The target contract is what §7 DECIDED for THIS app, gated by
`migration.yaml` `targetContract:` — apply only the shapes whose flags are
true. MAPPINGS "Production-grade defaults" is the CATALOG of options
(`ConcurrentHashMap`/`compute()`, cache refresh-guard, GET→404, →400
validation, →503 mapping, normalize-before-derive), not an unconditional
law: a read-only service, a batch job, or an API that must keep create-on-
GET will have some of those flags FALSE, and the class is built to match §7,
not to a checklist. Behavior-preserving shapes that §7 adopts (thread-
safety, cache policy) don't change observable behavior; behavior-changing
ones (GET→404, invalid→400) are the deliberate departures §7 recorded, and
the tests pin those §7 targets. HARVEST classes (models, DTOs, utilities)
stay faithful — fidelity applies, tests pin legacy values.

### Story scope is a hard boundary

When the run is story-scoped, modify only the existing `src/main` files
the story owns (the plan/brief lists them); creating new files the plan
designs and editing tests is always allowed. The supervisor's scope
sensor autonomously REVERTS out-of-scope `src/main` edits after the
commit. If a task genuinely cannot complete without touching another
story's file, record that in `migration/debt.md` instead of editing it.

### Never fabricate platform stubs

NEVER create stub classes for platform, framework, or vendor packages
(`javax.*`, `jakarta.*`, `com.enterprise.*`, `weblogic.*`, ...) to make
imports compile. A missing package is a DECISION — add the extension the
task's findings call for, or remove the premature import — never a file
you write yourself. Fabricated stubs poison the tree: they compile
locally and detonate in the factory.

### Harvest is per-file and follows transformation

Never harvest a file that still contains legacy-framework imports the
recipes did not transform (Spring annotations survive the jakarta
recipe) — the post-commit sensor will reject the tree, and a "harvest
everything, convert later" plan creates an inherent red window between
tasks. Plans order per-file conversion BEFORE (or WITH) that file's
harvest; a harvest packet lists only files whose transformations are
complete, and the harvesting session compiles before committing.

### Task completion is evidence in the destination

A task is complete when its FINDINGS are resolved IN
`/projects/modernized`. If a finding is inherently resolved by the
scaffold already (e.g. the pom is jakarta-native), verify that with
concrete evidence and record it as `resolved-by-scaffold` in the run-log
row — do not invent work. A worker run that changed no files is a FAILED
attempt — re-dispatch once with a sharper packet before burning the
budget.

For each task in `tasks.md`, in order:

**Class: rewrite** — HARVEST the already-transformed file (do NOT re-run
OpenRewrite):

M1 ALREADY applied the OpenRewrite recipes into `migration/staging` (via
`recipe-transform.sh`; `migration/recipe-log.md` lists which recipes ran on
which files). A rewrite task HARVESTS the pre-transformed file into the
scaffold, applying the package rename. Do NOT `mkdir /tmp/rewrite-staging`,
do NOT `tar` the legacy tree, do NOT re-run `rewrite-maven-plugin` — that
work is done, the scratch commands are redundant AND are denied by the
headless command policy (they will hang ~5 min each, then fail).

Use the bundled harvest script — do **NOT** hand-build the destination
path. It reads `legacyPackage`/`targetPackage` from `migration.yaml`, joins
the package into a real directory path (`com/demo`, never `com.demo`), and
applies the rename:

```bash
# harvest one class; arg is the path RELATIVE TO THE PACKAGE ROOT.
.hermes/skills/migration-harness/scripts/harvest-from-staging.sh model/Product.java
```

Pass only the package-relative path (`model/Product.java`,
`service/CatalogService.java`) — never the package directories, never an
absolute or dotted path. Hand-building `src/main/java/$TGT/...` is how a
session once wrote the target package as a dotted directory `com.demo/`
(compiles, ships silently, and the command policy denies the `rm` to undo
it — a long stall). The script makes that impossible; the `package` sensor
also fails any dotted package directory under `src/main`.

Harvest ONLY files whose transformation is complete (no surviving
legacy-framework imports — Spring annotations survive the jakarta recipe;
those files convert in an infer task first). The plan names the source
(`migration/staging/...`) and destination (`src/main/java/$TGTP/...`) per
task. Never write under the legacy package path in `src/main` — the target
is `targetPackage`. If `migration/staging` is absent, record debt — do NOT
stand up a scratch OpenRewrite run.

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
# summarize with the BUNDLED script — NOT an inline `python3 - <<EOF`
# heredoc (the headless command policy denies those: ~5 min hang, then
# block):
python3 .hermes/skills/migration-harness/scripts/summarize_worker.py /tmp/oc-task.json
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

A worker packet covers ONE concern and at most ~8 files or violation
sites. Split anything larger into sequential packets. Large single
packets push the worker (and you) into planning generations that outlast
client timeouts; small packets complete in minutes and retry cheaply.

### Packet content — the design is decided before dispatch

Test style that the sonar gate WILL flag (three stories of evidence —
write it right the first time, do not spend a fix session): JUnit 5
test methods and classes are package-private, never `public` (S5786);
no commented-out code blocks in tests (S125); one assertion chain per
subject, no redundant re-assertions (S5838, S5853); mock/fixture data
lives in test scope only.

Characterization-test packets (S01 retro: all four escalations were
this task class) additionally carry: (1) the specific legacy test cases
to port WITH their exact expected assertion values quoted; (2) the
instruction that expectations are the contract — never adjusted to
match code; (3) scope bounded to one class; (4) when the exercised
logic is out of story scope, pin values via a TEST-LOCAL expectation
helper — never invent src/main classes.

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

**Run the task sensor EXACTLY ONCE, immediately before the commit** —
not after every edit (each run is a full Maven cycle; sessions were
measured spending 2–4 of them). Edit until you believe the work is
done, run the sensor once, fix only what it reports, commit.

**Sensors: run the task sensor BEFORE you commit — never commit red**
(S01 retro). `sensors.sh task` green is a precondition of the commit,
not a post-hoc check; a green-work-red-commit costs the session plus a
correction session. Sonar-tier findings surfaced by the supervisor's
post-commit milestone cadence are the DESIGNED in-loop catch, not a
session failure — fix them in the dispatched session without
relitigating the commit.

**Sensors after EVERY task (cheap → expensive):**

```bash
.hermes/harness/sensors.sh task        # clean test on the ISOLATED repo
```

The sensors run on a per-run isolated Maven repository (factory-parity:
locally-installed artifacts do not exist there, exactly like the
pipeline). `clean` stays non-negotiable — stale `target/` classes hide
missing dependencies the factory WILL catch.

If the task touched `pom.xml`, `application.properties`, or any other
build/runtime configuration — and on every milestone boundary (3–4
tasks) — escalate to `.hermes/harness/sensors.sh milestone` (isolated
clean verify PLUS the factory's own new-code sonar gate, so style
violations die here, not in M5 ship rounds):
the factory runs the full Quarkus package build, whose extension
processors enforce prod-mode requirements (e.g. Hibernate ORM demands a
configured default datasource) that `clean test` never exercises —
test-scoped fixes can still fail prod packaging.

**The factory quality gate is part of every task's acceptance.** SonarQube
fails the exit on: new-code coverage < 80%, any new violation, or > 3%
duplicated new lines. Consequences for task packets:

- Code-producing tasks (harvest included) must ship **unit tests with the
  code** — coverage debt is a gate failure, not a follow-up.
- **Mock external boundaries only** (REST clients, remote services,
  datasources). Internal collaborators stay real: a test that mocks the
  classes under migration asserts the mocks, not the migration — no-op
  service mocks make legacy pricing/behavior assertions pass vacuously
  or fail falsely. When a legacy test suite exists, its assertion values
  are the contract; never edit an expected value to make a test pass.
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
is the default, not an invariant. **Escalated work carries the FULL
packet acceptance — nothing is waived by escalating**: unit tests ship
WITH the code (≥ 80% new-code coverage), the decided MAPPINGS.md shapes
are honored (never stub or fake an integration — a hardcoded stand-in
for an external service is a functional regression, not a migration),
every `preserve:` item in migration.yaml stays intact, and the sensors
run before commit. Start the run-log row with `ESCALATED` (the
supervisor counts escalations as a packet-quality KPI) and note why the
packet failed the worker. If you neither escalate nor finish, record the task in
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


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
Analysis evidence (from MTA — when mta-findings.json is present; K2):
                ≤6 incidents; ≤400 chars per message/code field;
                ≤2400 chars combined message+code (K2-CAP); round-robin
                across Findings rules (K2-RR)
Constraints:    follow AGENTS.md and the repo skills; no scope creep
Inputs:         attached via -f (spec.md, tasks.md, touched files)
Acceptance:     <files expected to change>; mvn -q clean test passes
Out of scope:   <explicitly excluded work>
```

`task-packet.py` injects Analysis evidence from `migration/mta-findings.json`
for the task's Findings ids (hard caps; same section is passed to MiniMax
escalation). Treat the rule message as authoritative remediation guidance.

## M4 — execution loop

### Model routing (V7) — Qwen codes; MiniMax orchestrates

| Seat | Model | Owns |
|------|-------|------|
| Worker (default for M4 coding) | Qwen3.6 27B via OpenCode | `rewrite` + `infer` file changes |
| Orchestrator | MiniMax M2 via Hermes | M1–M3, sensor-fix, M5, escalation after worker fail |

Mechanical harvest/POM/port work is **not** a MiniMax job. The supervisor
runs OpenCode first (`WORKER_FIRST=true`). If you are in an escalation
session: dispatch `opencode` for file-changing work; do not apply rewrite
edits with your own tools unless the worker already failed.

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

**Package rename is the full `legacyPackage` → `targetPackage` prefix
replace** (what `harvest-from-staging.sh` does). Example:
`com.redhat.coolstore.service.PromoService` →
`com.demo.service.PromoService`. Never write
`com.demo.coolstore.*` when `targetPackage` is `com.demo` — that partial
rename compiles, fails the package sensor, and breaks imports across
stories (V6 abort). Worker packets must map to `$TGTP/...` paths only.

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
(`sleep 30` then check for the `opencode` process) until it exits before
doing anything else. Before dispatching, verify no worker is already
running. The supervisor kills residual `opencode` processes after
`WORKER_WAIT_CAP` (default 900s) and then runs verify-and-commit — do not
rely on a 60-minute orphan wait.

### Denied command shapes (fast-fail — never burn ~5 min)

The headless command policy denies these shapes. Prefer bundled scripts;
if you must run a one-liner, keep it a single short argv (no heredoc):

| DENIED (will hang then block) | USE INSTEAD |
|------------------------------|-------------|
| `python3 <<'EOF'` / `python3 - <<EOF` heredocs | `python3 .hermes/harness/<script>.py …` or `scripts/summarize_worker.py` |
| Multi-line `python3 -c '…'` | Bundled harness script with file args |
| Scratch `mkdir /tmp/rewrite-staging` + OpenRewrite | `harvest-from-staging.sh` (M1 already ran recipes) |
| Background `opencode run … &` | Foreground `opencode run …` with ≥1800s timeout |

See `.hermes/harness/denied-shapes.md` for the platform allowlist contract.

### Verify-and-commit (orphan / retry) — no automatic second worker

When the supervisor dispatches VERIFY-AND-COMMIT (orphan worker recovery):

1. Inspect `git status --porcelain`.
2. Run `.hermes/harness/sensors.sh task` once.
3. **Do NOT launch `opencode`** unless the tree is dirty **and** that sensor is RED.
4. If GREEN: commit with the required `T-0XX:` prefix describing the work.
   Do **not** invent allow-empty `ALREADY COMPLETE` commits — that path is
   supervisor-only via `already-complete.py` (O-AC).

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

**Recurring Sonar rules to write correctly the first time (O-SONARFIX,
migration-general — V9 S03 T-008 probe):**

- **S5778** — `assertThrows` / `assertDoesNotThrow` lambdas must contain
  a *single* method invocation (no setup statements *and* no constructor
  calls inside the lambda — `() -> list.add(new Foo())` is two calls).
  Put arrange steps (including `new`) before the assert.
- **S2864** — iterate `map.entrySet()` when both key and value are needed;
  do not `keySet()` + `get(key)`.
- **S5976** — near-identical tests that differ only by a constant (e.g.
  shipping price tiers) → one `@ParameterizedTest` / `@CsvSource`.
- **S2737** — do not catch an exception only to rethrow it unchanged;
  wrap with context, handle it, or remove the catch.
- **S2925** — no `Thread.sleep` for TTL/cache proofs; inject a `Clock` /
  `Instant` (or equivalent) and advance time deterministically.
- **S1066** — collapsible nested `if` → single `if (a && b)` (also covered
  by style-autofix `CollapsibleIfStatements`).

**Sensor-fix sessions (O-SFIXLOOP):** when the supervisor dispatches a
sensor-fix, verify with the *cheap* dimension check only
(`.hermes/harness/sensors.sh sonar|task|fidelity|package`).
`sensors.sh milestone` is refused during sensor-fix (exits 2).

**Never wrap harness sensors in a short `timeout` (O-SONARTIME):**
`sensors.sh sonar` needs ~2–3 minutes. `timeout 60 .hermes/harness/sensors.sh sonar`
exits 124 before the gate finishes (V9 S03 T-008). Use the sensors
unwrapped, or `timeout` ≥ 600s.

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

Do **not** run `sensors.sh milestone` inside a supervisor sensor-fix
session — use `sensors.sh sonar` (or the matching cheap dimension). The
supervisor re-runs the triggering sensor after your commit.

**Package-structure tasks (O-PKGDIR):** never leave an empty directory.
Add `.gitkeep` or `package-info.java` so git can commit. The supervisor
also drops `.gitkeep` into empty `src/**/java` dirs before mechan-commit.

**Worker closeout:** always finish with `sensors.sh task` GREEN and ONE
commit whose message starts with the task id (`T-00N:`). Exiting 0
without a commit forces MiniMax escalation (V9 S03 T-007).

**Target destination basename is mandatory (O-TGTNAME):** when the plan
names `→ src/main/java/.../CartEndpoint.java`, create that exact file and
class name. Do not invent Quarkus-idiomatic renames (`CartResource`,
`CartController`). O-T6d will refuse mechan-commit on path mismatch and
burn a MiniMax escalation (V9 S04 T-001).

**Never commit `.hermes/` (O-HERMNEST):** harness files are workspace
runtime only. Do not `git add .hermes` / `git add -A` without resetting
`.hermes`. Nested `.hermes/harness/harness/` from a bad copy is also
forbidden in git.

**RestAssured / JAX-RS endpoint tests (O-RESTJSON / O-RESTEMPTY / O-TESTISO):**
when writing `@QuarkusTest` RestAssured suites for migrated endpoints:

1. **JSON paths** — list fields live under the collection property, not the
   response root. Prefer
   `body("shoppingCartItemList.find { it.product.itemId == '…' }.quantity", …)`
   (or the real DTO field names from the harvest). Root-level
   `find { it.product… }` returns null and fails GREEN-looking tests.
2. **Empty path segments** — `pathParam("id", "")` often yields **200/404/405**
   from JAX-RS routing, not a resource-level 400. Do not assert 400 on empty
   path params unless the API uses query/form params (or a dedicated
   validation route the plan requires). Prefer non-empty invalid ids, or
   `@QueryParam` validation tests.
3. **Isolation** — use a **unique cart/resource id per test** (or
   `@BeforeEach` clear). Shared ids make later tests see leftover items
   (`getCart` expected empty, actual size 1).
4. **Never commit with task sensor RED** claiming “pre-existing failures are
   out of scope” (V9 S04 T-003). Fix or narrow the suite until
   `sensors.sh task` is GREEN, or leave uncommitted and escalate honestly.

**Sensor-fix / escalation:** if surefire shows JSON-path or status-code
mismatches, fix the **tests or the contract** — do not only rewrite the
endpoint and debt-record RED (V9 S04 T-002/T-003 MiniMax path).

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


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
| Worker (O-SFIXWORKER) | Qwen3.6 27B via OpenCode | sensor-fix first; cheap sensor re-verify |
| Worker (O-M3WORKER) | Qwen3.6 27B via OpenCode | M3 SPECIFY draft/fix; plan-lint verifies |
| Orchestrator | MiniMax M2 via Hermes | M1–M2, M5 evaluate/ship, M4 escalation, capped sfix/M3 rescue |

Mechanical harvest/POM/port work is **not** a MiniMax job. The supervisor
runs OpenCode first (`WORKER_FIRST=true`). Sensor-fix also runs Qwen first
(`WORKER_SFIX_FIRST=true`) with one MiniMax rescue if the triggering sensor
stays RED. M3 drafts on Qwen (`WORKER_M3_FIRST=true`, ≤2 attempts) with one
MiniMax backstop if plan-lint stays RED. If you are in an escalation
session **without** O-ESCREOPENCODE: prefer dispatching `opencode` for
file-changing work. **O-ESCREOPENCODE / O-ESCREOPENCODE-ENFORCE /
O-ESCREOPENCODE-SENSORRED:** after a wedged/skipped/incomplete worker
(READ_THRASH, JSON_STALE, INFERABSENT, WORKERWEDGE, CHARORACLE,
O-STEPFINISHRED / cause `sensor-red` / SENSOR RED false-complete), MiniMax
**owns** file edits — do **not** re-dispatch `opencode`/Qwen (that nurses
hollow invent after harvest-only). The supervisor PATH-refuses and kills
opencode spawn during that escalation. Prefer O-NULLACTION
(`/tmp/escalation-noaction-<tid>.txt`) over hollow invent.

**Measure after this routing:** MiniMax session-minutes (sfix+M3+escalation)
and M4 rescue rate must not rise — revisit M5 evaluate only if both improve.

**O-ESCALORACLE:** the worker packet carries `Shape:` (create|modify|remove|
structure|verify|harvest) and `Oracle:` (absent|present). On escalation,
honor those fields — if Oracle=absent / Shape=remove, prove named targets
are gone; never create a file solely to delete it; never invent unlisted
deletion targets.

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

**Rewrite test migrations (O-HARVESTSTALL / O-ESCALGPLACE):** before inventing
new test stubs, harvest or port the staging/legacy test basename the task
names. Never close with `assertThat(true)` / `assertTrue(true)` (G-PLACE) —
run `.hermes/harness/sensors.sh task` GREEN before declaring success
(escalation path included; supervisor refuses red commits).

**FIRST mutate (O-WORKERWEDGE-RCA / O-WORKERREAD / O-CREATEFIRSTMUT /
O-FIRSTMUTBASH / O-INFERFIRSTWRITE / O-TASKMUTATE):** within the first ~5 tool
calls, `edit`/`write` the task Target (or run `harvest-from-staging.sh`). Do
**not** burn the seat on read/glob tours — the supervisor kills read-thrash,
frozen JSON sessions, and **M4 seats with 0 edit/write past ~120s**
(O-TASKMUTATE / ARCH-C1 — same first-write deadline as M3/sfix), then skips
further worker seats for the rest of the story. Plain `bash`
(`ls`/`cat`/explore) does **not** count as first mutate (O-FIRSTMUT). A
successful `harvest-from-staging.sh` that prints `harvested: … -> …` **does**
count (O-FIRSTMUTBASH) — do not get false READ_THRASH-killed after landing
Targets. **Class=infer with multiple Targets (O-INFERFIRSTWRITE):** after
Targets already exist (preseed/harvest), the first mutate must be a *concrete
import/API edit* on one named leaf Target (prefer `*RowMapper` /
`*Extractor` / small helper) — e.g. drop `org.springframework.jdbc.*` and add
`DataSource`+`@Inject` — before touring the full sibling stack. Harvest-as-
mutate alone is not enough once files are on disk. **Shape=create:** the
Target basename must exist after the first write batch (threshold is tighter
— ~10 reads with 0 writes → kill). Characterization: Target `*Test` first
before WireMock/pom rabbit holes. **M3 SPECIFY:** write
`specs/<slug>/tasks.md` first (lint gate), then plan/spec — do not explore
for 12 minutes with an empty specs tree (O-M3EMPTY).

Pass the package-relative path (`model/Product.java`,
`service/CatalogService.java`, `repository/jdbc/JdbcPet.java`) — never the
package directories, never an absolute or dotted path. **O-HARVESTFULLPATH:**
if you copy a Target-design line
(`src/main/java/<legacyPackage>/repository/jdbc/JdbcPet.java`), the script
strips the `src/(main|test)/java/<legacy|targetPackage>/` prefix — prefer
the short form anyway. Hand-building `src/main/java/$TGT/...` is how a
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

**PropertyComparator → JDK sort (O-FIDELITYSORT / O-FIDELITYDAO):** when
staging uses `PropertyComparator.sort(list, new MutableSortDefinition(...))`,
drop the Spring support call **and keep the staged list shape**:
`List<T> sortedX = new ArrayList<>(getXInternal());` then
`sortedX.sort(Comparator.comparing(...));` then the same
`Collections.unmodifiableList(sortedX)` return. Do **not** rewrite to
`stream().sorted(...).collect(...)` — harvest-fidelity already forgives the
Spring `PropertyComparator` line but REDs the collateral `new ArrayList<>(…)`
absence (v3 S02 T-003 / W4-018). Never re-harvest Spring beans.support
imports to green-wash fidelity.

**Port: rename | reimplement (O-PORTREIMPL / O-FIDELITYPORT /
O-REIMPLCREATE):** when the task packet declares `Port: reimplement`
(or Spring Data→Panache / JDBC→Agroal), treat the seat as an API swap —
convert-after-harvest is mandatory (`O-SDJPAHARVESTONLY`); follow the
task's API mapping table (per-type); do not tip-accept harvest-only
Spring Data or empty Panache shells. **O-FIDELITYPORT:** harvest
byte-match fidelity applies only to `Port: rename` (default harvest);
on `Port: reimplement` the fidelity dimension is redesign-sig / public
signatures — not Spring-import byte-match. **O-REIMPLCREATE /
O-RESTCREATE:** `Port: reimplement` + `Shape: create` always carries the
create-procedure tip — (1) `harvest-from-staging.sh` / write Target
basename first (create-from-legacy, not noop), (2) cite+apply the API
mapping table, (3) first-write anchor before sibling tour
(`O-CREATEFIRSTMUT`). Plan-lint REDs missing Port / mapping /
create-procedure prose on API-swap creates.

**DataAccessException / no spring-tx (O-M3PRESERVEDAO / O-DAOEXMAP /
O-HYGIENEWORKER / O-FIDELITYDAO / W4-085a):** when harvesting repository
interfaces into a Quarkus pom (no `spring-boot`), **remap per exact symbol**
or strip throws — never substring-replace `DataAccessException` inside
`EmptyResultDataAccessException` (invents
`EmptyResultPersistenceException` under `org.springframework.dao`). Table:

| legacy | target |
|---|---|
| `DataAccessException` | `jakarta.persistence.PersistenceException` |
| `EmptyResultDataAccessException` | `jakarta.persistence.NoResultException` |
| `DataRetrievalFailureException` | `jakarta.persistence.PersistenceException` |
| `ObjectRetrievalFailureException` | `jakarta.persistence.EntityNotFoundException` |

Canonical taught-side copy of this table: `MAPPINGS.md` §Spring Boot →
Quarkus (Spring DAO exceptions). Never add `spring-tx`/`spring-jdbc`/
`spring-orm`, and **never invent** a local
`targetPackage…DataAccessException` stub (S03 T-001 `f8dbcfe`). M3 must
not say “Preserve DataAccessException” without the table (plan-lint
`O-M3PRESERVEDAO`). Prefer `harvest-from-staging.sh`.

**Spring residue = 0 (O-SPRINGRESIDUE):** after Class=infer /
Port=reimplement convert, `org.springframework` under `src/main/java` must
be 0 (comments ignored). Sensors + commit-hygiene RED
`O-SPRINGRESIDUE` (peer of `O-CDIPARTIAL` / `O-JDBCHARVESTAPI`). Invented
`*PersistenceException` under `org.springframework.*` is RED.

**Spring Data → Panache harvest (O-SDJPAHARVEST / O-SDJPAHARVESTONLY /
O-T4SPRINGDATA / O-SDJPA-SKIP):**
when the Quarkus pom has **no** `spring-data` / `quarkus-spring-data-*`,
do not burn harvest/compile seats on `SpringData*` — declare
`Port: reimplement` + Panache mapping, or Already-satisfied /
redesign-skip when ≥3 `Jpa*RepositoryImpl` `@ApplicationScoped` cover
domain repos and Override-only work is done (**O-SDJPA-SKIP** /
**O-T4SPRINGDATA**). If keeping Spring Data `extends`, pom must carry
`quarkus-spring-data-jpa`. For Shape=`create`|`modify` Panache
consolidate/convert, `harvest-from-staging.sh` alone is **not**
task-complete (**O-SDJPAHARVESTONLY**). After harvest, before
`step_finish` / tip-accept / Already-satisfied: rewrite every Target
Spring Data repo to `PanacheRepository` / `PanacheRepositoryBase`, drop
`org.springframework.data.*`, and implement finder bodies — do **not**
exit 0 on Spring Data residue / Panache=0 dirt (sensors RED
`O-SDJPAHARVESTONLY`; supervisor rewrites false `rc=0`→`42` via
O-STEPFINISHRED). Consolidating is also **not** bare
`extends PanacheRepository<T>` plus empty finder shells
(**O-SDJPAHARVEST**). Keep the staging **domain-repository contract**
(`extends`/`implements` `<DomainRepository>` **and**
`PanacheRepository` or `PanacheRepositoryBase`). Rewrite staging method
`@Query` JPQL into Panache `find`/`list` **default or class methods** —
never park orphan `@NamedQuery` on the repository interface. Hollow
`ReturnType finder(...);` without a query body fails sensors. When staging
has `*RepositoryImpl` Override delete bodies, harvest those Impl classes
with the Override interfaces (iface-only ≠ consolidate). Prefer an
`@ApplicationScoped` class implementing the domain iface +
`PanacheRepositoryBase` when Override Impls need `EntityManager`. Sensors
+ commit-hygiene RED `O-SDJPAHARVEST` / `O-SDJPAHARVESTONLY`. Plan Shape
for Panache/convert `.java` Targets must be `create`/`modify`
(O-STRUCTJAVA).

**Partial CDI / Spring JDBC harvest (O-CDIPARTIAL / O-JDBCHARVESTAPI /
O-SPRINGRESIDUE / O-AGROALHELPERSIG / O-STEPFINISHRED):**
`harvest-from-staging.sh` may stamp `@ApplicationScoped` and remap
`@Autowired`→`@Inject`, but that is **not** task-complete for JDBC *Impl
classes. Before `step_finish` / tip-accept / Already-satisfied: (1) every
CDI-scoped Target must use jakarta `@Inject` (no leftover `@Autowired`);
(2) drop **all** `org.springframework` under `src/main/java` (comments
ignored) — rewrite `NamedParameterJdbcTemplate` / `SimpleJdbcInsert` /
`JdbcTemplate` to Agroal `DataSource` + `java.sql` (or `EntityManager`) —
never re-add `spring-jdbc` (O-JDBCREGRESS / O-SPRINGRESIDUE); (3)
**O-AGROALHELPERSIG** — preserve staging *exact public* helper method
names on the Impl class itself through the rewrite (`mapRow`,
`create*ParameterSource`, `extractData`, …). Inline Spring `RowMapper` /
`ParameterSource` as same-named *public* methods on the converted Impl —
do **not** rename (`mapRow`→`mapVetRow`), privatize, or move-only onto a
RowMapper collaborator (redesign-sig REDs missing names while
`spring.jdbc=0`); (4) **O-STEPFINISHRED** — run
`.hermes/harness/sensors.sh task` before claiming complete; if SENSOR RED
(incl. O-AGROALHELPERSIG / O-SPRINGRESIDUE), refuse `step_finish` /
tip-accept / Already-satisfied / prose "ready for commit" — keep editing
until GREEN then `commit-gated.sh`, or exit honest-incomplete (supervisor
rewrites false worker `rc=0`→`42` and escalates as `sensor-red`, not
`worker-failed`). Sensors + commit-hygiene RED `O-CDIPARTIAL` /
`O-JDBCHARVESTAPI` / `O-SPRINGRESIDUE` on partial trees; ESCW refuses
allow-empty. Pair O-FIRSTMUT — zero edit/write after harvest-only is a
failure, not done.

**Escalation util / non-Owns refuse (O-ESCWSCOPEUTIL):** MiniMax/Hermes
escalation must edit **only** this task's Owns/Target paths. Do **not**
create or harvest `src/main/**/util/*` (or any later-story class listed in
`LATER_CLASSES`) mid-convert to clear compile errors — keep those in
`migration/staging` until their owning story. The scope sensor removes
untracked later-class dirt (`O-ESCWSCOPEUTIL`); tip REJECT if util
collaborators land with a convert tip. Pair O-ESCWSCOPE / O-COLLABOWN
(missing same-package peers → own/defer them in plan, never invent util).

**MiniMax scope-quit with unfinished residue (O-MMSCOPEQUIT):** when any
sibling Target under the same task already proves the Agroal / `DataSource`
+ `java.sql` pattern (or sensors RED `O-JDBCHARVESTAPI` / leftover
`org.springframework` on remaining Targets), MiniMax/Hermes escalation
must **not** exit with "scope reclassification", "task splitting",
"human approval", or similar scope-quit narratives. Sensors refusing a
partial tip are **not** a scope defect — continue the remaining Targets
in the same seat until `org.springframework` residue = 0 and sensors
GREEN, or stop with an honest sensor-RED / O-NULLACTION that does **not**
ask to split the convert stack. Pair W4-085 §2 (convert titles understate
stack replacement).

**Tree-fix must not stub-nuke (O-TREEFIXSTUB / O-COLLABOWN):** clearing
`org.springframework` residue by rewriting owned Targets to comment-only
`/* REMOVED: … */` husks, deleting type bodies, or deleting interface
methods is **forbidden**. That can leave sensors falsely GREEN while the
convert stack is dishonest. Tree-fix / tip-accept / commit-hygiene RED
`O-TREEFIXSTUB` on comment-only stubs and on tips that delete owned Target
`.java` paths. For JDBC convert stacks, implement the **full** repository
API with Agroal `DataSource` + `java.sql` (or `EntityManager`). If
same-package collaborators required by Target files are not owned or
explicitly deferred (`O-COLLABOWN` plan defect), prefer honest
`O-NULLACTION` over stub-delete.

**Characterization oracle present (O-CHARORACLE / O-NULLACTION):** when
porting/characterizing via `Source→Target` under `src/test/`, the SOURCE
file must exist in `migration/staging` or `/projects/legacy`. If the packet
carries `O-CHARORACLE: characterization oracle ABSENT`, do **not** invent
hollow / `assertThat(true)` / G-PLACE tests. Write
`/tmp/escalation-noaction-<tid>.txt` with `O-CHARORACLE: oracle absent` and
STOP — that is success (O-NULLACTION), not a burn. Re-plan M3 to drop the
phantom path. **O-ESCREOPENCODE-ENFORCE / O-ESCREOPENCODE-SENSORRED:** do
not reopen OpenCode/Qwen to continue the invent path after this tip or
after O-STEPFINISHRED / sensor-red escalation — supervisor refuses/kills
that spawn.

**Infer + derived-absent oracle (O-INFERABSENT / O-ORACLEDERIVE):** the
packet `Oracle:` line is **derived** (legacy test for Target? Target in
destination?) — never a silent `present` default. If the packet tips
`O-INFERABSENT`, this is a plan defect: write
`/tmp/escalation-noaction-<tid>.txt` with `O-INFERABSENT` and STOP
(O-NULLACTION). M3 must reshape to `Shape: create` (create-procedure),
`Shape: verify` (deferral), or an explicit one-line `Proceed: O-NULLACTION`.
Do not READ_THRASH inventing behaviour with nothing to observe.

**Collection getters / harvest fidelity (O-STYLEFIDELITY):** when staging
returns a mutable field (`return roles;`), keep that return shape after
harvest. Do **not** wrap with `Set.copyOf` / `Collections.unmodifiable*` to
appease Sonar S2384 — that is a behavioural change (UOE on mutate-in-place
callers) and fidelity RED. Fix S2384 via approved recipe paths or document
debt; never land defensive-copy harvest drift in style-autofix or sfix.

**Sensor-fix first mutate (O-SFIXMUTATE):** after you name the
fidelity/sonar root cause from `/tmp/sensor-*.log`, your **next** tool must
be `edit`/`write` on the drifted file. Diagnose-then-read thrash with 0
mutates is killed early (~120s) and escalated — do not burn the full sfix
budget re-reading the same logs.

**OpenAPI DTO harvest (O-DTOCOV):** harvested `**/dto/**` beans are
generated shapes — the supervisor runs `ensure-dtocov-pom.py` before
milestone Sonar so `pom.xml` carries `sonar.exclusions` /
`sonar.coverage.exclusions` / `sonar.cpd.exclusions` for `**/dto/**`.
Do not invent BaseDto hierarchies or ceremonial getter tests to clear
coverage/CPD/S6353 on dto harvest commits (see SHIPPING.md).

**Feign → MicroProfile REST client (O-RESTCLIENTDEP):** import
`org.eclipse.microprofile.rest.client.inject.RegisterRestClient` — never
`...annotation.RegisterRestClient`. After edits: `mvn -q compile` before
exit (wrong package fails with cannot-find-symbol even when the Quarkus
REST-client dep is on the pom).

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
  a *single* method invocation (no setup steps *and* no constructor
  calls inside the lambda — `() -> list.add(new Foo())` is two calls).
  Put arrange steps (including `new`) before the assert.
  **O-SHIPASSERTWEAK:** never “fix” S5778 by deleting
  `assertThrows(UnsupportedOperationException)` (or renaming
  `*_returnsUnmodifiable*` → `*_returnsListWithExpectedBehavior` and
  keeping only `assertNotNull`/size/`assertSame`). Keep the typed
  unmodifiable contract: arrange the element outside the lambda, then
  `assertThrows(UnsupportedOperationException.class, () -> list.add(x))`.
  Broad `catch (Exception)` / empty-catch “expected” is also forbidden.
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
- **S6813** — field dependency injection must not be used. Fix by
  **constructor-injecting** collaborators (`private final EntityManager em`
  + `public Foo(EntityManager em)`). Do **not** “fix” S6813 by rewriting
  JPQL/SQL string concatenation to `:params` — that addresses a different
  rule (and may be good separately) but leaves S6813 RED (O-S6813MISREAD).
- **S125** — remove commented-out statements in production code (including
  legacy `//this.em.remove(...)` residue after redesign).
- **JPA writes need `@Transactional`** — after redesigning Spring Data /
  `@PersistenceContext` repos to plain `EntityManager`, annotate
  mutating methods (`save` / `delete` / `persist` / `merge` / `remove`)
  with `jakarta.transaction.Transactional` (O-JPACTX). Reads may stay
  non-transactional unless the brief requires otherwise.

**Sensor-fix sessions (O-SFIXLOOP):** when the supervisor dispatches a
sensor-fix, verify with the *cheap* dimension check only
(`.hermes/harness/sensors.sh sonar|task|fidelity|package|findings`).
If `/tmp/sensor-milestone.log` shows `FINDINGS:` / `FINDINGS RED`, the
dimension is **findings** — fix the listed pom/code incidents and verify
with `sensors.sh findings` only (O-SFIXWRONGDIM: do not polish unrelated
tests/comments while FINDINGS is RED).
`sensors.sh milestone` is refused during sensor-fix (exits 2).

**O-SFIXNODELTA:** the supervisor skips a *task-attributed* sensor-fix when
K7 failure-delta reports `SUMMARY new=0 gone=0` **and** the tip has no
content (0-byte / structure `.gitkeep` only). That RED is not this tip's
debt — do not burn a seat editing unrelated files under the task name.

**Never wrap harness sensors in a short `timeout` (O-SONARTIME):**
`sensors.sh sonar` needs ~2–3 minutes. `timeout 60 .hermes/harness/sensors.sh sonar`
exits 124 before the gate finishes (V9 S03 T-008). Use the sensors
unwrapped, or `timeout` ≥ 600s.

**Hermes/MiniMax gated commits (O-ESCTERM60):** do **not** run bare
`git commit` for `T-NNN:` / `sensor fix:` tips under a short terminal
timeout. The commit-msg hook re-runs `sensors.sh task` (~90–120s) and a
60s tool timeout kills the commit (exit 124) before the tip lands. Prefer:

```bash
# terminal timeout ≥300s (or background+notify). Stages optional paths.
.hermes/harness/commit-gated.sh 'T-005: …' src/test/java/…/FooTest.java pom.xml
```

That runs the task sensor once, then `SKIP_SENSOR_GATE=1 git commit`.
Do not stage `migration/mta-findings-current.json` on coding tips (O-SFIXSCOPE).

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

**Structure / `.gitkeep` targets (O-STRUCTTGT):** when `Shape: structure` or
the Target path ends with `.gitkeep`, the deliverable is package directories
plus `.gitkeep` only. Do **not** harvest or create entity/DTO `.java` classes
even if **Absorbs** lists later-story sources — those cites are ownership
markers for future tasks. Task packets gate O-TGTNAME to the `.gitkeep` path
only (v3 S01 T-003: Absorbs scrape → full model harvest → scope revert).

**Shape=structure + `.java` Targets (O-STRUCTJAVA):** if Target design names
real `.java` sources (Panache/harvest/convert) under `Shape: structure`, that
is a **plan defect** — plan-lint REDs it at M3 (`LINT:O-STRUCTJAVA`). If a
seat still reaches you with that contradiction, write
`/tmp/escalation-noaction-<tid>.txt` with `O-STRUCTJAVA` and STOP
(O-NULLACTION) so M3 can reshape to `create`/`modify`. Do **not** tip
`.gitkeep`-only as satisfying a Panache/class Goal, and do not READ_THRASH
trying to invent both.

**After scope revert (O-SCOPEBACKFILL / O-REVERTPURE):** if the story-scope
sensor removes later-story classes from a structure task, the supervisor
restores the declared Target `.gitkeep` mechanically and commits a clear
`T-NNN:` tip — a tip that is only `scope revert` must never mark the task ✓
while the Target is absent. Scope-revert commits stage **only** the reverted
paths (never `git add -A` / `mta-findings-current.json`).

**Owns-only staging (O-OWNSTAGE):** `stage_for_task_commit` / worker
auto-commit stage **only** paths declared in the task's Owns/Target (via
`task-stage-paths.py`). Sibling entities under the same package stay
untracked for their owning tip — do not ride along on `git add -A`.
`mechan-match.py` refuses create/harvest tips that still stage extra
`src/**/*.java` outside Owns/Target (`ownstage-extra`).

**Never commit `.hermes/` (O-HERMNEST):** harness files are workspace
runtime only. Do not `git add .hermes` / `git add -A` without resetting
`.hermes`. Nested `.hermes/harness/harness/` from a bad copy is also
forbidden in git.

**Characterization first commit (O-CHARWEDGE):** for endpoint RestAssured
tasks, create/port the Target `*Endpoint*Test.java` and get one green
request assertion committed **before** chasing WireMock / pom dependency
rabbit holes. WireMock without the Target test file is a wedge (S04 T-007).

**MockMvc → RestAssured (O-MAPPINGS-PETCLINIC):** Spring `MockMvc` suites are
a full rewrite, not a harvest. There is **no** `@WithMockUser` equivalent —
tests that need roles must create real users (or use the decided security
test helper). Budget this in M2/M3 test-task briefs; do not discover it as
surprise M4 debt on REST specimens.

**RestAssured / JAX-RS endpoint tests (O-RESTJSON / O-RESTEMPTY / O-TESTISO):**
when writing `@QuarkusTest` RestAssured suites for migrated endpoints:

1. **JSON paths** — list fields live under the collection property, not the
   response root. Prefer
   `body("shoppingCartItemList.find { it.product.itemId == '…' }.quantity", …)`
   (or the real DTO field names from the harvest). Root-level
   `find { it.product… }` returns null and fails GREEN-looking tests.
   **Enforced:** `sensors.sh` `restassured_contract` REDs `.body("find {`
   (O-RESTGUIDE / Poll 53 — prose alone did not transfer).
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

## O-IFACERENAME — preserve legacy public method names

When converting/porting a class that exists in `migration/staging`, keep the **exact** public method names from staging (including legacy typos like `getAllSpecialtys` or odd names like `addOwner` on `UserRestController`). Renaming for grammar or domain clarity trips redesign-sig (O-REDESIGNSIG) and forces MiniMax escalation. Fix call sites only if the plan explicitly renames.

## O-WIREUP — attach redesigned components

Signature preservation is not enough. If staging had `@Around` / `@Aspect` /
`@Scheduled` / `@EventListener`, the destination must carry a CDI attachment
(`@Interceptor` + `@InterceptorBinding`, `@AroundInvoke`, `@Observes`, …)
**or** be referenced by another source file. Empty `@ApplicationScoped` beans
with no members fail the sensor. Do not ship hollow aspect/config classes.

## O-SECAUTHTEST — exercise the security-enabled path

When adding `@RolesAllowed` / JDBC security and a `*.security.enable` property,
ship at least one `@QuarkusTest` + `@TestProfile` (or configOverrides) that sets
security enabled and asserts **401 or 403** on a protected route. The
security-disabled acceptance path alone cannot prove authorization.

## O-DSKIND — JDBC + db-kind when Hibernate / @Entity lands

Adding `quarkus-hibernate-orm` (or harvesting `@Entity`) without
`quarkus-jdbc-*` and `quarkus.datasource.db-kind` fails Quarkus boot with
`ConfigurationException: Datasource must be defined`. Wire in the same
task family:

- deps: `quarkus-jdbc-h2` + `quarkus-jdbc-postgresql`
- `%dev` / `%test` → `db-kind=h2` (+ mem JDBC URL); default/`%prod` → `postgresql`
- `%dev` / `%test` → `hibernate-orm.database.generation=drop-and-create` until a seed story

Harness `ensure-dskind.py` patches post-commit if the worker omits this;
task-packet injects the tip on entity/JPA harvests. See SHIPPING.md
O-ENTITYDSPROD (never leave unprofiled H2 as the deploy default).

## O-PRODSCHEMA — never unprofiled drop-and-create

Use `%dev` / `%test` / `%acceptancetest` for `database.generation=drop-and-create`.
Bare (production) `quarkus.hibernate-orm.database.generation=drop-and-create`
fails wiring — it drops the prod schema on every boot.

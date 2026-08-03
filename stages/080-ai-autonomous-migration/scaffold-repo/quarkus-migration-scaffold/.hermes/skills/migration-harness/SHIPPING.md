# M5 EVALUATE — final sensors and the factory gate

## Contents
- M5 evaluate — re-analysis, delta, final verify
- M5 ship — the supervised factory gate loop

## M5 evaluate — final sensors + ship

1. Re-analysis of the MIGRATED code:

```bash
kantra-ensure
# O-KANTRAPATH: binary lives under ${KANTRA_HOME:-/projects/.tools/kantra}
# (not /tmp — pod restart wipes /tmp). Supervisor owns the after-scan.
# O-DELTASTAGING: scan a copy that excludes migration/staging and .hermes.
```

Done means the baseline findings are resolved (or waived in the spec) —
not "the agent says done."

**O-DELTABASE:** after the after-scan, the supervisor runs
`.hermes/harness/findings-delta.py` → `migration/findings-delta.txt`.
Absence of a rule in the after-scan is **not** automatically resolved:
- **RESOLVED** — incident basename exists under `src/` (or pom/props landed)
  and the rule is gone after.
- **ABSENT-NOT-LANDED** — rule gone but nothing landed in `src/` (empty
  harvest / scaffold-only). Score these **0** toward resolve %.
- **SCAFFOLD-PRESATISFIED** — destination already satisfied (no story credit).
Always cite the `METRIC src_main_java` / `residual_incidents` lines so
pom/props residual cannot hide real Java progress.

**O-M5STALE:** if after-analysis fails or is substituted (no live kantra
delta), `findings-delta.txt` is stamped `STALE-AFTER` with
`stale_resolve_pct=UNSCORED` — **no rule may move into RESOLVED** and the
word "honest" must not appear. Re-run kantra before claiming resolve %.

**O-M5EVALHARVEST:** evaluate is a **delta report + optional in-story
pom/props closeout**, not a second harvest pass. Never
`harvest-from-staging` or create `model/`/`repository/`/`rest/`/`service/`
trees to clear REMAINING / ABSENT-NOT-LANDED. Explain those rows in
`migration/run-log.md` (later story / not landed). Pom-plugin residuals
(e.g. compiler/failsafe rule ids) → edit `pom.xml` only, or leave as
honest residual if out of story Owns.

**O-M5EVALDELETE:** never delete or empty story Owns / already-landed
`src/main/java` harvest to “fix” REMAINING or compile stories. If
sensors are RED, say so in the evaluate commit — do not remove
`repository/**` (or other landed packages) or swap away required deps
(e.g. `quarkus-spring-data-jpa`). Supervisor restores deletions and
FREEZEs ship when evaluate dirt includes tracked deletes under
`src/main/java` / `pom.xml`.

**O-M5SHIPHARVEST / O-QJACOCONOTEST:** preflight-fix must not harvest to
satisfy O-QJACOCO. If there is no `@QuarkusTest` yet, sensors skip the
jacoco.xml hard-fail — do not invent app classes for coverage on a
platform story.

**O-SHIPFIXCOMMIT:** when local `mvn test` / `sensors.sh task` is GREEN on
**tests-only** dirt (`src/main` clean), commit the `Preflight fix rN:` tip
**before** burning the seat on full `sensors.sh preflight` / sonar.
Supervisor also mechan-tips that class on seat timeout/`no_commit` (does
not require full preflight GREEN first). Never leave unpaid green coverage
tests sitting for attempt ≥2.

**O-SHIPFIXPOM:** mechan "tests-only" tips stage **`src/test/` only** — never
sweep unrelated `pom.xml` dependency adds (e.g. unused assertj-core) into a
tip whose subject claims tests-only. Real build-wiring pom edits need an
explicit agent commit (not the timeout mechan path).

**O-SHIPFIXJACOCO / O-SHIPFIXFINDINGS:** see boot/preflight tip hygiene under
O-BOOTSQLPROV below — no jacoco.report* strip, no findings-JSON thrash.

**O-PREFCONT:** preflight-fix attempt ≥2 is a **continuation**, not a
cold rewrite. Inspect `git status` first; continue from existing
dirty/untracked work **without** inventing new files/tests and **without**
rewriting already-present dirty tip content. Characterization floor: do
not shrink `@Test` / assertion counts vs attempt start (**O-PREFCONTUT:**
floor counts tracked + untracked); keep typed
`assertThrows(UnsupportedOperationException)` for unmodifiable getters
(O-SHIPASSERTWEAK).

**O-PREFDIMTHRASH / O-SONARFIX (S5778):** when preflight/sonar reports
`java:S5778`, arrange the mutation **outside** a single-invocation
`assertThrows` — do **not** thrash brace/bind/assertj cosmetics or burn the
seat on form-only edits while the failure file is only
`REFUSED (O-PREFLIGHTDIM)`. Prefer dim sensors (`sonar`/`task`/`fidelity`)
then **one** closing preflight. Supervisor auto-resets `/tmp/preflight-count`
at each fix-round start and on refuse (do not fight the cap by `rm`).

**O-SHIPROUNDBASE:** each M5 ship entry stamps `/tmp/ship-session-base` and
scopes Preflight/Gate/Build fix `committed()` checks to that base
(exclusive). Prior-session `Preflight fix rN:` tips under story `RUN_BASE`
must not auto-burn a fresh round. Diverged/abandoned `origin/main` tips are
**not** authority — never pull/merge them; O-SHIPREMOTE blocks non-FF push
until an operator reconciles to an honest tip (force-with-lease of known
thrash only — harness never force-pushes).

**O-SHIPNOPRSTALE:** each M5 ship entry also stamps
`/tmp/ship-session-started` (unix epoch). On Everything up-to-date
(O-SHIPNOPR), the supervisor may judge an existing PipelineRun **only** when
that run was created at/after the stamp **and** its `revision` param matches
HEAD. Prior Failed/Succeeded runs from abandoned ship rounds must **not**
open Deploy/Build/Gate fix seats — HOLD with `ship-blocked-stale-pipeline`
and wait for a post-session PipelineRun (operator/webhook trigger). Pair with
O-NOPUSHPR (stale Succeeded false-green when commits were pushed).

**O-SHIPBUDGET:** after preflight-fix rounds are spent, the supervisor runs
**one** untimed closing preflight. GREEN → push. Still RED (including boot /
`Schema-validation: missing table`) → **HOLD** with
`ship-blocked-preflight-budget` — never log `pushing anyway (factory as
arbiter)`. Factory cannot invent Flyway/schema/wiring; unpaid preflight must
not reach `git push`.

**O-BOOTNOFLYWAY / O-BOOTDEVPG / O-BOOTSQLPROV:** preflight `boot_check` uses
prod-profile + DEV Postgres. Schema provenance is **Flyway/Liquibase
migration files only** (`db/migration/*.sql` or `db/changelog/*`) —
`sql-load-script` is **not** provenance (it seeds data after schema exists).
Entity-only stories before Flyway keep the same DEV Postgres URL and set
`QUARKUS_HIBERNATE_ORM_DATABASE_GENERATION=drop-and-create` for the probe
only — never `QUARKUS_PROFILE=dev`/H2 (build-time postgresql db-kind rejects
`jdbc:h2:…`; see O-ENTITYDSPROD / O-PREFLIGHTH2). Preflight-fix must **not**
add `sql-load-script` / `import.sql` solely to flip provenance or clear boot
RED; prefer real Flyway or leave generation override to the sensor. Do not
pair `%prod.sql-load-script` with `%prod.generation=validate` (O-GENSEED).

**O-SHIPFIXJACOCO:** Preflight/boot tips must not strip
`quarkus.jacoco.report` / `quarkus.jacoco.report-location` while keeping
`quarkus.jacoco.data-file` (scaffold O-QJACOCO wiring). Only touch jacoco
props when qjacoco/coverage RED cites them.

**O-SHIPFIXFINDINGS:** Preflight/Gate/Build/Deploy fix tips must not bundle
`migration/mta-findings-current.json` churn. Supervisor scrubs that path from
those tips (same as T-NNN via O-T1FINDESC).

2. Factory pre-flight: run `.hermes/harness/sensors.sh preflight`
   (isolated clean verify, new-code sonar/coverage gate, prod-profile
   boot where applicable). **L-M5e:** the evaluate commit message must
   state preflight GREEN or RED honestly — never claim “factory/preflight
   green” unless that command exited 0. `mvn verify` alone is not the bar.
   Prefer fixing RED before commit; if budget is exhausted, commit with
   RED stated so ship correction is explicit.
3. Commit with a conventional message referencing the spec id. Under the
   supervisor, DO NOT push — the supervisor ships and drives M5 ship.
4. Final report: tasks completed/deferred, debt entries, findings delta
   (before → after).

## M5 ship — the factory gate loop (supervised)

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

**O-GATESCOPE:** gate/build/preflight correction commits may edit
`src/main` paths **named in `/tmp/gate-violations.txt`** even when those
paths are outside the current story's `STORY_SCOPE`. The story-scope
sensor keeps those allowlisted files and only reverts other out-of-scope
`src/main` edits. Do not park factory-named DTO/smell fixes in
`migration/debt.md` as "out of scope" — fix them in the Gate fix commit.
For Java records, put Bean Validation constraints on **record components**
(not only accessors) so `validator.validate(record)` fires (O-RECORDBV).

The supervisor classifies WHICH pipeline stage failed and starts the
matching correction session:

**Build correction** (`/tmp/build-failure.txt`): the repository does not
build in the pipeline environment — workspace-only state does not ship.
Diagnose the root cause (typical: a dependency resolvable only locally,
e.g. an installed legacy jar). Make the repository self-contained —
vendor the jar in-repo with a file-based repository declaration, or
replace the dependency — and prove pipeline-equivalent resolution: purge
the artifact from the local repo, then `mvn -q clean verify`.

**Deploy correction** (`/tmp/deploy-failure.txt`): build and gate passed
but the service does not start — the evidence file carries the failed
task and the crash-looping pod's logs. Typical classes: Hibernate schema
validation vs Flyway DDL drift, missing config/env, missing runtime
dependency. Fix the ROOT CAUSE in the repository (source, migrations,
`application.properties`, or `k8s/`); never weaken validation to make
the error disappear.

**O-PREFLIGHTH2:** never flip the default `quarkus.datasource.db-kind` to
`h2` just to green local preflight. Factory deploy injects a PostgreSQL
JDBC URL; an H2 driver then crash-loops. Use `%dev`/`%test` profiles or
env overrides for local H2; keep prod/default postgresql aligned with
`k8s/` and `QUARKUS_DATASOURCE_*`.

**O-HTTPPORT:** when converting Spring `server.port` → `quarkus.http.port`,
do **not** copy a non-8080 legacy port (e.g. Petclinic `9966`) unless
`k8s/*/containerPort` + Service/probes (or `QUARKUS_HTTP_PORT`) match.
Default/keep **8080** for the deploy contract. Sensors fail
`http_port_deploy_contract` on mismatch (same failure class as
O-PREFLIGHTH2: locally justified, deploy-broken). Prefer rewriting a
`# preserve:` marker to point at the Quarkus successor over deleting it.

**O-GENSEED:** if `quarkus.hibernate-orm.sql-load-script` is set, do **not**
use `database.generation=validate` or `none` — fresh DB then has no schema
for `import.sql` / validate fails. Prefer `update` or `drop-and-create`
when seeding. Sensor `gen_seed_contract` REDs the mismatch.

**O-PCTFILE / G2:** Quarkus config profiles use either (1) `application-{profile}.properties`
(e.g. `application-dev.properties` — **no** `%` in the filename) or (2)
`%dev.key=value` / `%prod.key=value` **keys inside** a properties file.
Never create `application-%hsqldb.properties` (literal percent in the name) —
that is not a profile selector. Prefer collapsing Spring multi-DB profile
files into `%dev`/`%test`/`%prod` stanzas; MySQL gone or listed in
`migration/deferred-by-decision.txt`. `%prod` datasource values are
Secret/env-fed (`QUARKUS_DATASOURCE_*`) — never hardcode passwords (D1).

**O-GATEACHIEVE / N14 / D2:** factory keeps the Sonar **80%** new_coverage
bar. When preflight is RED on a coverage gap ≥15 points with no
issue/hotspot blockers, the supervisor **blocks ship** and pages the
operator instead of burning MiniMax fix seats.

**O-HEALTHROOT / O-CTXROOT / O-ACCEPTROOT:** preserve servlet
context-path as `quarkus.http.root-path=/…` (QuarkusTest RestAssured
expects this — do **not** switch tests/main to `quarkus.rest.path` alone
or you get 405/404). Pair with `quarkus.http.non-application-root-path=/q`
so probes stay at `/q/health*`. Ship acceptance may curl `/` or, when
root-path is set, `${root-path}/` for the index (supervisor O-ACCEPTROOT).
**O-ACCEPTPROBE:** log the URL that actually returned index 200
(`/` vs `${root-path}/`) — external `/` may still be 404.
Keep `src/test/resources` on `http.root-path` matching main.

**O-SEEDIMPORT:** when `acceptance.needsDatabase` (or the stamped
handler 404s on empty collections), load the legacy populate script as
`import.sql` (`quarkus.hibernate-orm.sql-load-script=import.sql`). An
empty table that returns HTTP 404 is not an acceptance pass. Always use
**explicit column lists** — Hibernate physical column order can differ
from legacy `INSERT … VALUES` (e.g. pets `owner_id` before `type_id`);
a mid-script FK error rolls back the whole load.

**Gate correction** (`/tmp/gate-violations.txt`): as described above —
small per-rule packets, consolidation for duplication, semantics
preserved, coverage held.

When the evidence shows `COVERAGE` lines (the gate can fail on new-code
coverage alone, with zero violations — cart run #2), the fix is REAL
unit tests for the least-covered classes listed:

- Mock EXTERNAL BOUNDARIES only (REST clients, remote services);
  internal collaborators and models stay real — a test that mocks the
  migrated classes asserts the mocks, not the migration.
- NEVER change an expected assertion value to make a test pass; legacy
  assertion values are the contract.
- Plain JUnit/Mockito suffices for models and services; `@QuarkusTest`
  only where CDI wiring is the subject.
- Near-identical case families become one `@ParameterizedTest`
  (java:S5976 fails the in-loop gate otherwise).

**Acceptance correction** (`/tmp/deploy-failure.txt`, task
`acceptance-deploy`): the pipeline is green but the demo acceptance is
unmet. The contract is: route `/` serves 200 (a minimal index page over
the app's API is enough — a UI waive in the plan is overridden here),
and the `acceptance.path` from migration.yaml returns 200 with a
**non-empty JSON array** for `acceptance.collection` (Coolstore default
`products`, or e.g. `{"vetList":[...]}` — O-ACCEPTGEN) fetched via the
live client named in `acceptance.service` / `acceptance.endpointEnv` —
never a bare status object, never canned domain data
(forbidden-fabrication class; run-4 false green). Keep
`quarkus.http.root-path` at its default:
relocating it moves `/q/health` and `/` and breaks both the boot check
and this acceptance.

**Mandatory checklist (V6 — all required, not optional):**

1. **Do not edit** `migration.yaml` `acceptance.path` (R1). Implement the
   stamped path; goalpost moves are rejected by the supervisor.
2. Acceptance handler must call the live client (`@RegisterRestClient` /
   `acceptance.service` or equivalent) and return the configured
   collection (R2 / O-ACCEPTGEN).
3. **No fail-open**: never `catch` → `Response.ok(...)` that forces HTTP
   200 with empty/canned success (R3).
4. Wire `acceptance.endpointEnv` (Coolstore: `CATALOG_ENDPOINT`) into
   `k8s/` Deployment `env` for the in-cluster URL (R5) —
   `application.properties` alone is not enough.
   **O-CATALOGDNS:** the host in that URL must resolve. If you use a short
   name (`http://catalog-service:8080`), co-deploy a `Service` (+ backing
   workload) named `catalog-service` under `k8s/` that serves the client's
   path (legacy Coolstore: `GET /api/products` → JSON product array). Do
   **not** point the catalog client at inventory (`/api/inventory`) — wrong
   path and shape. Preflight fails when the env host has no matching
   **Service** document (O-CATALOGSVC: a Deployment with the same name is
   not enough). A same-namespace stub that serves `/api/products` is a
   valid migration-general choice for a self-contained demo — record that
   trade-off in the quality gate; do not claim Coolstore inventory
   integration. Presence of the env *key* alone is a false green.
5. Narrow error mapping: do **not** leave `ExceptionMapper<Exception>`
   (it remaps framework 404 → 503). Map catalog/service failures only (R6).
6. Preflight enforces handler-before-deploy (R7): a Java `@Path` /
   `acceptanceCheck` for the stamped path must exist in `src/main` before
   push — ceremonial task cites are not enough.
7. **Root index:** ship acceptance curls `/` for HTTP 200. With
   `quarkus.rest.path=/api`, JAX-RS does **not** cover `/` — add
   `src/main/resources/META-INF/resources/index.html` (static).

Round budget is supervisor-enforced across all three classes. A final
rejection halts the run with the evidence preserved for the retro —
never bypass or water down the gate.

## O-GUARDMANIFEST — computable guard coverage (ARCH-B2)

`.hermes/harness/guard-manifest.md` (generated by `guard-manifest.sh`)
lists each guard with **stage × mechanism × verification** (L1 fixture /
L2 corpus / L3 live). Run `bash .hermes/harness/guard-manifest.sh --check`
after harness edits. Bank **retest-owed** rows should cite a Guard ID +
tier here instead of prose-only greps.

## O-EVIDLIVE — K-system evidence liveness at story-gate

Before `story-gate-passed` / acceptance success, the supervisor runs
`.hermes/harness/evidence-liveness.sh heartbeat <SID>` then `check <SID>`.
Each active K-system (K1, K2, K3, K9, K11) must have ≥1 ledger row in
`migration/evidence-liveness.md` for that story — or the gate REDs
(`evidlive-red`). Legitimate empties still emit an explicit none/checked
row (K9 `(none this story)`, K11 `rule:_none` when no Findings). K10 is
retired from this gate (optional ADVANCE-gated hints). Silent channels
with Findings but zero `k2:evidence` / `rule:` events are a hard RED.


## O-DTOCOV — OpenAPI DTO package vs Sonar new-code coverage

Harvested OpenAPI `**/dto/**` beans routinely trip Sonar new-code coverage,
CPD, and unused-import / regex rules (S1128/S6353). Scaffold default:
`sonar.exclusions` + `sonar.coverage.exclusions` + `sonar.cpd.exclusions` =
`**/dto/**`. Prefer that over inventing BaseDto hierarchies, ceremonial
getter tests, or hand-scrubbing generator imports mid-sfix. Do not weaken
the gate for non-DTO packages.

## O-ENTITYDSPROD — default datasource vs factory postgres URL

Once `@Entity` lands, package/verify needs a default-profile datasource
(O-ENTITYDS). Putting unprofiled `db-kind=h2` satisfies verify but breaks
factory deploy when the Deployment injects
`QUARKUS_DATASOURCE_JDBC_URL=jdbc:postgresql://…` — H2 driver rejects the URL
and readiness stays 503.

**Rule:** default (and prod) `quarkus.datasource.db-kind=postgresql` with a
placeholder JDBC URL; confine H2 to `%dev` / `%test` only. Never clear
deploy readiness with Flyway scaffolding or index.html theater.

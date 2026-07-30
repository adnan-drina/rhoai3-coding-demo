# M5 EVALUATE — final sensors and the factory gate

## Contents
- M5 evaluate — re-analysis, delta, final verify
- M5 ship — the supervised factory gate loop

## M5 evaluate — final sensors + ship

1. Re-analysis of the MIGRATED code:

```bash
kantra-ensure
/tmp/kantra/kantra analyze -i /projects/modernized -o /tmp/kantra-after \
  --target quarkus --json-output --overwrite || true
cp /tmp/kantra-after/output.json /projects/modernized/migration/mta-findings-after.json
```

Done means the baseline findings are resolved (or waived in the spec) —
not "the agent says done."

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
**non-empty JSON array of catalog products** (or `{"products":[...]}`
with a non-empty array) fetched via the live catalog client — never a
bare status object, never canned domain data (forbidden-fabrication
class; run-4 false green). Keep `quarkus.http.root-path` at its default:
relocating it moves `/q/health` and `/` and breaks both the boot check
and this acceptance.

**Mandatory checklist (V6 — all required, not optional):**

1. **Do not edit** `migration.yaml` `acceptance.path` (R1). Implement the
   stamped path; goalpost moves are rejected by the supervisor.
2. Acceptance handler must call the catalog (`@RegisterRestClient` /
   `CatalogService` or equivalent) and return real products (R2).
3. **No fail-open**: never `catch` → `Response.ok(...)` that forces HTTP
   200 with empty/canned success (R3).
4. Wire `CATALOG_ENDPOINT` into `k8s/` Deployment `env` for the in-cluster
   catalog URL (R5) — `application.properties` alone is not enough.
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


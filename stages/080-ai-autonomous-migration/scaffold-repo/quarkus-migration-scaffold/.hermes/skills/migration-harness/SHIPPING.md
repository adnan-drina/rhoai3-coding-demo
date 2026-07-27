# Phases D and E — final sensors and the factory gate

## Contents
- Phase D — re-analysis, delta, final verify
- Phase E — the supervised factory gate loop

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

2. Factory pre-flight green: `.hermes/harness/sensors.sh preflight` —
   isolated clean verify, the new-code sonar gate, and a prod-profile
   boot against the dev PostgreSQL (Flyway + Hibernate schema
   validation). Fix everything it reports BEFORE committing: the first
   push should be a formality the factory confirms.
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
and the `acceptance.path` from migration.yaml returns 200 with
non-empty JSON reporting REAL service state — never canned domain data
(that is the forbidden-fabrication class). Keep `quarkus.http.root-path`
at its default: relocating it moves `/q/health` and `/` and breaks both
the boot check and this acceptance.

Round budget is supervisor-enforced across all three classes. A final
rejection halts the run with the evidence preserved for the retro —
never bypass or water down the gate.


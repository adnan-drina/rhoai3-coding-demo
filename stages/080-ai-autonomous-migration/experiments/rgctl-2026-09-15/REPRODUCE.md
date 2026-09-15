# Reproducing this run

The migrated application lives **outside any repository checkout**, in its own git
repository:

```
path : /Users/adrina/Sandbox/rgctl-experiment/app
HEAD : b34e3eaf66bab3ed6fa3e155842e8992ba1bba4c
base : e1e11e4  (bootstrap of the frozen source, before any repair)
```

`evidence/this-run/app-commits.txt` lists the full series;
`evidence/this-run/app-diffstat.txt` is `git diff --stat e1e11e4 HEAD`.

## 0. Toolchain actually used

JDK 21.0.5 (Temurin), Maven 3.9.10, podman 5.6.1, oc 4.21.12, rgctl 0.4.12.
No Go, no Rust, no MTA CLI.

```bash
curl -fsSLO https://github.com/sshaaf/rgctl/releases/download/v0.4.12/rgctl-0.4.12-aarch64-apple-darwin.tar.gz
curl -fsSLO https://github.com/sshaaf/rgctl/releases/download/v0.4.12/SHA256SUMS.txt
shasum -a 256 -c SHA256SUMS.txt --ignore-missing     # 3e1ef9fd...16df
tar xzf rgctl-0.4.12-aarch64-apple-darwin.tar.gz
```

## 1. Database

PostgreSQL 16 locally under podman. **No cluster resource was created** and the
`rgctl-experiment` namespace was never needed.

```bash
podman machine start
podman run -d --name petclinic-pg -p 55432:5432 \
  -e POSTGRESQL_USER=petclinic -e POSTGRESQL_PASSWORD="$PGPW" \
  -e POSTGRESQL_DATABASE=petclinic -e POSTGRESQL_ADMIN_PASSWORD="$PGPW" \
  registry.redhat.io/rhel9/postgresql-16
```

`registry.redhat.io/rhel9/postgresql-16` was used, not the Docker Hub image, because
ADR-009 names Red Hat's supported PostgreSQL 16 and the registry was already
authenticated on this host. It runs 16.14. Note the Red Hat image takes
`POSTGRESQL_*` env names, not `POSTGRES_*`.

Credentials are passed by environment variable only and appear in no evidence file:

```bash
export PETCLINIC_DB_URL='jdbc:postgresql://localhost:55432/petclinic'
export PETCLINIC_DB_USER='petclinic'
export PETCLINIC_DB_PASSWORD='<...>'
export PETCLINIC_ADMIN_CREDENTIAL='<the seeded fixture credential>'
export PETCLINIC_INVALID_CREDENTIAL='<any other value>'
```

## 2. Inputs copied out of the official workspace, read-only

`oc exec ... -- sh -c 'cd /projects/modernized && tar czf - <paths>'` — note **`sh`,
not `bash -lc`**: the login shell emits a terminal escape sequence that corrupts the
first 38 bytes of a piped tar stream.

Copied: `.derived/frozen-input`, `decisions.yaml`, `.hermes/pins.json`,
`.hermes/planning`, `.mvn`, `evidence/{planning,frozen,producers,build,mta,structure,
verdicts}`, `verification/{source-oracles,scenarios,parity,loop/steps.json}`.
Nothing was written to the pod, no producer was run there, no process was started.

## 3. Bootstrap — reused, not rewritten

The destination baseline is the scaffold's own producer, unmodified:

```bash
python3 .hermes/skills/migration/bootstrap-destination/scripts/bootstrap-destination.py --root "$APP"
python3 .hermes/skills/migration/bootstrap-destination/scripts/check-datasource-decision.py "$APP"
```

Result: `OK: bootstrap (244 change(s))`, `PASS: datasource decision rendered`.
The freeze receipt's `analysis_copy` was repointed at the local frozen copy; the
source digest is unchanged.

## 4. Uncapped diagnostic census

`mvn compile` under-reports (see FINDINGS B-1). Use `tools/diag.sh`:

```bash
mvn -q dependency:build-classpath -Dmdep.outputFile=cp.txt -Dmdep.includeScope=compile
javac -proc:none -nowarn -d /tmp/out -Xmaxerrs 100000 --release 21 -cp "$(cat cp.txt)" @srcs.txt
```

`srcs.txt` must include `target/generated-sources` — the OpenAPI DTOs are generated at
build time and omitting them produces a phantom 17-diagnostic cascade.

## 5. Build, boot, verify

```bash
mvn -B package                                   # includes the retained ValidatorTests

bash .hermes/skills/gates/capture-source-oracles/scripts/reset-parity-db.sh --root "$APP"

QUARKUS_HTTP_PORT=8081 QUARKUS_PROFILE=prod,spring-data-jpa \
  java -jar target/quarkus-app/quarkus-run.jar

python3 .hermes/skills/planning/admit-migration-plan/scripts/admit-migration-plan.py --root "$APP"
python3 .hermes/skills/paved-road/paved-road-m4/scripts/run-parity.py \
        --root "$APP" --dest-url http://localhost:8081/petclinic
```

`admit-migration-plan.py` must be re-run after the bootstrap and any `decisions.yaml`
change, or every comparator refuses with "receipt not authoritative" before doing any
work.

## 6. Generated product tests (ADR-015)

```bash
python3 .hermes/skills/gates/generate-product-tests/scripts/generate-product-tests.py --root "$APP"
python3 .hermes/skills/gates/generate-product-tests/scripts/commit-generated-tests.py --root "$APP"

mvn -B -Pm4-parity -Dtest='*ParityTest' -DfailIfNoSpecifiedTests=false \
    -Dquarkus.test.profile=prod,spring-data-jpa \
    -Dpetclinic.security.enable=false test
```

Both overrides are required and neither is optional:

- `-Dquarkus.test.profile=prod,spring-data-jpa` — without it `@IfBuildProfile` vetoes
  all fifteen repository beans under `@QuarkusTest` and augmentation fails with 11
  unsatisfied dependencies.
- `-Dpetclinic.security.enable=false` — the **frozen source's own**
  `src/test/resources/application.properties` sets it to `true`, and under
  `@QuarkusTest` that file overrides the destination's configuration, so every
  generated case's reset probe answers 401. The generated manifest declares
  `security-mode disabled`; the run must pin the mode the manifest declares.

## 7. Security modes

One artifact, both modes, selected at run time:

```bash
PETCLINIC_SECURITY_ENABLE=false java -jar target/quarkus-app/quarkus-run.jar   # anonymous 200
PETCLINIC_SECURITY_ENABLE=true  java -jar target/quarkus-app/quarkus-run.jar   # anonymous 401, admin 200
```

## 8. rgctl policy

```bash
cd "$APP" && rgctl discover . --exclude ".derived,target,.hermes,verification,evidence" --with-cfg --with-harmonic
python3 policy/build-policy.py            # baseline only
python3 policy/build-policy.py --write    # baseline + policy.json
rgctl -r "$APP" -f json check --policy-file policy/policy.json
```

`build-policy.py --write` must be re-run after **every** `discover`: node UUIDs are
regenerated each time and a stale policy passes silently (POLICY.md section 4).

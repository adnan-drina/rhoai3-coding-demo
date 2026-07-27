#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Factory-parity sensors (improvement plan C1/D1).
#
# "Green in the workspace" must mean "green in the factory": every sensor
# here reproduces a pipeline stage locally so defects die at the task that
# introduces them, not in Phase E rounds.
#
#   sensors.sh seed        one-time per run: seed the isolated Maven repo
#   sensors.sh task        after every sub-fix: clean test, isolated repo
#   sensors.sh milestone   pom/config changes + every 3-4 tasks:
#                          clean verify (isolated) + new-code sonar check
#   sensors.sh preflight   Phase D exit: verify + sonar + container-profile
#                          boot against the dev PostgreSQL (schema drift)
#
# Exit 0 = green. Non-zero = red, with the failure summarized on stdout.
# Measured cost (spike S1): seed ~5-6 min once; +24 s per verify vs the
# shared repo — the price of proving pipeline-equivalent resolution.
# ---------------------------------------------------------------------------
set -uo pipefail
export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"
export PATH="${JAVA_HOME}/bin:${PATH}"
# SENSOR_ROOT override exists for the instrument test suite (X1), which
# runs the static checks against fixture trees.
cd "${SENSOR_ROOT:-/projects/modernized}"

M2_RUN="${M2_RUN:-/tmp/m2-run}"
MVN="mvn -q -Dmaven.repo.local=${M2_RUN}"
SONAR_GOAL="org.sonarsource.scanner.maven:sonar-maven-plugin:5.7.0.6970:sonar"
SONAR_HOST="${SONAR_HOST:-http://sonarqube.sonarqube.svc:9000}"
PROJECT_KEY="$(basename "$(git remote get-url origin 2>/dev/null || echo fixture)" .git)"
DEV_DB_URL="${DEV_DB_URL:-jdbc:postgresql://coolstore-postgres.${PROJECT_KEY}-dev.svc:5432/coolstore}"

fail() { echo "SENSOR RED ($1): $2"; exit 1; }

yaml_items() { # $1 = top-level key; prints its list items, section-bounded.
  # grep -A<N> overreads into the NEXT yaml section (X1 suite catch: a
  # forbidden: item was read as a preserve: item). Stop at the next
  # top-level key instead.
  awk -v k="^$1:" '$0 ~ k {f=1; next} /^[^ \t]/ {f=0} f' migration.yaml \
    | grep -E "^[[:space:]]*-" | sed -E 's/^[[:space:]]*-[[:space:]]*//; s/^"//; s/"$//'
}

seed() {
  [ -d "$M2_RUN" ] && { echo "isolated repo already seeded ($(du -sh "$M2_RUN" | cut -f1))"; return 0; }
  echo "seeding isolated Maven repo (one-time, ~5 min)..."
  $MVN clean verify > /tmp/sensor-seed.log 2>&1 \
    || fail seed "baseline build failed on the isolated repo — see /tmp/sensor-seed.log"
  echo "seeded: $(du -sh "$M2_RUN" | cut -f1)"
}

forbidden_patterns() {
  # migration.yaml forbidden: patterns that must never appear in src/main
  # (fabricated domain data disguised as fallbacks — observed twice).
  [ -f migration.yaml ] && grep -q "^forbidden:" migration.yaml || return 0
  yaml_items forbidden | while read -r pat; do
    [ -n "$pat" ] || continue
    if grep -rq "$pat" src/main 2>/dev/null; then
      echo "SENSOR RED (forbidden): pattern '$pat' found in src/main: $(grep -rl "$pat" src/main | head -2 | tr '\n' ' ')"
      exit 1
    fi
  done || exit 1
}

tree_hygiene() {
  # Shell-quoting accidents leave literal glob/space filenames that
  # compile silently and detonate at the factory (observed: empty
  # '*.java' files -> S1220 trio). Fail fast on illegal names.
  local bad
  bad=$(find src -name '*\**' -o -name '*"*"*' -o -name '* *' 2>/dev/null | head -5)
  [ -z "$bad" ] || fail hygiene "illegal filenames in tree: $bad"
}

task_sensor() {
  tree_hygiene
  wiring_invariants
  forbidden_patterns
  $MVN clean test > /tmp/sensor-task.log 2>&1 \
    || fail task "$(grep -E 'ERROR|FAIL' /tmp/sensor-task.log | head -5)"
  echo "task sensor GREEN (clean test, isolated repo)"
}

sonar_check() { # $1 = inloop|full  (default full)
  local mode="${1:-full}"
  if [ -z "${SONAR_TOKEN:-}" ]; then
    echo "WARN: SONAR_TOKEN not set — sonar check skipped (factory will judge)"
    return 0
  fi
  # In-loop: judge NEW VIOLATIONS only — coverage is inherently
  # unsatisfiable before the plan's test tasks run and would spam fix
  # sessions. The full gate (coverage included) applies at preflight.
  local gate_wait=true
  [ "$mode" = "inloop" ] && gate_wait=false
  $MVN $SONAR_GOAL -Dsonar.host.url="$SONAR_HOST" -Dsonar.token="$SONAR_TOKEN" \
      -Dsonar.projectKey="$PROJECT_KEY" -Dsonar.qualitygate.wait=$gate_wait \
      > /tmp/sensor-sonar.log 2>&1
  local rc=$?
  # Violation evidence comes from the single helper (audit consolidation).
  if [ "$mode" = "inloop" ]; then
    [ $rc -ne 0 ] && fail sonar "analysis submit failed — /tmp/sensor-sonar.log"
    # Wait for the server to PROCESS this scan before querying issues —
    # a fixed sleep races the compute engine and reports the PREVIOUS
    # analysis's issues (V3 S02: a clean tree went red on stale evidence).
    CE_TASK=$(grep -m1 "^ceTaskId=" target/sonar/report-task.txt 2>/dev/null | cut -d= -f2)
    if [ -n "$CE_TASK" ]; then
      for _ in $(seq 1 40); do
        ST=$(curl -sf "$SONAR_HOST/api/ce/task?id=$CE_TASK" 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['task']['status'])" 2>/dev/null)
        [ "$ST" = "SUCCESS" ] && break
        [ "$ST" = "FAILED" ] || [ "$ST" = "CANCELED" ] && fail sonar "server-side analysis $ST"
        sleep 3
      done
    else
      sleep 8
    fi
    local n
    n=$(python3 .hermes/harness/sonar-report.py "$SONAR_HOST" "$PROJECT_KEY" 2>/tmp/sonar-violations.txt || echo 0)
    if [ "${n:-0}" -gt 0 ]; then
      cat /tmp/sonar-violations.txt
      fail sonar "in-loop gate: ${n} new violations (list above)"
    fi
    echo "sonar check GREEN (in-loop: 0 new violations)"
    return 0
  fi
  if [ $rc -ne 0 ]; then
    python3 .hermes/harness/sonar-report.py "$SONAR_HOST" "$PROJECT_KEY" --coverage >/dev/null 2>/tmp/sonar-violations.txt
    cat /tmp/sonar-violations.txt
    fail sonar "quality gate red — violations above; full log /tmp/sensor-sonar.log"
  fi
  echo "sonar check GREEN (new-code gate)"
}

milestone_sensor() { # $1 = inloop|full (default inloop)
  # Harvest fidelity first (cheap, pure python): staged legacy classes
  # must survive into the destination modulo approved transforms
  # (V3 catch: a fix session silently rewrote a serialVersionUID).
  # FIDELITY_CHECK=off waives it for hardening stories (S03 lesson:
  # they deliberately depart from the staged legacy — the brief, not
  # staging, is their design authority). /tmp/fidelity-off is the
  # live-run bridge for an already-running supervisor (pause-flag
  # pattern; env cannot be injected into a running loop).
  if [ "${FIDELITY_CHECK:-on}" = "off" ] || [ -f /tmp/fidelity-off ]; then
    echo "fidelity check WAIVED (hardening story)"
  else
    python3 .hermes/harness/harvest-fidelity.py \
      || fail fidelity "harvested class drifted from staged legacy source (see FIDELITY lines)"
  fi
  $MVN clean verify > /tmp/sensor-milestone.log 2>&1 \
    || fail milestone "$(grep -E 'ERROR|FAIL' /tmp/sensor-milestone.log | head -5)"
  sonar_check "${1:-inloop}"
  echo "milestone sensor GREEN (clean verify + sonar[${1:-inloop}], isolated repo)"
}

boot_check() {
  # Prod-profile boot against the dev PostgreSQL: exercises Flyway +
  # Hibernate schema validation — the drift class no unit test catches.
  $MVN clean package -DskipTests > /tmp/sensor-package.log 2>&1 \
    || fail boot "package failed — /tmp/sensor-package.log"
  # DB env only when the app actually has a JDBC extension — a DB-less
  # migration (e.g. the cart service) boots plain.
  DB_ENV=()
  if grep -q "quarkus-jdbc" pom.xml 2>/dev/null; then
    DB_ENV=(QUARKUS_DATASOURCE_JDBC_URL="$DEV_DB_URL"
            QUARKUS_DATASOURCE_USERNAME="${DEV_DB_USER:-coolstore}"
            QUARKUS_DATASOURCE_PASSWORD="${DEV_DB_PASSWORD:-coolstore}")
  fi
  env "${DB_ENV[@]}" QUARKUS_HTTP_PORT=8099 \
    java -jar target/quarkus-app/quarkus-run.jar > /tmp/sensor-boot.log 2>&1 &
  local pid=$!
  local up=""
  for _ in $(seq 1 30); do
    sleep 2
    if curl -sf http://localhost:8099/q/health >/dev/null 2>&1; then up=yes; break; fi
    kill -0 $pid 2>/dev/null || break
  done
  kill $pid 2>/dev/null; wait $pid 2>/dev/null
  [ "$up" = "yes" ] || fail boot "$(grep -iE 'ERROR|Caused by|SchemaManagement|Migration' /tmp/sensor-boot.log | head -6)"
  echo "boot check GREEN (Flyway + schema validation against the dev DB)"
}

wiring_invariants() {
  # N3: pom rewrites twice stripped the coverage instrumentation — the
  # factory's coverage gate reads jacoco; losing the wiring reads as 0%.
  grep -q "jacoco-maven-plugin" pom.xml \
    || fail wiring "pom.xml lost the jacoco-maven-plugin (coverage gate will read 0%)"
  grep -q "sonar.coverage.jacoco.xmlReportPaths" pom.xml \
    || fail wiring "pom.xml lost sonar.coverage.jacoco.xmlReportPaths"
  # Cart run #2 factory failure: the factory's older Maven defaults to
  # maven-compiler-plugin 3.1, which predates <release> and compiles at
  # source 5. Local builds mask this (newer Maven). The plugin pin is a
  # scaffold-pom convention every migrated pom must keep.
  grep -A2 "maven-compiler-plugin" pom.xml | grep -q "<version>" \
    || fail wiring "pom.xml does not pin maven-compiler-plugin with a <version> (factory Maven defaults to 3.1 → 'Source option 5' failure)"
  # V3 two-run recurrence: injecting a @RegisterRestClient interface
  # without the @RestClient qualifier fails CDI resolution at build/boot
  # — invisible to plain unit tests.
  for iface in $(grep -rl "@RegisterRestClient" src/main 2>/dev/null | xargs -r grep -l "interface" | sed -E "s|.*/([A-Za-z0-9]+)\.java|\1|"); do
    # Only INJECTION POINTS need the qualifier (fields assigned from a
    # qualified constructor param are fine): a type usage within 4 lines
    # after an @Inject, with no @RestClient in that window, is the trap.
    grep -rn "$iface [a-zA-Z]" src/main --include="*.java" 2>/dev/null | grep -vE "interface $iface|import |class " | while read -r line; do
      f2=$(echo "$line" | cut -d: -f1); ln=$(echo "$line" | cut -d: -f2)
      start=$((ln>4 ? ln-4 : 1))
      window=$(sed -n "${start},${ln}p" "$f2")
      echo "$window" | grep -q "@Inject" || continue
      echo "$window" | grep -q "@RestClient" \
        || { echo "SENSOR RED (wiring): ${f2}:${ln} injects $iface without @RestClient qualifier (CDI UnsatisfiedResolution at boot)"; exit 1; }
    done || exit 1
  done
}

preserved_integrations() {
  # Story mode: a story that owns no preserve items runs with
  # PRESERVE_CHECK=off (the item arrives with its owning story; the
  # deploy-story/final preflight enforces it). Outer loop sets this from
  # roadmap ownership.
  [ "${PRESERVE_CHECK:-on}" = "off" ] && return 0
  # N2: every preserve: item in migration.yaml must survive into the
  # built configuration or source — an erased integration is a
  # functional regression no unit test catches.
  [ -f migration.yaml ] && grep -q "^preserve:" migration.yaml || return 0
  local item
  yaml_items preserve | while read -r item; do
    [ -n "$item" ] || continue
    grep -rq "$item" src/main pom.xml k8s/ 2>/dev/null \
      || { echo "SENSOR RED (preserve): preserved integration '$item' absent from src/main, pom.xml and k8s/"; exit 1; }
  done || exit 1
}

preflight() {
  wiring_invariants
  preserved_integrations
  milestone_sensor full
  boot_check
  echo "PREFLIGHT GREEN — the factory should confirm, not discover"
}

case "${1:-}" in
  seed)      seed;;
  task)      task_sensor;;
  milestone) milestone_sensor;;
  preflight) preflight;;
  # static: every check that needs no Maven/JVM — used by the X1
  # instrument test suite (tests/instruments.bats) against fixture trees.
  static)    tree_hygiene; forbidden_patterns; wiring_invariants; preserved_integrations; echo "STATIC CHECKS GREEN";;
  *) echo "usage: sensors.sh seed|task|milestone|preflight|static"; exit 2;;
esac

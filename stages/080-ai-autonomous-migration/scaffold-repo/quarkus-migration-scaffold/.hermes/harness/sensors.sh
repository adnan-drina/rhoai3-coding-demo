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
cd /projects/modernized

M2_RUN="${M2_RUN:-/tmp/m2-run}"
MVN="mvn -q -Dmaven.repo.local=${M2_RUN}"
SONAR_GOAL="org.sonarsource.scanner.maven:sonar-maven-plugin:5.7.0.6970:sonar"
SONAR_HOST="${SONAR_HOST:-http://sonarqube.sonarqube.svc:9000}"
PROJECT_KEY="$(basename "$(git remote get-url origin)" .git)"
DEV_DB_URL="${DEV_DB_URL:-jdbc:postgresql://coolstore-postgres.${PROJECT_KEY}-dev.svc:5432/coolstore}"

fail() { echo "SENSOR RED ($1): $2"; exit 1; }

seed() {
  [ -d "$M2_RUN" ] && { echo "isolated repo already seeded ($(du -sh "$M2_RUN" | cut -f1))"; return 0; }
  echo "seeding isolated Maven repo (one-time, ~5 min)..."
  $MVN clean verify > /tmp/sensor-seed.log 2>&1 \
    || fail seed "baseline build failed on the isolated repo — see /tmp/sensor-seed.log"
  echo "seeded: $(du -sh "$M2_RUN" | cut -f1)"
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
  $MVN clean test > /tmp/sensor-task.log 2>&1 \
    || fail task "$(grep -E 'ERROR|FAIL' /tmp/sensor-task.log | head -5)"
  echo "task sensor GREEN (clean test, isolated repo)"
}

sonar_check() {
  if [ -z "${SONAR_TOKEN:-}" ]; then
    echo "WARN: SONAR_TOKEN not set — sonar check skipped (factory will judge)"
    return 0
  fi
  $MVN $SONAR_GOAL -Dsonar.host.url="$SONAR_HOST" -Dsonar.token="$SONAR_TOKEN" \
      -Dsonar.projectKey="$PROJECT_KEY" -Dsonar.qualitygate.wait=true \
      > /tmp/sensor-sonar.log 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then
    python3 - "$SONAR_HOST" "$PROJECT_KEY" <<'PYEOF'
import json, sys, urllib.request, collections
base, key = sys.argv[1], sys.argv[2]
try:
    with urllib.request.urlopen(f"{base}/api/issues/search?componentKeys={key}&resolved=false&inNewCodePeriod=true&ps=100", timeout=30) as r:
        d = json.load(r)
    by = collections.defaultdict(list)
    for i in d.get("issues", []):
        by[i["rule"]].append(f"{i['component'].split(':')[-1]}:{i.get('line','?')}")
    print(f"new violations: {d.get('total', '?')}")
    for rule in sorted(by):
        print(f"{rule} ({len(by[rule])}): " + ", ".join(by[rule][:10]))
except Exception as e:
    print(f"(violation detail fetch failed: {e})")
PYEOF
    fail sonar "quality gate red — violations above; full log /tmp/sensor-sonar.log"
  fi
  echo "sonar check GREEN (new-code gate)"
}

milestone_sensor() {
  $MVN clean verify > /tmp/sensor-milestone.log 2>&1 \
    || fail milestone "$(grep -E 'ERROR|FAIL' /tmp/sensor-milestone.log | head -5)"
  sonar_check
  echo "milestone sensor GREEN (clean verify + sonar, isolated repo)"
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

preflight() {
  milestone_sensor
  boot_check
  echo "PREFLIGHT GREEN — the factory should confirm, not discover"
}

case "${1:-}" in
  seed)      seed;;
  task)      task_sensor;;
  milestone) milestone_sensor;;
  preflight) preflight;;
  *) echo "usage: sensors.sh seed|task|milestone|preflight"; exit 2;;
esac

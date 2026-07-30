#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Factory-parity sensors (improvement plan C1/D1).
#
# "Green in the workspace" must mean "green in the factory": every sensor
# here reproduces a pipeline stage locally so defects die at the task that
# introduces them, not in M5 ship rounds.
#
#   sensors.sh seed        one-time per run: seed the isolated Maven repo
#   sensors.sh task        after every sub-fix: clean test, isolated repo
#   sensors.sh milestone   pom/config changes + every 3-4 tasks:
#                          clean verify (isolated) + new-code sonar check
#   sensors.sh preflight   M5 evaluate exit: verify + sonar + container-profile
#                          boot against the dev PostgreSQL (schema drift)
#
# Exit 0 = green. Non-zero = red, with the failure summarized on stdout.
# Measured cost (spike S1): seed ~5-6 min once; +24 s per verify vs the
# shared repo — the price of proving pipeline-equivalent resolution.
# ---------------------------------------------------------------------------
set -uo pipefail
export JAVA_HOME="${JAVA_HOME_21:-${JAVA_HOME:-}}"
export PATH="${JAVA_HOME}/bin:${PATH}"
# Resolve the harness dir from this script's own location so helper
# scripts are found regardless of cwd (the instrument suite runs with
# SENSOR_ROOT pointing at a fixture tree that has no .hermes/harness).
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# SENSOR_ROOT override exists for the instrument test suite (X1), which
# runs the static checks against fixture trees.
cd "${SENSOR_ROOT:-/projects/modernized}"

M2_RUN="${M2_RUN:-/tmp/m2-run}"
MVN="mvn -q -Dmaven.repo.local=${M2_RUN}"
SONAR_GOAL="org.sonarsource.scanner.maven:sonar-maven-plugin:5.7.0.6970:sonar"
SONAR_HOST="${SONAR_HOST:-http://sonarqube.sonarqube.svc:9000}"
PROJECT_KEY="$(basename "$(git remote get-url origin 2>/dev/null || echo fixture)" .git)"
DEV_DB_URL="${DEV_DB_URL:-jdbc:postgresql://coolstore-postgres.${PROJECT_KEY}-dev.svc:5432/coolstore}"

# Self-correction guidance after the evidence line (Böckeler: sensors should
# inject how-to-fix context, not only the raw failure). First line always
# stays "SENSOR RED (<kind>): …" — instrument tests and correction packets
# match on that prefix / kind token.
guide_for() {
  case "$1" in
    forbidden)
      cat <<'EOF'
FIX: Delete the fabricated fallback from src/main (call the real integration
or fail closed). Do not edit migration.yaml forbidden: to waive. See
.hermes/skills/migration-harness/SHIPPING.md (fabrication class).
EOF
      ;;
    preserve)
      cat <<'EOF'
FIX: Restore the preserve: token into src/main, pom.xml, or k8s/ (env key,
config property, or client URL). An erased integration is a silent functional
regression. Check migration.yaml preserve: and PLANNING.md preserve coverage.
EOF
      ;;
    hygiene)
      cat <<'EOF'
FIX: Remove or rename illegal paths under src/ (literal glob chars, spaces,
or quoted junk filenames). Re-harvest/rewrite the intended .java files with
real names — empty '*.java' files compile locally and fail the factory.
EOF
      ;;
    package)
      cat <<'EOF'
FIX: A legacy-package file is under src/main. The migration RENAMES the legacy
package to the target package (migration.yaml legacyPackage -> targetPackage) —
it NEVER keeps or reverts a class into the legacy package. Move the file to the
target-package path and rewrite its `package`/imports to the target. Do NOT
"revert to the legacy package" to satisfy fidelity — that is the inversion.
The factory build/sonar gate compiles legacy-package code cleanly, so this
defect ships silently unless caught here.
EOF
      ;;
    wiring)
      cat <<'EOF'
FIX: Restore scaffold pom conventions (jacoco-maven-plugin,
sonar.coverage.jacoco.xmlReportPaths, pinned maven-compiler-plugin version)
and/or add @RestClient next to @Inject for @RegisterRestClient interfaces.
Losing wiring makes the factory coverage/compile gate fail while local builds
look green. Diff against the scaffold pom / SHIPPING.md gate notes.
EOF
      ;;
    fidelity)
      cat <<'EOF'
FIX: the destination class must MATCH its migration/staging source (approved
transforms only: package, whitespace, comments, annotations, diamond).
Re-harvest the drifted file from migration/staging, or REVERT a class that
was invented/fabricated instead of harvested. Do not hand-edit constants or
serialVersionUID to match. Never disable or waive this check.
EOF
      ;;
    task|milestone)
      cat <<'EOF'
FIX: Read the sensor log cited above. Prefer root-cause (missing harvest
dependency, wrong package, broken test) over silencing assertions. G-PLACE:
never "fix" with assertThat(true)/assertTrue(true) or Placeholder stubs —
restore real behavior assertions or defer the test task to the owning story.
Re-run .hermes/harness/sensors.sh task until GREEN, then commit. See EXECUTION.md.
EOF
      ;;
    sonar)
      cat <<'EOF'
FIX: Resolve each listed new-code violation (or coverage gap at preflight) with
real code/tests — never weaken assertions or drop jacoco wiring. In-loop gate
is violations-only; full coverage is preflight/factory. See SHIPPING.md.
EOF
      ;;
    boot)
      cat <<'EOF'
FIX: Read /tmp/sensor-boot.log (and /tmp/sensor-package.log if package failed).
Typical causes: schema drift, missing Flyway migration, CDI UnsatisfiedResolution
(@RestClient), bad datasource URL. Fix root cause, then sensors.sh preflight.
EOF
      ;;
    seed)
      cat <<'EOF'
FIX: Inspect /tmp/sensor-seed.log. The isolated Maven repo must build the
current tree once before task sensors are meaningful. Fix compile/test
failures, remove /tmp/m2-run if corrupt, re-run sensors.sh seed.
EOF
      ;;
    *)
      cat <<'EOF'
FIX: Diagnose from the evidence above; run the same sensors.sh mode until
GREEN; commit one sensor-fix commit. Do not push — the supervisor ships.
EOF
      ;;
  esac
}

fail() {
  echo "SENSOR RED ($1): $2"
  guide_for "$1"
  exit 1
}

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
  # Feed via a here-string, NOT `yaml_items | while … done || exit 1`: with
  # `set -o pipefail`, an empty `yaml_items` (or the loop reaching no `fail`)
  # made that pipe exit 1, so `|| exit 1` fired a SILENT false RED — the
  # empty-log rc=1 that stalled S03 (V5 run-4). A here-string runs the loop in
  # the current shell so `fail` propagates directly and empty input is inert.
  local _items; _items=$(yaml_items forbidden)
  while read -r pat; do
    [ -n "$pat" ] || continue
    if grep -rq "$pat" src/main 2>/dev/null; then
      fail forbidden "pattern '$pat' found in src/main: $(grep -rl "$pat" src/main | head -2 | tr '\n' ' ')"
    fi
  done <<< "$_items"
}

tree_hygiene() {
  # Shell-quoting accidents leave literal glob/space filenames that
  # compile silently and detonate at the factory (observed: empty
  # '*.java' files -> S1220 trio). Fail fast on illegal names.
  local bad
  bad=$(find src -name '*\**' -o -name '*"*"*' -o -name '* *' 2>/dev/null | head -5)
  [ -z "$bad" ] || fail hygiene "illegal filenames in tree: $bad"
}

package_scope() {
  # V5 finding #3: a legacy-package file under src/main is the package-map
  # INVERSION — a fix session that read "harvested into the wrong package"
  # and "reverted" a class into the legacy package instead of renaming it to
  # the target (V5 run-4: com.demo models rewritten into com.redhat.coolstore
  # under fidelity pressure). The factory build+sonar gate does NOT catch it
  # (legacy-package code compiles and passes sonar), so it would ship
  # silently. Catch it as a hard tree defect. migration/staging legitimately
  # holds legacy-package source — only src/main is checked.
  [ -f migration.yaml ] || return 0
  local leg tgt
  leg=$(grep -E "^[[:space:]]*legacyPackage:" migration.yaml 2>/dev/null | head -1 \
        | sed -E 's/.*legacyPackage:[[:space:]]*//; s/[[:space:]]*$//')
  tgt=$(grep -E "^[[:space:]]*targetPackage:" migration.yaml 2>/dev/null | head -1 \
        | sed -E 's/.*targetPackage:[[:space:]]*//; s/[[:space:]]*$//')
  [ -n "$leg" ] || return 0
  local legpath="src/main/java/$(echo "$leg" | tr '.' '/')"
  [ -d "$legpath" ] && fail package "legacy package '$leg' present under src/main ($legpath) — a harvest was placed/reverted into the legacy package instead of renamed to the target."
  # A directory literally named with dots (com.demo/, com.redhat.coolstore/)
  # is a mangled package PATH — the harvest joined the package with '.'
  # instead of '/'. It COMPILES (javac reads the package declaration, not the
  # file path) so no build/sonar gate catches it; a duplicate class next to
  # the correct path is caught by compile, but a lone mangled path ships
  # silently. Package-path segments are never dotted directory names.
  local dotdir
  dotdir=$(find src/main/java -type d -name '*.*' 2>/dev/null | head -3)
  [ -z "$dotdir" ] || fail package "dotted package directory under src/main (mangled package path — join segments with '/', not '.'): $(echo $dotdir | tr '\n' ' ')"
  if grep -rqE "^[[:space:]]*package[[:space:]]+$(echo "$leg" | sed 's/\./\\./g')\b" src/main/java 2>/dev/null; then
    fail package "a src/main file declares the legacy package '$leg' — rename it to the target package (never revert a harvest to the legacy package): $(grep -rlE "^[[:space:]]*package[[:space:]]+$(echo "$leg" | sed 's/\./\\./g')\b" src/main/java 2>/dev/null | head -2 | tr '\n' ' ')"
  fi
  # V6 abort: partial rename left com.demo.coolstore.* when migration.yaml
  # targetPackage is com.demo (replaced only the vendor prefix, or invented
  # targetPackage + last legacy segment). Correct map is full prefix replace:
  # com.redhat.coolstore.service → com.demo.service (never com.demo.coolstore).
  if [ -n "$tgt" ]; then
    local leg_last wrong wrongpath
    leg_last=${leg##*.}
    wrong="${tgt}.${leg_last}"
    wrongpath="src/main/java/$(echo "$wrong" | tr '.' '/')"
    if [ -d "$wrongpath" ] || [ -d "src/test/java/$(echo "$wrong" | tr '.' '/')" ]; then
      fail package "wrong rewrite prefix '$wrong' under src/ (V6) — full rename is '$leg' → '$tgt' (e.g. $leg.service → $tgt.service), never '$wrong'"
    fi
    if grep -rqE "^[[:space:]]*package[[:space:]]+$(echo "$wrong" | sed 's/\./\\./g')(\\.|;)" src/main/java src/test/java 2>/dev/null; then
      fail package "a src file declares wrong rewrite package '$wrong' — must be under '$tgt' via full legacy→target prefix replace: $(grep -rlE "^[[:space:]]*package[[:space:]]+$(echo "$wrong" | sed 's/\./\\./g')(\\.|;)" src/main/java src/test/java 2>/dev/null | head -2 | tr '\n' ' ')"
    fi
    # Every src/main declaration must live under targetPackage.
    local badpkg
    badpkg=$(grep -rhE "^[[:space:]]*package[[:space:]]+" src/main/java 2>/dev/null \
      | sed -E 's/^[[:space:]]*package[[:space:]]+//; s/[[:space:]]*;.*$//' \
      | grep -vE "^$(echo "$tgt" | sed 's/\./\\./g')(\.|$)" | head -3 || true)
    [ -z "$badpkg" ] || fail package "src/main package(s) outside targetPackage '$tgt': $badpkg"
  fi
}

# G-PLACE: ceremonial / placeholder tests that compile+pass without asserting
# product behavior (V8 S02 T-005: assertThat(true).isTrue() shipped as
# "verified working"). Cheap static scan — no Maven.
placeholder_tests() {
  [ -d src/test/java ] || return 0
  local hits
  hits=$(grep -RInE \
    --include='*.java' \
    'assertThat[[:space:]]*\([[:space:]]*true[[:space:]]*\)[[:space:]]*\.isTrue[[:space:]]*\(|assertThat[[:space:]]*\([[:space:]]*false[[:space:]]*\)[[:space:]]*\.isFalse[[:space:]]*\(|assertTrue[[:space:]]*\([[:space:]]*true[[:space:]]*\)|assertFalse[[:space:]]*\([[:space:]]*false[[:space:]]*\)|Placeholder until (service|implementation)|//[[:space:]]*Placeholder' \
    src/test/java 2>/dev/null | head -8 || true)
  [ -z "$hits" ] || fail task "placeholder/ceremonial test assertions (G-PLACE) — replace with real behavior checks or defer the task; hits: $(echo "$hits" | tr '\n' ' ')"
}

task_sensor() {
  tree_hygiene
  package_scope
  wiring_invariants
  forbidden_patterns
  placeholder_tests
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
  # Harvest fidelity first (cheap, pure python): staged legacy HARVEST
  # classes must survive into the destination modulo approved transforms
  # (V3 catch: a fix session silently rewrote a serialVersionUID).
  # REDESIGN classes are exempt by the discriminator, so fidelity is on
  # for every story. FIDELITY_CHECK=off is an OPERATOR-ONLY override (env,
  # set by the launcher) for a confirmed false positive — a worker session
  # CANNOT set the supervisor subprocess's env, so it cannot self-waive.
  # (The old /tmp/fidelity-off file bridge was removed: a session touched
  # it to escape a real fidelity RED — V5 T-004 fabricated-CatalogService.)
  placeholder_tests
  # G-AC3 (V9 S01): catch ceremonial acceptance surfaces in-loop, not only
  # at deploy preflight — status-map / "OK" endpoints must not land in S01.
  acceptance_ship_contract
  package_scope
  if [ "${FIDELITY_CHECK:-on}" = "off" ]; then
    echo "fidelity check WAIVED (operator override)"
  else
    python3 .hermes/harness/harvest-fidelity.py \
      || fail fidelity "harvested class drifted from staged legacy source (see FIDELITY lines)"
  fi
  $MVN clean verify > /tmp/sensor-milestone.log 2>&1 \
    || fail milestone "$(grep -E 'ERROR|FAIL' /tmp/sensor-milestone.log | head -5)"
  sonar_check "${1:-inloop}"
  # G-FID: fidelity GREEN ≠ scope clean — summarize later-story classes already in src/main
  if [ -n "${LATER_CLASSES:-}" ]; then
    local drift="" c
    for c in ${LATER_CLASSES}; do
      find src/main/java -type f -name "${c}.java" 2>/dev/null | grep -q . && drift="${drift} ${c}"
    done
    if [ -n "$drift" ]; then
      echo "WARN scope-drift (G-FID): later-story class(es) present under src/main while fidelity GREEN:${drift}"
      echo "WARN scope-drift (G-FID): later-story class(es) present under src/main while fidelity GREEN:${drift}" \
        >> /tmp/outer-loop.log 2>/dev/null || true
    fi
  fi
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
  # — invisible to plain unit tests. V6 P1.4: constructor parameters need
  # @RestClient even when @Inject is absent (Quarkus single-ctor injection).
  for iface in $(grep -rl "@RegisterRestClient" src/main 2>/dev/null | xargs -r grep -l "interface" | sed -E "s|.*/([A-Za-z0-9]+)\.java|\1|"); do
    # Capture injection points first, then loop via a here-string. The old
    # `grep … | while … done || exit 1` FALSE-FAILED with `set -o pipefail`
    # when the grep found NO injection points (an interface-only story where
    # the @RegisterRestClient client has no injector yet): empty grep → pipe
    # exit 1 → silent `exit 1` → empty-log false RED. That is the root of the
    # V5 run-4 S03 cascade (CatalogService present, no impl to inject it).
    local _points
    _points=$(grep -rn "$iface [a-zA-Z]" src/main --include="*.java" 2>/dev/null | grep -vE "interface $iface|import |class ")
    [ -n "$_points" ] || continue
    while read -r line; do
      [ -n "$line" ] || continue
      f2=$(echo "$line" | cut -d: -f1); ln=$(echo "$line" | cut -d: -f2)
      start=$((ln>4 ? ln-4 : 1))
      window=$(sed -n "${start},${ln}p" "$f2")
      echo "$window" | grep -q "@RestClient" && continue
      # Field injection: @Inject window without @RestClient
      if echo "$window" | grep -q "@Inject"; then
        fail wiring "${f2}:${ln} injects $iface without @RestClient qualifier (CDI UnsatisfiedResolution at boot)"
      fi
      # Constructor parameter: `Iface name,` / `Iface name)` — Quarkus injects
      # the sole ctor without requiring @Inject on the ctor (V6 P1.4).
      if echo "$line" | grep -qE "${iface}[[:space:]]+[a-zA-Z_][a-zA-Z0-9_]*[[:space:]]*[,)]"; then
        fail wiring "${f2}:${ln} constructs with $iface without @RestClient qualifier (CDI UnsatisfiedResolution at boot — V6 P1.4)"
      fi
    done <<< "$_points"
  done
  # Behavior-preserving target default (PROCESS-FIX #1): a CDI singleton
  # with shared mutable state must use a concurrent collection or confine
  # mutation to init — the S03 T-001 / V4 finding #1 thread-safety class,
  # caught deterministically in-loop instead of by post-ship review.
  OUT=$(python3 "$SELF_DIR/wiring-check.py" src/main/java 2>/dev/null) \
    || fail wiring "$(echo "$OUT" | head -3)"
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
  # Here-string, not `yaml_items | while … done || exit 1` (pipefail empty →
  # silent false RED — V5 run-4 empty-log class).
  local item _items; _items=$(yaml_items preserve)
  while read -r item; do
    [ -n "$item" ] || continue
    grep -rq "$item" src/main pom.xml k8s/ 2>/dev/null \
      || fail preserve "preserved integration '$item' absent from src/main, pom.xml and k8s/"
    # V6 R5: env-style preserve keys must appear under k8s/ when this is the
    # deploying story — application.properties alone shipped run-4 false green.
    if [ "${STORY_DEPLOY:-false}" = "true" ] && [[ "$item" =~ ^[A-Z][A-Z0-9_]+$ ]]; then
      grep -rq "$item" k8s/ 2>/dev/null \
        || fail preserve "preserved env '$item' absent from k8s/ (Deployment env required when deploy=true — V6 R5)"
    fi
  done <<< "$_items"
  # O-CATALOGDNS: key presence is not enough — http(s)://HOST values in k8s
  # env must have a same-namespace Service declared under k8s/ (or the host
  # is an FQDN with at least two dots, e.g. other-ns.svc.cluster.local).
  if [ "${STORY_DEPLOY:-false}" = "true" ]; then
    preserve_env_services_declared
  fi
}

# O-CATALOGDNS — Deployment env URLs must resolve to a declared Service (or FQDN).
# Same-document check only (O-CATALOGSVC): independent kind:/name: greps are
# forbidden — a Deployment named catalog-service must not GREEN without a Service.
preserve_env_services_declared() {
  [ -d k8s ] || return 0
  python3 - <<'PY' || fail preserve "k8s env points at an undeclared short-name Service (O-CATALOGDNS / O-CATALOGSVC)"
import re, pathlib, sys
hosts = set()
for p in pathlib.Path("k8s").rglob("*"):
    if not (p.is_file() and p.suffix in {".yaml", ".yml"}):
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r'value:\s*"?https?://([^/\s":]+)', text):
        hosts.add(m.group(1))
if not hosts:
    sys.exit(0)
docs = []
for p in pathlib.Path("k8s").rglob("*"):
    if p.is_file() and p.suffix in {".yaml", ".yml"}:
        docs.append(p.read_text(encoding="utf-8", errors="replace"))
blob = "\n---\n".join(docs)
service_names = set()
for doc in re.split(r"\n---\n", blob):
    if not re.search(r"(?m)^kind:\s*Service\s*$", doc):
        continue
    m = re.search(r"(?m)^metadata:\s*$[\s\S]*?^\s+name:\s*(\S+)\s*$", doc)
    if m:
        service_names.add(m.group(1))
bad = []
for host in sorted(hosts):
    # FQDN / dotted host: cross-ns or external — skip short-name Service check
    # (wrong-namespace FQDN is a known soft spot; do not pretend we validate DNS)
    if "." in host:
        continue
    if host not in service_names:
        bad.append(host)
if bad:
    print(
        "undeclared Service host(s): "
        + ", ".join(bad)
        + " — co-deploy Service or use resolvable FQDN",
        file=sys.stderr,
    )
    sys.exit(1)
sys.exit(0)
PY
}

# STORY_DEPLOY: static index at / (quarkus.rest.path=/api does not cover root).
root_index_present() {
  [ "${STORY_DEPLOY:-false}" = "true" ] || return 0
  [ -f src/main/resources/META-INF/resources/index.html ] \
    || fail acceptance "META-INF/resources/index.html missing — route / must return 200 (JAX-RS under quarkus.rest.path does not serve /)"
}

# V6 R3/R6 — ship-contract static checks (acceptance fail-open + mapper breadth).
acceptance_ship_contract() {
  [ -d src/main/java ] || return 0
  if grep -RIqE 'ExceptionMapper\s*<\s*Exception\s*>' src/main/java 2>/dev/null; then
    fail mapper "ExceptionMapper<Exception> is forbidden (remaps NotFound→503) — narrow to catalog/service failures (V6 R6)"
  fi
  # Fail-open heuristic: files that define an acceptance surface and catch→Response.ok
  # (run-4 cartCount:0 pattern). Package-agnostic.
  local f
  while IFS= read -r -d '' f; do
    grep -qE 'acceptanceCheck|acceptance-check|/acceptance' "$f" 2>/dev/null || continue
    grep -qE 'catch[[:space:]]*\(' "$f" || continue
    if awk '
      /acceptanceCheck|acceptance-check|\/acceptance/ { inacc=1 }
      inacc && /catch[[:space:]]*\(/ { incatch=1 }
      incatch && /Response\.ok/ { found=1; exit }
      END { exit found?0:1 }
    ' "$f"; then
      fail acceptance "fail-open acceptance handler in $f (catch→Response.ok) — V6 R3"
    fi
  done < <(find src/main/java -type f -name '*.java' -print0 2>/dev/null)
  # V6 abort: ceremonial status-map acceptance (service_interfaces_ready /
  # story-id Map) ships a 200 JSON object that is not a products[] catalog
  # proof — reject whenever such a marker appears on an acceptance surface.
  while IFS= read -r -d '' f; do
    grep -qE 'acceptanceCheck|acceptance-check|/acceptance' "$f" 2>/dev/null || continue
    if grep -qE 'service_interfaces_ready|interfaces_ready|"status"\s*,' "$f" 2>/dev/null; then
      fail acceptance "ceremonial status-map acceptance in $f (V6) — must return catalog products[] / live fetch, not a status Map"
    fi
  done < <(find src/main/java -type f -name '*.java' -print0 2>/dev/null)
  # G-OK (V7/V8): plain String / "OK" TEXT acceptance is not catalog proof.
  # Non-deploy stories otherwise story-gate-pass with return "OK".
  while IFS= read -r -d '' f; do
    grep -qE 'acceptanceCheck|acceptance-check|/acceptance' "$f" 2>/dev/null || continue
    if grep -qE 'return[[:space:]]+"OK"|return[[:space:]]+"ok"|public[[:space:]]+String[[:space:]]+[a-zA-Z0-9_]*\(' "$f" 2>/dev/null; then
      # Allow String only if the file also fetches a catalog / products list.
      if ! grep -qE 'products\(|CatalogService|CATALOG_ENDPOINT|List<.*Product' "$f" 2>/dev/null; then
        fail acceptance "ceremonial String/OK acceptance in $f (G-OK) — must return catalog products[] / live fetch, not TEXT \"OK\""
      fi
    fi
  done < <(find src/main/java -type f -name '*.java' -print0 2>/dev/null)
  # G-FAKE: MockCatalogService (or hardcoded List.of Product pairs) in src/main
  # is not a live catalog — ship must use @RestClient CatalogService.
  if find src/main/java -type f -name 'MockCatalogService.java' 2>/dev/null | grep -q .; then
    fail acceptance "MockCatalogService in src/main (G-FAKE) — use @RegisterRestClient CatalogService + CATALOG_ENDPOINT"
  fi
  while IFS= read -r -d '' f; do
    grep -qE 'acceptanceCheck|acceptance-check|/acceptance' "$f" 2>/dev/null || continue
    if grep -qE 'List\.of\s*\(\s*new[[:space:]]+Product|getMockProducts' "$f" 2>/dev/null; then
      fail acceptance "hardcoded mock products in acceptance surface $f (G-FAKE) — fetch live catalog"
    fi
  done < <(find src/main/java -type f -name '*.java' -print0 2>/dev/null)
}

# V6 R7 / P0c — before deploy, the stamped acceptance.path must have a Java
# handler (full path, leaf @Path, or acceptanceCheck method). Plan-lint alone
# only requires the path string in tasks.md; this catches ceremonial tasks.
acceptance_path_handler() {
  [ "${STORY_DEPLOY:-false}" = "true" ] || return 0
  [ -f migration.yaml ] || return 0
  [ -d src/main/java ] || fail acceptance "STORY_DEPLOY=true but src/main/java is absent — cannot serve acceptance.path"
  local acc_path leaf
  acc_path=$(python3 -c "
import re,sys
try: my=open('migration.yaml').read()
except FileNotFoundError: sys.exit(0)
m=re.search(r'^acceptance:\s*\n(?:[ \t]*#.*\n|[ \t]*\n)*[ \t]*path:\s*(\S+)', my, re.M)
print(m.group(1) if m else '')
" 2>/dev/null)
  [ -n "$acc_path" ] || return 0
  leaf="${acc_path##*/}"
  if grep -RIqF --include='*.java' "$acc_path" src/main/java 2>/dev/null; then
    return 0
  fi
  if [ -n "$leaf" ] && grep -RIqE --include='*.java' \
      "@Path\\(\"${leaf}\"|@Path\\('/${leaf}'|acceptanceCheck|acceptance-check" \
      src/main/java 2>/dev/null; then
    return 0
  fi
  fail acceptance "acceptance.path '${acc_path}' has no Java @Path/handler in src/main (V6 R7 handler-before-deploy) — add the resource method before ship"
}

preflight() {
  wiring_invariants
  preserved_integrations
  acceptance_ship_contract
  acceptance_path_handler
  root_index_present
  milestone_sensor full
  boot_check
  echo "PREFLIGHT GREEN — the factory should confirm, not discover"
}

fidelity_check() {
  # Standalone harvest-fidelity (the cheap dimension-specific recheck for a
  # fidelity-triggered sfix — pure python, no Maven).
  if [ "${FIDELITY_CHECK:-on}" = "off" ]; then
    echo "fidelity check WAIVED"; return 0
  fi
  python3 .hermes/harness/harvest-fidelity.py \
    || fail fidelity "harvested class drifted from staged legacy source (see FIDELITY lines)"
  echo "fidelity check GREEN"
}

sonar_only() {
  # Cheap dimension-specific recheck for a sonar-triggered sfix (V4 finding
  # #1: fix loops ran full `mvn clean verify` per iteration, ~5100s of the
  # run). Assumes compile/test already green — verify that with `task`
  # separately if unsure. Compiles test-classes only (sonar needs them) and
  # runs the new-code gate, skipping the full verify.
  $MVN test-compile > /tmp/sensor-sonar.log 2>&1 \
    || fail sonar "test-compile failed before sonar — /tmp/sensor-sonar.log"
  sonar_check inloop
  echo "sonar-only check GREEN (no full verify)"
}

case "${1:-}" in
  seed)      seed;;
  task)      task_sensor;;
  milestone)
    # O-SFIXLOOP: sensor-fix sessions must use cheap dimension checks.
    # MiniMax ignored prompt-only guidance (V9 S03 T-008: 5× milestone).
    if [ -f /tmp/sensor-fix-mode ] || [ "${SENSOR_FIX_MODE:-}" = "1" ]; then
      echo "REFUSED (O-SFIXLOOP): sensor-fix mode — use .hermes/harness/sensors.sh sonar|task|fidelity|package (not milestone)"
      exit 2
    fi
    milestone_sensor
    ;;
  sonar)     sonar_only;;
  fidelity)  fidelity_check;;
  preflight) preflight;;
  # static: every check that needs no Maven/JVM — used by the X1
  # instrument test suite (tests/instruments.bats) against fixture trees.
  static)    tree_hygiene; package_scope; forbidden_patterns; placeholder_tests; wiring_invariants; preserved_integrations; acceptance_ship_contract; acceptance_path_handler; root_index_present; echo "STATIC CHECKS GREEN";;
  package)   package_scope; echo "PACKAGE SCOPE GREEN";;
  *) echo "usage: sensors.sh seed|task|milestone|sonar|fidelity|preflight|package|static"; exit 2;;
esac

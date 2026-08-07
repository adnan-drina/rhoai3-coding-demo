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
# R-83 P2 / O-DEVDBURL: default DEV_DB_URL from migration.yaml acceptance.dbService
# / dbName (omit → ${PROJECT_KEY}-postgres / ${PROJECT_KEY}), not a Coolstore
# service or database name. Env DEV_DB_URL still wins when already set.
eval "$(python3 "$SELF_DIR/acceptance_config.py" --yaml migration.yaml --export-shell 2>/dev/null)" || true
DB_SERVICE="${ACC_DB_SERVICE:-${PROJECT_KEY}-postgres}"
DB_NAME="${ACC_DB_NAME:-${PROJECT_KEY}}"
DEV_DB_URL="${DEV_DB_URL:-jdbc:postgresql://${DB_SERVICE}.${PROJECT_KEY}-dev.svc:5432/${DB_NAME}}"

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
    # O-CONFIGFIXMODE / W4-677 §3.3: mode-2 drift must NEVER get mode-1
    # "restore into src/main" guidance (that produced MiniMax e0c82e9).
    configderived)
      cat <<'EOF'
FIX: Declare the transform in migration.yaml configTransforms: (from / to /
optional valueMap + reason). Do NOT re-introduce spring.* or server.* keys
into Quarkus application.properties, and do NOT invent valueTransforms: or
preserve: arrow strings — the gate only reads configTransforms:. See
.hermes/skills/migration-harness/SHIPPING.md (O-CONFIGDERIVED / O-CONFIGNOSPRING).
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
FIX: O-FIDELITYPORT — acceptance regime follows task **Port**:
  Port=rename (default): destination must MATCH migration/staging (approved
    transforms only: package, whitespace, comments, annotations, diamond,
    PropertyComparator→JDK sort). O-FIDELITYSORT: keep ArrayList+List.sort —
    not stream().sorted(); never re-harvest org.springframework.beans.support.*
    (O-SFIXNOSPRING). Evidence: FIDELITY: lines in /tmp/sensor-fidelity.log.
  Port=reimplement: byte-match harvest fidelity is NOT the gate — preserve
    public method signatures (redesign-sig / SIG: lines). Apply the API mapping
    table; do not transliterate Spring imports to green-wash.
Never disable or waive this check.
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
    findings)
      cat <<'EOF'
FIX: Convert or remove surviving in-scope MTA incidents (FINDINGS: lines).
Re-run .hermes/harness/sensors.sh findings (or milestone). scaffold-presatisfied
rules are already excluded (K5/K6).
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

# O-ADR46-S1: migration/staging must match capture-time tree hash (W4-709).
staging_immutable_check() {
  [ -f "$SELF_DIR/staging_immutable.py" ] || return 0
  [ -d migration/staging ] || return 0
  local out
  out=$(python3 "$SELF_DIR/staging_immutable.py" check 2>&1) || {
    echo "$out"
    fail hygiene "O-ADR46-S1 staging immutable RED — fidelity baseline moved (see STAGING_IMMUTABLE:)"
  }
  echo "$out"
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

# O-SHIPASSERTWEAK: refuse characterization-drop of unmodifiable-collection
# contracts (S5778 dodge via rename + soft asserts, or catch(Exception)
# "expected"). Migration-general — any Spring→Quarkus specimen.
ship_assert_weaken() {
  [ -d src/test/java ] || return 0
  local hits
  hits=$(grep -RInE --include='*.java' \
    'returnsListWithExpectedBehavior' \
    src/test/java 2>/dev/null | head -8 || true)
  [ -z "$hits" ] || fail task "characterization assert weaken (O-SHIPASSERTWEAK) — restore typed assertThrows(UnsupportedOperationException) for unmodifiable getters; do not rename *_returnsUnmodifiable* → *ListWithExpectedBehavior; hits: $(echo "$hits" | tr '\n' ' ')"
  hits=$(grep -RInE --include='*.java' \
    'catch[[:space:]]*\([[:space:]]*Exception[[:space:]]+[A-Za-z_][A-Za-z0-9_]*[[:space:]]*\)' \
    src/test/java 2>/dev/null | grep -iE 'expected|/\*|//' | head -8 || true)
  [ -z "$hits" ] || fail task "broad catch(Exception) expected (O-SHIPASSERTWEAK) — use assertThrows(specific); hits: $(echo "$hits" | tr '\n' ' ')"
}

# O-RESTGUIDE / O-RESTJSON (Poll 53): EXECUTION prose failed to transfer —
# reject root-level RestAssured find { } (must be under collection property).
restassured_contract() {
  [ -d src/test/java ] || return 0
  local hits
  hits=$(grep -RInE --include='*.java' \
    '\.body\([[:space:]]*["'"'"']find[[:space:]]*\{' \
    src/test/java 2>/dev/null | head -8 || true)
  [ -z "$hits" ] || fail task "RestAssured root-level find{} (O-RESTJSON/O-RESTGUIDE) — use collectionProperty.find { … }; hits: $(echo "$hits" | tr '\n' ' ')"
  # O-RESTEMPTY: empty pathParam + statusCode(400) is a JAX-RS routing myth.
  hits=$(grep -RInE --include='*.java' \
    'pathParam\([^)]*""[^)]*\)' \
    src/test/java 2>/dev/null | grep -E 'statusCode[[:space:]]*\([[:space:]]*400|400[[:space:]]*\)' | head -8 || true)
  # Also catch nearby .then().statusCode(400) after empty pathParam in same method — crude: same file lines with both.
  if [ -z "$hits" ]; then
    while IFS= read -r -d '' f; do
      if grep -qE 'pathParam\([^)]*""[^)]*\)' "$f" 2>/dev/null \
        && grep -qE 'statusCode[[:space:]]*\([[:space:]]*400' "$f" 2>/dev/null; then
        hits="$f: empty pathParam with statusCode(400)"
        break
      fi
    done < <(find src/test/java -type f -name '*.java' -print0 2>/dev/null)
  fi
  [ -z "$hits" ] || fail task "RestAssured empty pathParam→400 myth (O-RESTEMPTY) — use non-empty invalid ids or query/form validation; hits: $(echo "$hits" | tr '\n' ' ')"
  # O-TESTISO: multi-test *Endpoint* characterization suites need isolation
  # (scoped to Endpoint*Test so platform smoke suites are not false-REDs).
  local f n_tests
  while IFS= read -r -d '' f; do
    grep -qE '@QuarkusTest' "$f" 2>/dev/null || continue
    grep -qE 'RestAssured|\.given\(\)' "$f" 2>/dev/null || continue
    # O-SFIXCOUNT: @ParameterizedTest (+ @CsvSource rows) count as cases —
    # do not treat S5976 parameterization as suite thinning / single-test.
    n_tests=$(python3 -c "
import re, sys
t = open(sys.argv[1], encoding='utf-8', errors='replace').read()
n = len(re.findall(r'(?m)^\\s*@Test\\b', t))
n += len(re.findall(r'(?m)^\\s*@ParameterizedTest\\b', t))
for m in re.finditer(r'@CsvSource\\s*\\(\\s*\\{([^}]*)\\}', t, re.S):
    rows = re.findall(r'\"[^\"]*\"|\\'[^\\']*\\'', m.group(1))
    if len(rows) > 1:
        n += len(rows) - 1  # method already counted once via ParameterizedTest
print(n)
" "$f" 2>/dev/null || grep -cE '^[[:space:]]*@(Test|ParameterizedTest)\b' "$f" 2>/dev/null || echo 0)
    [ "${n_tests:-0}" -ge 2 ] || continue
    if ! grep -qE '@BeforeEach|UUID\.randomUUID|System\.nanoTime' "$f" 2>/dev/null; then
      fail task "RestAssured suite lacks isolation (O-TESTISO/O-RESTGUIDE) in $f — use @BeforeEach clear or UUID/nanoTime unique resource id per test"
    fi
  done < <(find src/test/java -type f -name '*Endpoint*Test.java' -print0 2>/dev/null)
}

redesign_sig_check() {
  python3 "$SELF_DIR/redesign-sig.py" \
    || fail task "redesign public method set drifted from staging (O-REDESIGNSIG/O-IFACERENAME) — keep legacy method names"
}

# O-FIDELITYPORT: Port=rename → harvest byte-match; Port=reimplement →
# behavioural/signature contract (redesign-sig --mode=reimpl). Migration-
# general — reads **Port** from CURRENT_TASK in tasks.md only.
task_port_mode() {
  local tid="${CURRENT_TASK:-}" tasks=""
  tasks="${STORY_TASKS:-${TASKS_FILE:-}}"
  if [ -z "$tasks" ] || [ ! -f "$tasks" ]; then
    tasks=$(ls specs/*/tasks.md 2>/dev/null | head -1)
  fi
  [ -n "$tid" ] && [ -n "$tasks" ] && [ -f "$tasks" ] || { echo ""; return 0; }
  PYTHONPATH="$SELF_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 - "$tasks" "$tid" <<'PY'
import re, sys
from task_contract import task_heading_parts  # O-T6dTCHEADING / step 1 SoT
path, tid = sys.argv[1], sys.argv[2]
text = open(path, encoding="utf-8", errors="replace").read()
_title, body = task_heading_parts(text, tid)
pm = re.search(
    r"(?im)^\*\*Port\*\*\s*:?\s*(rename|reimplement)\b"
    r"|^\*\*Port\s*:\s*(rename|reimplement)\*\*"
    r"|^Port\s*:\s*(rename|reimplement)\b",
    body,
)
if not pm:
    print("")
    raise SystemExit(0)
print(next(g for g in pm.groups() if g).lower())
PY
}

# Run the Port-scoped fidelity dimension into /tmp/sensor-fidelity.log.
# Exit 0 GREEN, 1 RED (caller fails the sensor).
run_port_scoped_fidelity() {
  local port
  port="$(task_port_mode)"
  if [ "$port" = "reimplement" ]; then
    {
      echo "O-FIDELITYPORT: Port=reimplement — harvest byte-match SKIPPED; using redesign-sig behavioural/signature contract"
      python3 "$SELF_DIR/redesign-sig.py" --mode=reimpl
    } > /tmp/sensor-fidelity.log 2>&1
    return $?
  fi
  # Port=rename or undeclared (harvest default): byte-match harvest fidelity.
  if [ -n "$port" ]; then
    {
      echo "O-FIDELITYPORT: Port=${port} — harvest byte-match fidelity"
      python3 "$SELF_DIR/harvest-fidelity.py"
    } > /tmp/sensor-fidelity.log 2>&1
    return $?
  fi
  python3 "$SELF_DIR/harvest-fidelity.py" > /tmp/sensor-fidelity.log 2>&1
}

# O-WIREUP (W3-141): attachment/reachability, not just method-name shape.
wireup_check() {
  [ -f "$SELF_DIR/wireup-check.py" ] || return 0
  OUT=$(python3 "$SELF_DIR/wireup-check.py" 2>/dev/null) \
    || fail task "$(echo "$OUT" | head -3)"
}

# O-CDIPARTIAL / O-JDBCHARVESTAPI / O-SPRINGRESIDUE: CDI stamp without
# Inject, Spring JDBC APIs, or any org.springframework under src/main —
# refuse before mvn (cheap).
cdi_partial_check() {
  [ -f "$SELF_DIR/cdi-partial-check.py" ] || return 0
  OUT=$(python3 "$SELF_DIR/cdi-partial-check.py" 2>/dev/null) \
    || fail task "$(echo "$OUT" | head -5) — finish Autowired→Inject; org.springframework under src/main/java must be 0 (Agroal/java.sql or EntityManager; exact DAO exception map — never invent *PersistenceException under spring.*); never tip-accept partial CDI / spring residue"
}

# O-TREEFIXSTUB: comment-only / REMOVED husks under src/main are not a fix —
# tree-fix must implement Agroal/java.sql (or O-NULLACTION), never stub-nuke.
tree_fix_stub_check() {
  [ -f "$SELF_DIR/tree-fix-stub-check.py" ] || return 0
  OUT=$(python3 "$SELF_DIR/tree-fix-stub-check.py" 2>/dev/null) \
    || fail task "$(echo "$OUT" | head -5) — O-TREEFIXSTUB: restore real types (Agroal/java.sql full API) or O-NULLACTION; never REMOVED/comment stubs"
}

# O-SDJPAHARVEST / O-SDJPAHARVESTONLY: Spring Data → Panache must convert
# after harvest (no spring-data residue), keep domain-repo extends, no
# orphan @NamedQuery on repo ifaces, no hollow finders, harvest Override Impls.
sdjpa_harvest_check() {
  [ -f "$SELF_DIR/sdjpa-harvest-check.py" ] || return 0
  OUT=$(python3 "$SELF_DIR/sdjpa-harvest-check.py" 2>/dev/null) \
    || fail task "$(echo "$OUT" | head -5) — O-SDJPAHARVEST/O-SDJPAHARVESTONLY: convert after harvest (Panache + no org.springframework.data); preserve domain-repo extends + Panache query bodies; harvest Override *Impl; no hollow finders / orphan NamedQuery"
}

# O-SECAUTHTEST (W3-142): if RolesAllowed + security.enable exist, require a
# test that asserts 401/403 (security-enabled path must be exercised).
security_auth_test_contract() {
  local props="src/main/resources/application.properties"
  [ -f "$props" ] || return 0
  grep -qE '\.security\.enable=' "$props" 2>/dev/null || return 0
  grep -Rql '@RolesAllowed' src/main/java --include='*.java' 2>/dev/null || return 0
  if ! grep -RqlE '401|403|Unauthorized|Forbidden|Status\.UNAUTHORIZED|Status\.FORBIDDEN' \
       src/test/java --include='*.java' 2>/dev/null; then
    fail task "O-SECAUTHTEST — @RolesAllowed + security.enable present but no test asserts 401/403 (use @TestProfile / configOverrides)"
  fi
}

task_sensor() {
  tree_hygiene
  staging_immutable_check
  package_scope
  wiring_invariants
  forbidden_patterns
  placeholder_tests
  ship_assert_weaken
  restassured_contract
  redesign_sig_check
  wireup_check
  cdi_partial_check
  tree_fix_stub_check
  sdjpa_harvest_check
  security_auth_test_contract
  # G-AC3 / O-ACCEPTREC (Poll 50): ceremonial acceptance must fail on the
  # per-task sensor, not only at milestone/preflight/ship — T-006 record DTO
  # otherwise lands GREEN via task-only post-commit verify.
  acceptance_ship_contract
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
  # O-SONAR401: invalid/expired token must not look like a code-violation RED
  # that burns Qwen/MiniMax sfix (S01 T-002: HTTP 401 on analysis/version).
  if [ $rc -ne 0 ] && grep -qE 'HTTP 401|401 Unauthorized|Not authorized|check the property sonar\.token' /tmp/sensor-sonar.log; then
    fail sonar "O-SONAR401: Sonar auth failed (401) — refresh SONAR_TOKEN; not a code sfix"
  fi
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
    # O-SONAROPAQUE: report.py emits QUALITYGATE/HOTSPOTS/issues/coverage —
    # not violations-only (M5 ship thrashed on empty issues while hotspot %).
    python3 .hermes/harness/sonar-report.py "$SONAR_HOST" "$PROJECT_KEY" --coverage >/dev/null 2>/tmp/sonar-violations.txt
    cat /tmp/sonar-violations.txt
    fail sonar "quality gate red — conditions above; full log /tmp/sensor-sonar.log"
  fi
  echo "sonar check GREEN (new-code gate)"
}

# O-K5MILESCOPE: in-loop milestone checks Findings only for tasks already
# committed (T-NNN: tips since RUN_BASE). Later pom/metrics/native rules
# must not RED early harvest tasks (migration-general; v3 S01 T-001).
# O-K5WAIVELEAK: empty completed-task Findings must short-circuit findings_sensor
# — do NOT fall through to PLAN_SCOPE / --scope-all (bash ${VAR:-alt} treats
# empty FINDINGS_SCOPE as unset; v3 S02 T-007 false RED on metrics-0200).
_k5_milestone_scope_inloop() {
  unset FINDINGS_K5_WAIVED
  [ -n "${FINDINGS_SCOPE:-}" ] && return 0
  [ -f "$SELF_DIR/findings-milestone-scope.py" ] || return 0
  local tf="${STORY_TASKS:-${TASKS_FILE:-}}"
  [ -n "$tf" ] && [ -f "$tf" ] || tf=$(ls specs/*/tasks.md 2>/dev/null | head -1)
  [ -n "$tf" ] && [ -f "$tf" ] || return 0
  local scoped n
  scoped=$(FINDINGS_MILESTONE_SCOPE_ROOT="$PWD" python3 "$SELF_DIR/findings-milestone-scope.py" \
    "$tf" "${RUN_BASE:-HEAD}" 2>/dev/null) || scoped=""
  if [ -n "$scoped" ]; then
    FINDINGS_SCOPE="$scoped"
    export FINDINGS_SCOPE
    unset FINDINGS_K5_WAIVED
    n=$(echo "$scoped" | tr ',' '\n' | grep -c . || true)
    echo "findings in-loop scope: ${n} rule(s) from completed tasks (O-K5MILESCOPE)"
  else
    FINDINGS_SCOPE=""
    export FINDINGS_SCOPE
    FINDINGS_K5_WAIVED=1
    export FINDINGS_K5_WAIVED
    echo "findings in-loop scope: none — K5 waived for completed tasks without Findings (O-K5MILESCOPE)"
  fi
}

# O-QJACOCO — also exposed as `sensors.sh qjacoco` for behavioural instruments.
qjacoco_check() {
  if [ -s target/jacoco-report/jacoco.xml ]; then
    echo "qjacoco check GREEN"
    return 0
  fi
  # O-M5SHIPHARVEST / O-QJACOCONOTEST: platform stories (deploy=false, no
  # @QuarkusTest yet) cannot produce quarkus-jacoco.xml — hard-failing here
  # sent MiniMax ship preflight-fix into full staging harvest (Wave2 S01).
  # Skip until at least one @QuarkusTest exists under src/test.
  if ! grep -RqlE '@QuarkusTest' src/test/java 2>/dev/null; then
    echo "qjacoco check SKIP (O-QJACOCONOTEST: no @QuarkusTest yet — not a harvest signal)"
    return 0
  fi
  fail coverage "O-QJACOCO: quarkus-jacoco report missing (target/jacoco-report/jacoco.xml) — coverage number is not trustworthy; do not chase Sonar new_coverage until @QuarkusTest instrumentation lands after mvn verify"
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
  # it to escape a real fidelity RED — V5 T-004 fabricated client.)  # ALLOWED: coolstore-default-fallback (historical note)
  staging_immutable_check
  placeholder_tests
  ship_assert_weaken
  # G-AC3 (V9 S01): catch ceremonial acceptance surfaces in-loop, not only
  # at deploy preflight — status-map / "OK" endpoints must not land in S01.
  acceptance_ship_contract
  package_scope
  # O-HTTPPORT / O-GENSEED: milestone does not run full wiring — still catch
  # deploy-contract breaks that task-sensor would see on other paths.
  http_port_deploy_contract
  gen_seed_contract
  pct_file_contract
  if [ "${FIDELITY_CHECK:-on}" = "off" ]; then
    echo "fidelity check WAIVED (operator override)"
  else
    # O-SFIXHINTFIDELITY + O-FIDELITYPORT: Port=rename → harvest-fidelity;
    # Port=reimplement → redesign-sig (byte-match unsatisfiable on API swap).
    if ! run_port_scoped_fidelity; then
      cat /tmp/sensor-fidelity.log
      {
        echo "SENSOR RED:fidelity (HARVEST FIDELITY / O-FIDELITYPORT — primary sfix dimension)"
        cat /tmp/sensor-fidelity.log
      } > /tmp/sensor-milestone.log
      printf '%s\n' fidelity > /tmp/sensor-fix-dim
      fail fidelity "Port-scoped fidelity RED (see FIDELITY:/SIG: lines / /tmp/sensor-fidelity.log) — Port=rename=byte-match; Port=reimplement=public signatures"
    fi
    cat /tmp/sensor-fidelity.log
    rm -f /tmp/sensor-fix-dim
  fi
  # SENSOR_SKIP_MVN=1 — instrument-only (O-INSTQUAL / O-QJACOCO fixture).
  if [ "${SENSOR_SKIP_MVN:-}" = "1" ]; then
    echo "milestone mvn WAIVED (SENSOR_SKIP_MVN=1)"
  else
    $MVN clean verify > /tmp/sensor-milestone.log 2>&1 \
      || fail milestone "$(grep -E 'ERROR|FAIL' /tmp/sensor-milestone.log | head -5)"
  fi
  # O-QJACOCO (Poll 55): Sonar new_coverage is untrustworthy when the
  # @QuarkusTest jacoco report is missing — CartEndpoint can be 0% while
  # CartEndpointTest is GREEN. Full/preflight must hard-fail before ship
  # correction chases an unreachable metric (ceremonial-test hazard).
  if [ "${1:-inloop}" = "full" ]; then
    qjacoco_check
  fi
  if [ "${SENSOR_SKIP_SONAR:-}" = "1" ]; then
    echo "sonar check WAIVED (SENSOR_SKIP_SONAR=1)"
  else
    sonar_check "${1:-inloop}"
  fi
  # K5: findings dimension at milestone only (not per-task — kantra cost).
  if [ "${1:-inloop}" = "inloop" ]; then
    _k5_milestone_scope_inloop
  else
    unset FINDINGS_K5_WAIVED
    if [ -z "${FINDINGS_SCOPE:-}" ]; then
      unset FINDINGS_SCOPE
    fi
  fi
  findings_sensor
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
  # O-K5GREENSUM (W4-650): do not name findings as a passed check when K5 was
  # waived (O-K5WAIVELEAK / FINDINGS_CHECK=off) — operator-facing honesty.
  local _findings_sum=findings
  if [ "${FINDINGS_K5_WAIVED:-}" = "1" ] || [ "${FINDINGS_CHECK:-on}" = "off" ]; then
    _findings_sum="findings[waived]"
  fi
  echo "milestone sensor GREEN (clean verify + sonar[${1:-inloop}] + ${_findings_sum}, isolated repo)"
}

# K5 — native findings sensor (milestone + preflight/M5). Kantra source-only
# against modernized (excl. staging/.hermes); compare to M1 baseline for
# PLAN_SCOPE / FINDINGS_SCOPE. FINDINGS_CHECK=off waives; FINDINGS_SENSOR_JSON
# injects a prebuilt current snapshot (instruments / offline).
findings_sensor() {
  [ "${FINDINGS_CHECK:-on}" = "off" ] && { echo "findings check WAIVED (operator override)"; return 0; }
  # O-K5WAIVELEAK: in-loop milestone with zero completed-task Findings must
  # not evaluate PLAN_SCOPE / --scope-all (empty FINDINGS_SCOPE + :- fallback).
  if [ "${FINDINGS_K5_WAIVED:-}" = "1" ]; then
    echo "findings check WAIVED (O-K5WAIVELEAK: no completed-task Findings in-loop)"
    return 0
  fi
  [ -f migration/mta-findings.json ] || { echo "findings check skip — no M1 baseline"; return 0; }
  [ -f "$SELF_DIR/findings-diff.py" ] || { echo "findings check skip — findings-diff.py absent"; return 0; }
  local cur="migration/mta-findings-current.json"
  local scope="${FINDINGS_SCOPE:-${PLAN_SCOPE:-}}"
  if [ -n "${FINDINGS_SENSOR_JSON:-}" ] && [ -f "${FINDINGS_SENSOR_JSON}" ]; then
    cp "${FINDINGS_SENSOR_JSON}" "$cur"
  elif [ "${FINDINGS_SENSOR_REUSE:-}" = "1" ] && [ -f "$cur" ]; then
    :
  elif KBIN=$(
      # shellcheck disable=SC1091
      . "$SELF_DIR/kantra-path.sh" 2>/dev/null
      kantra_bin 2>/dev/null
    ) && [ -n "$KBIN" ]; then
    local A_TARGETS K_ARGS t DEST_SRC
    A_TARGETS=$(grep -A12 "^analysis:" migration.yaml 2>/dev/null | grep -m1 "targets:" | sed 's/.*\[\(.*\)\].*/\1/; s/,/ /g')
    [ -n "$A_TARGETS" ] || A_TARGETS="quarkus jakarta-ee9 cloud-readiness"
    K_ARGS=""
    for t in $A_TARGETS; do K_ARGS="$K_ARGS --target $t"; done
    [ -d .hermes/rules ] && K_ARGS="$K_ARGS --rules $(pwd)/.hermes/rules"
    DEST_SRC=/tmp/kantra-findings-src
    rm -rf "$DEST_SRC" /tmp/kantra-findings-out
    mkdir -p "$DEST_SRC"
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --delete \
        --exclude 'migration/staging/' --exclude '.hermes/' --exclude 'target/' \
        --exclude '.git/' \
        ./ "$DEST_SRC/" >/tmp/sensor-findings-rsync.log 2>&1 || true
    else
      cp -a . "$DEST_SRC/" 2>/dev/null || true
      rm -rf "$DEST_SRC/migration/staging" "$DEST_SRC/.hermes" "$DEST_SRC/target" \
        "$DEST_SRC/.git" 2>/dev/null || true
    fi
    (cd /tmp && JAVA_HOME="${JAVA_HOME_21:-$JAVA_HOME}" PATH="${JAVA_HOME_21:-$JAVA_HOME}/bin:$PATH" \
      "$KBIN" analyze -i "$DEST_SRC" -o /tmp/kantra-findings-out \
      $K_ARGS --mode source-only --json-output --overwrite) \
      > /tmp/sensor-findings.log 2>&1 \
      || { echo "WARN findings: kantra failed — see /tmp/sensor-findings.log (not hard RED)"; return 0; }
    [ -f /tmp/kantra-findings-out/output.json ] \
      && cp /tmp/kantra-findings-out/output.json "$cur" \
      || { echo "WARN findings: no kantra output — skip"; return 0; }
  elif [ -f migration/mta-findings-after.json ]; then
    cp migration/mta-findings-after.json "$cur"
  else
    echo "WARN findings: no kantra and no after/current snapshot — skip"
    return 0
  fi
  local diff_args=(migration/mta-findings.json "$cur")
  if [ -n "$scope" ]; then
    # PLAN_SCOPE may be space-separated rule prefixes
    scope=$(echo "$scope" | tr ' ' ',')
    diff_args+=(--scope "$scope")
  else
    diff_args+=(--scope-all)
  fi
  python3 "$SELF_DIR/findings-diff.py" "${diff_args[@]}" \
    || fail findings "in-scope MTA incidents survive (K5) — see FINDINGS: lines above"
  echo "findings check GREEN (K5)"
}

boot_check() {
  # Prod-profile boot against the dev PostgreSQL: exercises Flyway +
  # Hibernate schema validation — the drift class no unit test catches.
  # O-BOOTNOFLYWAY / O-BOOTDEVPG: packaged jar defaults to prod;
  # %prod.generation=validate against an empty DEV DB false-REDs
  # (missing table) when entities landed but Flyway/import.sql have not.
  # Do NOT switch to QUARKUS_PROFILE=dev/H2 here — db-kind is often
  # build-time postgresql (O-ENTITYDSPROD / O-PREFLIGHTH2), so %dev H2
  # URLs fail with "Driver does not support the provided URL: jdbc:h2:…".
  # Before schema provenance: keep DEV Postgres URL, override generation
  # to drop-and-create for the probe only.
  # O-BOOTSQLPROV: sql-load-script alone is NOT schema provenance — it seeds
  # data and needs a schema first. Counting it as provenance skipped
  # drop-and-create while %prod.generation=validate → missing table [owners].
  # Only Flyway/Liquibase migration files flip has_schema_prov.
  $MVN clean package -DskipTests > /tmp/sensor-package.log 2>&1 \
    || fail boot "package failed — /tmp/sensor-package.log"
  # DB env only when the app actually has a JDBC extension — a DB-less
  # migration (e.g. the cart service) boots plain.
  DB_ENV=()
  BOOT_EXTRA=()
  local has_schema_prov=0
  if [ -n "$(find src/main/resources/db/migration -name '*.sql' 2>/dev/null | head -1)" ] \
    || [ -n "$(find src/main/resources/db/changelog -name '*.xml' -o -name '*.yaml' -o -name '*.yml' -o -name '*.sql' 2>/dev/null | head -1)" ]; then
    has_schema_prov=1
  fi
  if grep -q "quarkus-jdbc" pom.xml 2>/dev/null; then
    DB_ENV=(QUARKUS_DATASOURCE_JDBC_URL="$DEV_DB_URL"
            QUARKUS_DATASOURCE_USERNAME="${DEV_DB_USER:-coolstore}"
            QUARKUS_DATASOURCE_PASSWORD="${DEV_DB_PASSWORD:-coolstore}")
    if [ "$has_schema_prov" != "1" ]; then
      # Entity harvest before Flyway — do not prod-validate empty Postgres.
      # sql-load-script (if present) still needs drop-and-create here (O-BOOTSQLPROV).
      BOOT_EXTRA=(QUARKUS_HIBERNATE_ORM_DATABASE_GENERATION=drop-and-create)
      echo "boot check: O-BOOTDEVPG — no Flyway/Liquibase migrations; DEV Postgres + generation=drop-and-create (O-BOOTSQLPROV: sql-load ≠ provenance)"
    fi
  fi
  # O-BOOTPORTSTALE: drop a prior quarkus-run on the probe port before start.
  if command -v ss >/dev/null 2>&1; then
    ss -lptn 2>/dev/null | grep -q ':8099' && {
      for p in $(ps -eo pid=,args= | awk '/[q]uarkus-run\.jar/{print $1}'); do
        kill -9 "$p" 2>/dev/null || true
      done
      sleep 1
    }
  fi
  env "${DB_ENV[@]}" "${BOOT_EXTRA[@]}" QUARKUS_HTTP_PORT=8099 \
    java -jar target/quarkus-app/quarkus-run.jar > /tmp/sensor-boot.log 2>&1 &
  local pid=$!
  local up="" root=""
  # O-HEALTHROOT / O-BOOTROOT: preserved servlet context-path as
  # quarkus.http.root-path moves /q/health under ${root}/q/health unless
  # non-application-root-path=/q is set. Probe both.
  root=$(grep -E '^(%prod\.)?quarkus\.http\.root-path=' src/main/resources/application.properties 2>/dev/null \
    | tail -1 | sed -E 's/^[^=]+=//;s/[[:space:]]+$//' || true)
  root=${root%/}
  for _ in $(seq 1 30); do
    sleep 2
    if curl -sf http://localhost:8099/q/health >/dev/null 2>&1 \
      || { [ -n "$root" ] && curl -sf "http://localhost:8099${root}/q/health" >/dev/null 2>&1; }; then
      up=yes; break
    fi
    kill -0 $pid 2>/dev/null || break
  done
  kill $pid 2>/dev/null; wait $pid 2>/dev/null
  [ "$up" = "yes" ] || fail boot "$(grep -iE 'ERROR|Caused by|SchemaManagement|Migration|Port .* in use' /tmp/sensor-boot.log | head -6)"
  if [ "$has_schema_prov" = "1" ]; then
    echo "boot check GREEN (Flyway + schema validation against the dev DB)"
  else
    echo "boot check GREEN (O-BOOTDEVPG DEV Postgres drop-and-create — schema provenance deferred)"
  fi
}

wiring_invariants() {
  # N3: pom rewrites twice stripped the coverage instrumentation — the
  # factory's coverage gate reads jacoco; losing the wiring reads as 0%.
  grep -q "jacoco-maven-plugin" pom.xml \
    || fail wiring "pom.xml lost the jacoco-maven-plugin (coverage gate will read 0%)"
  grep -q "sonar.coverage.jacoco.xmlReportPaths" pom.xml \
    || fail wiring "pom.xml lost sonar.coverage.jacoco.xmlReportPaths"
  # O-SHIPFIXJACOCO: preflight/boot tips must not strip quarkus.jacoco.report*
  # while keeping data-file (harness O-QJACOCO wiring). Only drop when the
  # whole jacoco stanza is intentionally removed with the extension.
  local _props="src/main/resources/application.properties"
  if [ -f "$_props" ] && grep -qE '^[[:space:]]*quarkus\.jacoco\.data-file=' "$_props" 2>/dev/null; then
    grep -qE '^[[:space:]]*quarkus\.jacoco\.report=' "$_props" 2>/dev/null \
      || fail wiring "quarkus.jacoco.report missing while data-file set (O-SHIPFIXJACOCO) — do not strip report wiring in Preflight/boot tips"
    grep -qE '^[[:space:]]*quarkus\.jacoco\.report-location=' "$_props" 2>/dev/null \
      || fail wiring "quarkus.jacoco.report-location missing while data-file set (O-SHIPFIXJACOCO) — do not strip report wiring in Preflight/boot tips"
  fi
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
    # V5 run-4 S03 cascade (REST client present, no impl to inject it).
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
  http_port_deploy_contract
  gen_seed_contract
  prod_schema_contract
  pct_file_contract
}

# O-HTTPPORT — quarkus.http.port must match k8s http containerPort (or
# QUARKUS_HTTP_PORT env). Copying legacy server.port (e.g. 9966) while
# Service/probes stay on 8080 is a deploy crash-loop that compile/test miss.
http_port_deploy_contract() {
  local props="src/main/resources/application.properties"
  [ -f "$props" ] || return 0
  [ -d k8s ] || return 0
  local app_port
  app_port=$(grep -E '^[[:space:]]*quarkus\.http\.port=' "$props" 2>/dev/null \
    | head -1 | cut -d= -f2 | tr -d '[:space:]')
  [ -n "$app_port" ] || return 0
  # Deploy env override is the runtime authority when present.
  local env_file env_val=""
  env_file=$(grep -REl 'name:[[:space:]]*QUARKUS_HTTP_PORT' k8s 2>/dev/null | head -1 || true)
  if [ -n "$env_file" ]; then
    env_val=$(grep -A5 'name:[[:space:]]*QUARKUS_HTTP_PORT' "$env_file" \
      | grep -E 'value:' | head -1 | awk '{print $2}' | tr -d '"' || true)
    [ -n "$env_val" ] && app_port="$env_val"
  fi
  APP_PORT="$app_port" python3 - <<'PY' \
    || fail wiring "quarkus.http.port=${app_port} mismatches k8s http containerPort (O-HTTPPORT) — do not copy legacy server.port; keep deploy contract (usually 8080) or set QUARKUS_HTTP_PORT"
import os, pathlib, re, sys
app_port = os.environ.get("APP_PORT", "").strip()
if not app_port.isdigit():
    sys.exit(0)
want = int(app_port)
dbish = {5432, 3306, 6379, 27017, 11211}
ports = []
root = pathlib.Path("k8s")
for p in root.rglob("*"):
    if p.suffix not in {".yaml", ".yml"}:
        continue
    text = p.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"containerPort:\s*(\d+)", text):
        n = int(m.group(1))
        if n not in dbish:
            ports.append(n)
if not ports:
    sys.exit(0)
sys.exit(0 if want in ports else 1)
PY
}

# O-GENSEED (R-225/R-226): sql-load-script requires a generation mode that
# creates/updates schema. validate/none + import.sql → empty tables / validate
# fail on fresh DB (seed skipped or schema missing).
# O-BOOTSQLPROV: %prod.sql-load-script + %prod.generation=validate|none is also
# RED (preflight tips used that pair to fake schema provenance).
gen_seed_contract() {
  local props="src/main/resources/application.properties"
  [ -f "$props" ] || return 0
  # Profiled prod seed + validate/none — check even when %dev is drop-and-create.
  if grep -qE '^[[:space:]]*%prod\.quarkus\.hibernate-orm\.sql-load-script=' "$props" 2>/dev/null; then
    local prod_gen
    prod_gen=$(grep -E '^[[:space:]]*%prod\.quarkus\.hibernate-orm\.database\.generation=' "$props" 2>/dev/null \
      | head -1 | cut -d= -f2 | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
    case "${prod_gen}" in
      validate|none|"")
        fail wiring "%prod.sql-load-script set but %prod.database.generation=${prod_gen:-unset} (O-GENSEED/O-BOOTSQLPROV) — use update or prefer Flyway; do not pair prod seed with validate"
        ;;
    esac
  fi
  grep -qE '^[[:space:]]*%?(dev|test|acceptancetest)\.?quarkus\.hibernate-orm\.sql-load-script=|^[[:space:]]*quarkus\.hibernate-orm\.sql-load-script=' "$props" 2>/dev/null \
    || return 0
  # Prefer profiled generation for seed; unprofiled drop-and-create is O-PRODSCHEMA.
  if grep -qE '^[[:space:]]*%(dev|test|acceptancetest)\.quarkus\.hibernate-orm\.database\.generation=(drop-and-create|update)\b' "$props" 2>/dev/null; then
    return 0
  fi
  local gen
  gen=$(grep -E '^[[:space:]]*quarkus\.hibernate-orm\.database\.generation=' "$props" 2>/dev/null \
    | head -1 | cut -d= -f2 | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
  [ -n "$gen" ] || return 0
  case "$gen" in
    validate|none)
      fail wiring "sql-load-script set but database.generation=${gen} (O-GENSEED) — use %dev/%test/%acceptancetest drop-and-create|update (not prod drop-and-create)"
      ;;
  esac
}

# O-PRODSCHEMA (W3-131/132): unprofiled drop-and-create drops production schema
# on boot when profiled variants already exist (or always — prod must not recreate).
prod_schema_contract() {
  local props="src/main/resources/application.properties"
  [ -f "$props" ] || return 0
  if grep -qE '^[[:space:]]*quarkus\.hibernate-orm\.database\.generation=drop-and-create\b' "$props" 2>/dev/null; then
    fail wiring "unprofiled database.generation=drop-and-create (O-PRODSCHEMA) — use %dev/%test/%acceptancetest only; prod must not drop schema on boot"
  fi
}

# O-PCTFILE (R-230/F-68/T-012): Quarkus profile-aware *files* are
# application-{profile}.properties (no percent). The `%profile.` prefix is
# for keys inside a properties file — a literal `application-%foo.properties`
# filename is not a profile selector and is ignored / confusing (S03 T-012
# MiniMax tip `4032cdf`).
pct_file_contract() {
  local bad
  bad=$(find src/main/resources src/test/resources -maxdepth 1 -type f \
    \( -name 'application-%*.properties' -o -name 'application-%*.yaml' \
       -o -name 'application-%*.yml' \) 2>/dev/null | head -5 | tr '\n' ' ')
  [ -z "$bad" ] || fail wiring "literal % in profile filename(s): ${bad}(O-PCTFILE) — use application-{profile}.properties or %profile.key= inside application.properties"
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

# O-REDATTRIB: when G-CAT fails, attribute the owning task (acceptance in
# Owns/Target) so later tasks do not burn MiniMax on inherited debt.
_redattrib_gcat() {
  local surf="$1" tasks="${STORY_TASKS:-migration/tasks.md}" tid="${CURRENT_TASK:-}"
  rm -f /tmp/red-attrib.txt
  [ -f "$tasks" ] || return 0
  local owner
  owner=$(PYTHONPATH="$SELF_DIR${PYTHONPATH:+:$PYTHONPATH}" python3 - "$tasks" "$surf" "$tid" <<'PY'
import re, sys
from task_contract import iter_task_headings  # O-T6dTCHEADING / step 1 SoT
tasks, surf, tid = sys.argv[1], sys.argv[2], sys.argv[3]
text = open(tasks, encoding="utf-8", errors="replace").read()
heads = list(iter_task_headings(text))
owners = []
for i, m in enumerate(heads):
    body = text[m.end(): heads[i+1].start() if i+1 < len(heads) else len(text)]
    if re.search(r"acceptanceCheck|acceptance-check|/acceptance|acceptance\.path", body, re.I):
        owners.append(m.group(1))
if not owners:
    sys.exit(0)
own = owners[0]
if tid and tid != own:
    print(f"INHERITED-FROM:{own} current={tid} surface={surf} — fix acceptance on {own} (do not MiniMax-burn {tid} for G-CAT debt)")
else:
    print(f"OWNED-BY:{own} surface={surf}")
PY
)
  [ -n "$owner" ] || return 0
  printf '%s\n' "$owner" > /tmp/red-attrib.txt
  echo "O-REDATTRIB: $owner" >&2
}

# O-ACCEPTGEN / Poll 81 B1: load acceptance.* from migration.yaml.
# Fallback literals below are Coolstore defaults only (ALLOWED: coolstore-default-fallback).
_acceptance_load_cfg() {
  ACC_COLLECTION=products  # ALLOWED: coolstore-default-fallback
  ACC_COLLECTION_LABEL=products
  ACC_BARE_ARRAY=0
  ACC_SERVICE=CatalogService  # ALLOWED: coolstore-default-fallback
  ACC_ENDPOINT_ENV=CATALOG_ENDPOINT  # ALLOWED: coolstore-default-fallback
  ACC_ITEM_TYPE=Product  # ALLOWED: coolstore-default-fallback
  ACC_MOCK_CLASS=MockCatalogService  # ALLOWED: coolstore-default-fallback
  ACC_GETTER=getProducts  # ALLOWED: coolstore-default-fallback
  ACC_PROOF_RE='products\(|getProducts\(|CatalogService|CATALOG_ENDPOINT|List<.*Product'  # ALLOWED: coolstore-default-fallback
  ACC_RETURN_RE='return[[:space:]]+.*\b(products|getProducts)\s*\(|return[[:space:]]+products\b'  # ALLOWED: coolstore-default-fallback
  # shellcheck disable=SC1090
  eval "$(python3 "$SELF_DIR/acceptance_config.py" --yaml migration.yaml --export-shell 2>/dev/null)" || true
  ACC_COLLECTION_LABEL="${ACC_COLLECTION_LABEL:-$ACC_COLLECTION}"
}

# V6 R3/R6 — ship-contract static checks (acceptance fail-open + mapper breadth).
acceptance_ship_contract() {
  [ -d src/main/java ] || return 0
  _acceptance_load_cfg
  if grep -RIqE 'ExceptionMapper\s*<\s*Exception\s*>' src/main/java 2>/dev/null; then
    fail mapper "ExceptionMapper<Exception> is forbidden (remaps NotFound→503) — narrow to catalog/service failures (V6 R6)"
  fi
  # Fail-open heuristic (V6 R3 / O-FAILOPEN-DTO Poll 52): acceptance surface
  # catch→return is HTTP 200 by default for POJO/record returns — not only
  # Response.ok. Allow rethrow or Response.status/serverError.
  local f
  while IFS= read -r -d '' f; do
    grep -qE 'acceptanceCheck|acceptance-check|/acceptance' "$f" 2>/dev/null || continue
    grep -qE 'catch[[:space:]]*\(' "$f" || continue
    if awk '
      /acceptanceCheck|acceptance-check|\/acceptance/ { inacc=1 }
      inacc && /catch[[:space:]]*\(/ { incatch=1 }
      incatch && /return/ && !/throw/ && !/Response\.(status|serverError)/ { found=1; exit }
      END { exit found?0:1 }
    ' "$f"; then
      fail acceptance "fail-open acceptance handler in $f (catch→return 200/DTO) — V6 R3 / O-FAILOPEN-DTO"
    fi
  done < <(find src/main/java -type f -name '*.java' -print0 2>/dev/null)
  # V6 abort: ceremonial status-map acceptance (service_interfaces_ready /
  # story-id Map) ships a 200 JSON object that is not a collection proof
  # — reject whenever such a marker appears on an acceptance surface.
  while IFS= read -r -d '' f; do
    grep -qE 'acceptanceCheck|acceptance-check|/acceptance' "$f" 2>/dev/null || continue
    if grep -qE 'service_interfaces_ready|interfaces_ready|"status"\s*,' "$f" 2>/dev/null; then
      fail acceptance "ceremonial status-map acceptance in $f (V6) — must return ${ACC_COLLECTION_LABEL} / live fetch, not a status Map"
    fi
  done < <(find src/main/java -type f -name '*.java' -print0 2>/dev/null)
  # G-OK (V7/V8): plain String / "OK" TEXT acceptance is not collection proof.
  # Non-deploy stories otherwise story-gate-pass with return "OK".
  while IFS= read -r -d '' f; do
    grep -qE 'acceptanceCheck|acceptance-check|/acceptance' "$f" 2>/dev/null || continue
    if grep -qE 'return[[:space:]]+"OK"|return[[:space:]]+"ok"|public[[:space:]]+String[[:space:]]+[a-zA-Z0-9_]*\(' "$f" 2>/dev/null; then
      if ! grep -qE "$ACC_PROOF_RE" "$f" 2>/dev/null; then
        fail acceptance "ceremonial String/OK acceptance in $f (G-OK) — must return ${ACC_COLLECTION_LABEL} / live fetch, not TEXT \"OK\""
      fi
    fi
  done < <(find src/main/java -type f -name '*.java' -print0 2>/dev/null)
  # G-CAT / O-ACCEPTREC (Poll 50) / O-ACCEPTGEN: positive collection requirement
  # for ANY acceptance surface — tokens from migration.yaml acceptance.*.
  while IFS= read -r -d '' f; do
    grep -qE 'acceptanceCheck|acceptance-check|/acceptance' "$f" 2>/dev/null || continue
    if ! grep -qE "$ACC_PROOF_RE" "$f" 2>/dev/null; then
      _redattrib_gcat "$f"
      fail acceptance "acceptance surface $f lacks collection fetch (G-CAT) — must reference ${ACC_SERVICE:-service}/${ACC_GETTER}()/${ACC_ENDPOINT_ENV:-endpoint} from migration.yaml acceptance.* (not ceremonial status DTO/record/Map/String)"
    fi
  done < <(find src/main/java -type f -name '*.java' -print0 2>/dev/null)
  # G-CATBODY: collection side-effect + status DTO still ships count=0 —
  # require the handler to *return* the collection, not wrap a fetch in
  # AcceptanceStatus("accepted", …).
  while IFS= read -r -d '' f; do
    grep -qE 'acceptanceCheck|acceptance-check|/acceptance' "$f" 2>/dev/null || continue
    if grep -qE 'new[[:space:]]+AcceptanceStatus|record[[:space:]]+AcceptanceStatus|"accepted"|"degraded"' "$f" 2>/dev/null; then
      fail acceptance "acceptance surface $f returns ceremonial status DTO (G-CATBODY) — return ${ACC_COLLECTION_LABEL} (${ACC_GETTER}()), not status/message"
    fi
    if ! grep -qE "$ACC_RETURN_RE" "$f" 2>/dev/null; then
      fail acceptance "acceptance surface $f does not return collection (G-CATBODY) — handler must return ${ACC_GETTER}() result (ship counts ${ACC_COLLECTION_LABEL})"
    fi
  done < <(find src/main/java -type f -name '*.java' -print0 2>/dev/null)
  # G-FAKE: mock service class (or hardcoded List.of itemType) in src/main
  # is not a live fetch — ship must use the configured client/endpoint.
  if [ -n "${ACC_MOCK_CLASS:-}" ] \
    && find src/main/java -type f -name "${ACC_MOCK_CLASS}.java" 2>/dev/null | grep -q .; then
    fail acceptance "${ACC_MOCK_CLASS} in src/main (G-FAKE) — use @RegisterRestClient ${ACC_SERVICE:-client} + ${ACC_ENDPOINT_ENV:-endpoint env}"
  fi
  while IFS= read -r -d '' f; do
    grep -qE 'acceptanceCheck|acceptance-check|/acceptance' "$f" 2>/dev/null || continue
    local fake_re='getMockProducts'
    if [ -n "${ACC_ITEM_TYPE:-}" ]; then
      fake_re="List\\.of\\s*\\(\\s*new[[:space:]]+${ACC_ITEM_TYPE}|getMockProducts"
    fi
    if grep -qE "$fake_re" "$f" 2>/dev/null; then
      fail acceptance "hardcoded mock ${ACC_COLLECTION} in acceptance surface $f (G-FAKE) — fetch live collection"
    fi
  done < <(find src/main/java -type f -name '*.java' -print0 2>/dev/null)
}

# V6 R7 / P0c — before deploy, the stamped acceptance.path must have a Java
# handler (full path, leaf @Path, or acceptanceCheck method). Plan-lint alone
# only requires the path string in tasks.md; this catches ceremonial tasks.
# O-ACCPATHROOT: acceptance.path often includes quarkus.http.root-path
# (e.g. /petclinic/api/vets) while @Path is only the resource suffix
# (/api/vets). Strip root-path before matching; also accept @Path containing
# the resource path or the leaf segment.
acceptance_path_handler() {
  [ "${STORY_DEPLOY:-false}" = "true" ] || return 0
  [ -f migration.yaml ] || return 0
  [ -d src/main/java ] || fail acceptance "STORY_DEPLOY=true but src/main/java is absent — cannot serve acceptance.path"
  local acc_path leaf root_path resource_path
  acc_path=$(python3 -c "
import re,sys
try: my=open('migration.yaml').read()
except FileNotFoundError: sys.exit(0)
m=re.search(r'^acceptance:\s*\n(?:[ \t]*#.*\n|[ \t]*\n)*[ \t]*path:\s*(\S+)', my, re.M)
print(m.group(1) if m else '')
" 2>/dev/null)
  [ -n "$acc_path" ] || return 0
  leaf="${acc_path##*/}"
  root_path=$(python3 -c "
import re,sys
try: p=open('src/main/resources/application.properties').read()
except FileNotFoundError: sys.exit(0)
# prefer unprofiled quarkus.http.root-path=
m=re.search(r'^(?!%)quarkus\\.http\\.root-path=(\\S+)', p, re.M)
if not m:
    m=re.search(r'^quarkus\\.http\\.root-path=(\\S+)', p, re.M)
print(m.group(1).rstrip('/') if m else '')
" 2>/dev/null || true)
  resource_path="$acc_path"
  if [ -n "$root_path" ] && [[ "$acc_path" == "$root_path"/* ]]; then
    resource_path="${acc_path#"$root_path"}"
  fi
  # normalize leading slash for matching
  resource_path="/${resource_path#/}"
  if grep -RIqF --include='*.java' "$acc_path" src/main/java 2>/dev/null; then
    return 0
  fi
  # @Path("/api/vets") or @Path("api/vets") matching resource suffix after root-path
  if [ -n "$resource_path" ] && [ "$resource_path" != "/" ] && grep -RIqE --include='*.java' \
      "@Path\\(\"${resource_path}\"|@Path\\(\"${resource_path#/}\"|@Path\\('${resource_path}'|@Path\\('${resource_path#/}'" \
      src/main/java 2>/dev/null; then
    return 0
  fi
  if [ -n "$leaf" ] && grep -RIqE --include='*.java' \
      "@Path\\(\"${leaf}\"|@Path\\(\"/${leaf}\"|@Path\\('/${leaf}'|@Path\\('${leaf}'|acceptanceCheck|acceptance-check" \
      src/main/java 2>/dev/null; then
    return 0
  fi
  # leaf embedded in a longer @Path (e.g. @Path("/api/vets") when leaf=vets)
  if [ -n "$leaf" ] && grep -RIqE --include='*.java' \
      "@Path\\(\"[^\"]*/${leaf}\"|@Path\\('[^']*/${leaf}'" \
      src/main/java 2>/dev/null; then
    return 0
  fi
  fail acceptance "acceptance.path '${acc_path}' has no Java @Path/handler in src/main (V6 R7 handler-before-deploy) — add the resource method before ship"
}

preflight() {
  # O-PREFLIGHTDIM (F-70/F-37): cap full preflights per ship session.
  # S01 burned ~30m / 9× full milestone-via-preflight on one RED. Prefer
  # dimension sensors (sonar|task|fidelity) in the fix loop; allow this
  # many full preflights then refuse (closing preflight after a GREEN
  # dimension pass should reset /tmp/preflight-count).
  local _pf_n=0 _pf_cap="${PREFLIGHT_FULL_CAP:-3}"
  if [ -f /tmp/preflight-count ]; then
    _pf_n=$(cat /tmp/preflight-count 2>/dev/null || echo 0)
  fi
  _pf_n=$((_pf_n + 1))
  printf '%s\n' "$_pf_n" > /tmp/preflight-count
  if [ "$_pf_n" -gt "$_pf_cap" ]; then
    # O-PREFDIMTHRASH / O-PFCOUNTRM: refuse is a budget signal. Supervisor
    # resets /tmp/preflight-count at fix-round start and on refuse→closing
    # path — seats should NOT rm the counter themselves.
    echo "REFUSED (O-PREFLIGHTDIM): full preflight #${_pf_n} exceeds cap ${_pf_cap} — use .hermes/harness/sensors.sh sonar|task|fidelity then ONE closing preflight (supervisor resets preflight-count; do not rm)"
    exit 2
  fi
  wiring_invariants
  preserved_integrations
  # O-CONFIGDERIVED / F-config-derived: migrated properties must match legacy
  # or a declared configTransforms: rename (architecture gate, not ship hack).
  if [ "${CONFIG_DERIVED_CHECK:-on}" != "off" ] \
    && [ -f .hermes/harness/config_derived.py ]; then
    if ! python3 .hermes/harness/config_derived.py \
      --root . --legacy "${LEGACY_ROOT:-/projects/legacy}" \
      --yaml migration.yaml > /tmp/config-derived.txt 2>&1; then
      cat /tmp/config-derived.txt
      fail configderived "O-CONFIGDERIVED undeclared config drift (see CONFIGDERIVED: lines / /tmp/config-derived.txt)"
    fi
    cat /tmp/config-derived.txt
    echo "config-derived check GREEN"
  fi
  acceptance_ship_contract
  acceptance_path_handler
  root_index_present
  milestone_sensor full
  # K5: M5/preflight always re-checks findings (milestone already ran it;
  # reuse current snapshot unless forced refresh).
  FINDINGS_SENSOR_REUSE="${FINDINGS_SENSOR_REUSE:-1}" findings_sensor
  boot_check
  echo "PREFLIGHT GREEN — the factory should confirm, not discover"
}

fidelity_check() {
  # Standalone Port-scoped fidelity (cheap sfix recheck — pure python).
  # O-FIDELITYPORT: Port=reimplement uses redesign-sig, not byte-match.
  if [ "${FIDELITY_CHECK:-on}" = "off" ]; then
    echo "fidelity check WAIVED"; return 0
  fi
  if ! run_port_scoped_fidelity; then
    cat /tmp/sensor-fidelity.log
    {
      echo "SENSOR RED:fidelity (HARVEST FIDELITY / O-FIDELITYPORT — primary sfix dimension)"
      cat /tmp/sensor-fidelity.log
    } >> /tmp/sensor-milestone.log 2>/dev/null || cp /tmp/sensor-fidelity.log /tmp/sensor-milestone.log
    printf '%s\n' fidelity > /tmp/sensor-fix-dim
    fail fidelity "Port-scoped fidelity RED (see FIDELITY:/SIG: lines / /tmp/sensor-fidelity.log) — Port=rename=byte-match; Port=reimplement=public signatures"
  fi
  cat /tmp/sensor-fidelity.log
  echo "fidelity check GREEN"
  echo "harvest fidelity GREEN" >> /tmp/sensor-milestone.log 2>/dev/null || true
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
  static)    tree_hygiene; package_scope; forbidden_patterns; placeholder_tests; ship_assert_weaken; restassured_contract; redesign_sig_check; wireup_check; cdi_partial_check; tree_fix_stub_check; sdjpa_harvest_check; security_auth_test_contract; wiring_invariants; preserved_integrations; acceptance_ship_contract; acceptance_path_handler; root_index_present; echo "STATIC CHECKS GREEN";;
  package)   package_scope; echo "PACKAGE SCOPE GREEN";;
  findings)  findings_sensor; echo "FINDINGS CHECK DONE";;
  qjacoco)   qjacoco_check;;
  *) echo "usage: sensors.sh seed|task|milestone|sonar|fidelity|preflight|package|static|findings|qjacoco"; exit 2;;
esac

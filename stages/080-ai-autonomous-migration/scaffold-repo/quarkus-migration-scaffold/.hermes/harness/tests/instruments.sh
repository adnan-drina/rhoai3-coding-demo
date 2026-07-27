#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# X1 instrument test suite.
#
# Two plan-lint self-defects burned model budget in the cart runs (a rigid
# Class-marker regex, star-file confusion). Instruments that gate model
# sessions must themselves be tested before deployment. This suite covers
# every deterministic check in plan-lint.py and the static (no-Maven)
# sensors. Pure bash on purpose — it must run identically on workstations
# and workspace pods, neither of which ships bats.
#
#   .hermes/harness/tests/instruments.sh        run everything
#
# Exit 0 = all green. Each case prints ok/FAIL in TAP-ish style.
# ---------------------------------------------------------------------------
set -uo pipefail

HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LINT="$HARNESS_DIR/plan-lint.py"
SENSORS="$HARNESS_DIR/sensors.sh"
PASS=0; FAIL=0; N=0

check() { # $1=name $2=expected-exit(0|1) $3=expected-substring-of-output ("" = any)
  local name="$1" want_rc="$2" want_out="$3" rc=0 out
  out=$(run_case 2>&1) || rc=$?
  [ "$rc" -gt 1 ] && rc=1
  N=$((N+1))
  if [ "$rc" = "$want_rc" ] && { [ -z "$want_out" ] || grep -q "$want_out" <<<"$out"; }; then
    PASS=$((PASS+1)); echo "ok $N - $name"
  else
    FAIL=$((FAIL+1)); echo "FAIL $N - $name (rc=$rc want=$want_rc; output below)"
    sed 's/^/    /' <<<"$out"
  fi
}

# --- plan fixtures ---------------------------------------------------------

plan_header() { # a compliant two-task plan; stdin appends extra tasks
  cat <<'EOF'
# Tasks

UI surface: waived (API-only service; no legacy web frontend).

#### T-001: Swap javax imports
**Class**: rewrite
- Mechanical jakarta rename.

#### T-002: Design the cart endpoint
**Class**: infer
- Target: → src/main/java/com/demo/rest/CartEndpoint.java with @Path("/api/cart")
EOF
}

mkfix() { FIX=$(mktemp -d); cd "$FIX"; }

# 1. compliant plan accepted
run_case() { mkfix; plan_header > tasks.md; python3 "$LINT" tasks.md; }
check "lint accepts a compliant plan" 0 "PLAN OK"

# 2. the burned-budget regression: substance Class form must be accepted
run_case() {
  mkfix
  { plan_header; cat <<'EOF'

#### T-003: Convert services
- **Type:** `Class: infer`
- Target design: → src/main/java/com/demo/service/CartService.java
EOF
  } > tasks.md
  python3 "$LINT" tasks.md
}
check "lint accepts '- **Type:** \`Class: infer\`' substance form" 0 "PLAN OK"

# 3. duplicate ids rejected
run_case() {
  mkfix
  { plan_header; cat <<'EOF'

#### T-002: A second task reusing the id
**Class**: infer
- Target: → src/main/java/com/demo/Other.java
EOF
  } > tasks.md
  python3 "$LINT" tasks.md
}
check "lint rejects duplicate task ids" 1 "LINT:dup-ids"

# 4. missing Class marker rejected
run_case() {
  mkfix
  { plan_header; printf '\n#### T-003: No class here\n- Just prose.\n'; } > tasks.md
  python3 "$LINT" tasks.md
}
check "lint rejects a task without a Class marker" 1 "LINT:ids"

# 5. rewrite after infer rejected
run_case() {
  mkfix
  { plan_header; cat <<'EOF'

#### T-003: Late mechanical rename
**Class**: rewrite
- Should have come before the infer tasks.
EOF
  } > tasks.md
  python3 "$LINT" tasks.md
}
check "lint rejects rewrite tasks after infer tasks began" 1 "LINT:order"

# 6. infer without design rejected
run_case() {
  mkfix
  { plan_header; printf '\n#### T-003: Vague judgment task\n**Class**: infer\n- Figure it out later.\n'; } > tasks.md
  python3 "$LINT" tasks.md
}
check "lint rejects an infer task without decided design" 1 "LINT:design"

# 7. legacy package identity rejected
run_case() {
  mkfix
  { plan_header; printf '\n#### T-003: Port service\n**Class**: infer\n- Target: → src/main/java/com/redhat/coolstore/Svc.java\n'; } > tasks.md
  python3 "$LINT" tasks.md
}
check "lint rejects com.redhat.coolstore package targets" 1 "LINT:package"

# 8. ui surface must be covered or waived
run_case() {
  mkfix
  plan_header | grep -v "UI surface" > tasks.md
  python3 "$LINT" tasks.md
}
check "lint requires the UI surface covered or waived" 1 "LINT:ui-surface"

# 9. preserve: items must be mapped (and mapped passes)
run_case() {
  mkfix
  plan_header > tasks.md
  printf 'preserve:\n  - CATALOG_ENDPOINT\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "lint rejects an unmapped preserve: item" 1 "LINT:preserve"

run_case() {
  mkfix
  { plan_header; printf '\nT-002 also preserves CATALOG_ENDPOINT via the REST client url.\n'; } > tasks.md
  printf 'preserve:\n  - CATALOG_ENDPOINT\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "lint accepts a mapped preserve: item" 0 "PLAN OK"

# 10. acceptance.path must be mapped (cart run #2 ship-time discovery)
run_case() {
  mkfix
  plan_header > tasks.md
  printf 'acceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "lint rejects an unmapped acceptance path" 1 "LINT:acceptance"

run_case() {
  mkfix
  { plan_header; printf '\nT-002 also serves /api/cart/acceptance-check for the ship gate.\n'; } > tasks.md
  printf 'acceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "lint accepts a mapped acceptance path" 0 "PLAN OK"

# 11. mandatory findings must be mapped
run_case() {
  mkfix
  plan_header > tasks.md
  cat > findings.json <<'EOF'
[{"violations": {"javax-to-jakarta-00001": {"category": "mandatory"},
                 "spring-components-00002": {"category": "mandatory"}}}]
EOF
  python3 "$LINT" tasks.md findings.json
}
check "lint rejects unmapped mandatory findings" 1 "LINT:findings"

# 11b. parser parity: the supervisor's task-id grep must accept every
# heading depth the lint accepts (audit finding: #{3,6} vs #{2,6} drift)
run_case() {
  mkfix
  printf '## T-001: Depth-two heading\n**Class**: rewrite\n- x\n\nUI surface: waived.\n' > tasks.md
  python3 "$LINT" tasks.md > lint.out
  ids=$(grep -E '^#{2,6} +T[-A-Za-z0-9]*[0-9]+:' tasks.md | wc -l | tr -d ' ')
  grep -q "PLAN OK" lint.out && [ "$ids" = "1" ] && echo "PARITY OK"
}
check "supervisor task grep accepts every lint-accepted heading depth" 0 "PARITY OK"

# 11c. dependency-order: dependencies must precede dependents
run_case() {
  mkfix
  mkdir -p src/main/java/app
  printf 'package app;\npublic class Model {}\n' > src/main/java/app/Model.java
  printf 'package other;\nimport app.Model;\npublic class Endpoint {}\n' > src/main/java/app/Endpoint.java
  python3 "$HARNESS_DIR/dependency-order.py" . | awk "/^1\./ {print \$2}"
}
check "dependency-order puts the imported class first" 0 "app.Model"

# 11d. findings-inventory: joins rules via the MAPPINGS table
run_case() {
  mkfix
  printf '[{"violations": {"javax-to-jakarta-import-00001": {"category": "mandatory", "description": "javax to jakarta", "incidents": [{"uri": "file:///a/B.java", "lineNumber": 3}]}, "custom-rule-001": {"category": "mandatory", "description": "no join", "incidents": []}}}]' > f.json
  printf '## Windup rule joins\n\n| rule id prefix | class | decided target |\n|---|---|---|\n| javax-to-jakarta- | recipe:5.46.1:g:a:1.0:R.Name | jakarta |\n' > M.md
  python3 "$HARNESS_DIR/findings-inventory.py" f.json M.md
}
check "findings-inventory classifies joined + flags OPEN DESIGN" 0 "OPEN DESIGN: 1"

# 11e. plan-lint: recipe-log covers a mandatory rule without a task
run_case() {
  mkfix
  plan_header > tasks.md
  printf '[{"violations": {"javax-to-jakarta-import-00001": {"category": "mandatory", "incidents": []}}}]' > f.json
  mkdir -p migration && printf 'Resolved rule ids:\n- javax-to-jakarta-import-00001\n' > migration/recipe-log.md
  python3 "$LINT" tasks.md f.json
}
check "lint accepts recipe-executed mandatory rule with no task" 0 "PLAN OK"

# --- static sensor fixtures ------------------------------------------------

green_pom() {
  cat <<'EOF'
<project>
  <properties>
    <sonar.coverage.jacoco.xmlReportPaths>target/jacoco-report/jacoco.xml</sonar.coverage.jacoco.xmlReportPaths>
  </properties>
  <build><plugins>
    <plugin>
      <artifactId>maven-compiler-plugin</artifactId>
      <version>3.14.0</version>
    </plugin>
    <plugin>
      <groupId>org.jacoco</groupId>
      <artifactId>jacoco-maven-plugin</artifactId>
      <version>0.8.12</version>
    </plugin>
  </plugins></build>
</project>
EOF
}

sensor_fixture() { # a static-green tree
  mkfix
  mkdir -p src/main/java/com/demo
  green_pom > pom.xml
  printf 'public class Svc { String url = "${CATALOG_ENDPOINT}"; }\n' > src/main/java/com/demo/Svc.java
  printf 'preserve:\n  - CATALOG_ENDPOINT\nforbidden:\n  - getMockProducts\n' > migration.yaml
}

# 12. green fixture passes
run_case() { sensor_fixture; SENSOR_ROOT="$FIX" bash "$SENSORS" static; }
check "static sensors pass a clean fixture" 0 "STATIC CHECKS GREEN"

# 13. star-file tree hygiene
run_case() { sensor_fixture; touch 'src/main/java/com/demo/*.java'; SENSOR_ROOT="$FIX" bash "$SENSORS" static; }
check "static sensors reject a literal '*.java' filename" 1 "hygiene"

# 14. lost jacoco wiring
run_case() { sensor_fixture; grep -v jacoco-maven-plugin pom.xml > p && mv p pom.xml; SENSOR_ROOT="$FIX" bash "$SENSORS" static; }
check "static sensors reject a pom without jacoco-maven-plugin" 1 "wiring"

# 15. compiler plugin without a version pin (cart run #2 factory failure)
run_case() { sensor_fixture; sed '/maven-compiler-plugin/{n;d;}' pom.xml > p && mv p pom.xml; SENSOR_ROOT="$FIX" bash "$SENSORS" static; }
check "static sensors reject an unpinned maven-compiler-plugin" 1 "wiring"

# 16. forbidden pattern in src/main (fabrication tripwire)
run_case() { sensor_fixture; printf 'class Fake { void getMockProducts() {} }\n' > src/main/java/com/demo/Fake.java; SENSOR_ROOT="$FIX" bash "$SENSORS" static; }
check "static sensors reject a forbidden: pattern in src/main" 1 "forbidden"

# 17. erased preserved integration
run_case() { sensor_fixture; printf 'public class Svc { }\n' > src/main/java/com/demo/Svc.java; SENSOR_ROOT="$FIX" bash "$SENSORS" static; }
check "static sensors reject an erased preserve: item" 1 "preserve"

echo "----"
echo "$PASS/$N passed"
[ "$FAIL" -eq 0 ]

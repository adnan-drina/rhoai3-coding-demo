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
- Mechanical jakarta rename across src/main/java sources.

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

# 7. legacy package identity rejected — but only in TARGET position
run_case() {
  mkfix
  { plan_header; printf '\n#### T-003: Port service\n**Class**: infer\n- Target: → src/main/java/com/redhat/coolstore/Svc.java\n'; } > tasks.md
  python3 "$LINT" tasks.md
}
check "lint rejects com.redhat.coolstore package targets" 1 "LINT:package"

run_case() {
  mkfix
  { plan_header; cat <<'EOF'

#### T-003: Harvest model
**Class**: infer
**Source**: migration/staging/src/main/java/com/redhat/coolstore/model/Cart.java
**Target**: src/main/java/com/demo/model/Cart.java
**Test**: src/test/java/com/demo/model/CartTest.java
Package transform com.redhat.coolstore.model to com.demo.model.
EOF
  } > tasks.md
  python3 "$LINT" tasks.md
}
check "lint accepts legacy package in SOURCE position (from-to plan)" 0 "PLAN OK"

# 7b. ceremonial tasks rejected (task-substance, T-029 class)
run_case() {
  mkfix
  { plan_header; printf '\n#### T-003: UI surface waiver\n**Class**: infer\nExplicitly waive the UI surface with a documented rationale and target design statement.\n'; } > tasks.md
  python3 "$LINT" tasks.md
}
check "lint rejects tasks naming no code path (ceremonial)" 1 "LINT:substance"

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

# 10b. V5/run-4: comment between acceptance: and path: must still enforce mapping (V6 R7)
run_case() {
  mkfix
  plan_header > tasks.md
  printf 'acceptance:\n  # harness asserts this after deploy\n  path: /api/cart/acceptance-check\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "lint rejects unmapped acceptance path when comment precedes path:" 1 "LINT:acceptance"

run_case() {
  mkfix
  { plan_header; printf '\nT-002 also serves /api/cart/acceptance-check for the ship gate.\n'; } > tasks.md
  printf 'acceptance:\n  # harness asserts this after deploy\n  path: /api/cart/acceptance-check\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "lint accepts mapped acceptance path when comment precedes path:" 0 "PLAN OK"

# 10c. V6 R4 — acceptance product counter (bare objects must count as 0)
run_case() {
  mkfix
  printf '%s\n' '[{"id":"1"},{"id":"2"}]' | python3 "$HARNESS_DIR/acceptance-products.py"
}
check "acceptance-products counts JSON arrays" 0 "2"

run_case() {
  mkfix
  printf '%s\n' '{"products":[{"id":"1"}]}' | python3 "$HARNESS_DIR/acceptance-products.py"
}
check "acceptance-products counts nested products arrays" 0 "1"

run_case() {
  mkfix
  out=$(printf '%s\n' '{"status":"ok","cartCount":0}' | python3 "$HARNESS_DIR/acceptance-products.py")
  [ "$out" = "0" ]
}
check "acceptance-products rejects bare status objects (run-4 false green)" 0 ""

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
  printf '## T-001: Depth-two heading\n**Class**: rewrite\n- rename across src/main/java.\n\nUI surface: waived.\n' > tasks.md
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

# 11f. profile-rubric: accepts a complete cited profile
profile_fixture() {
  cat <<'EOF'
# Architecture profile
## 1. Purpose & domain
A shopping cart service managing carts, items and promotions for the coolstore shop; carts price their items against a remote product catalog and apply threshold-based shipping costs and promotions, with the expected totals pinned by the legacy suite (ShoppingCartServiceTest). The core domain concepts are the cart, its items, the product, and the promotion.
## 2. Components & relationships
The REST layer (CartEndpoint, src/main/java/com/redhat/coolstore/rest/CartEndpoint.java:20) depends on ShoppingCartServiceImpl which composes ShippingService and PromoService; models ShoppingCart and Product are the god nodes per the dependency analysis and carry the highest fan-in and therefore the change risk.
## 3. Integration surfaces
The catalog is consumed via an env-configured endpoint CATALOG_ENDPOINT (src/main/resources/application.properties:6), covered by preserve: CATALOG_ENDPOINT; the REST API exposes cart operations under /api/cart per the controller mappings in the endpoint class source.
## 4. Behavioral contract sources
The legacy suite ShoppingCartServiceTest pins the pricing behavior that constitutes the contract: cartItemTotal 2000.0 and shippingPromoSavings -10.99 for the two-item vehicle cart fixture (src/test/java/com/redhat/coolstore/service/ShoppingCartServiceTest.java:40). The checkout and set-cart flows carry no test coverage at all — a contract gap the specs must close with characterization tests before those flows are touched.
## 5. Modernization surface
The pom family must move to the Quarkus platform (javaee-pom-to-quarkus-00010 and siblings, all mandatory); imports move per javax-to-jakarta-import-00001; in-memory cart state flagged by the platform rule needs an explicit decision (src/main/java/com/redhat/coolstore/service/ShoppingCartServiceImpl.java:30).
## 6. Domain boundaries
Effectively a single bounded context: the cart, pricing and promotion classes all share mutable state through the ShoppingCart model, and the dependency graph shows edges from the model package into every service class (src/main/java/com/redhat/coolstore). No seam exists that would let pricing or promotion be modernized in isolation from the cart itself.
## 7. Class roles & target contract
The model classes (Product, ShoppingCart) are HARVEST — carried faithfully with legacy value pins (src/main/java/com/redhat/coolstore/model). ShoppingCartServiceImpl is REDESIGN: target concurrency is a ConcurrentHashMap with compute() for cart state, the cache refresh-guard replaces clear-on-miss, and the API contract makes GET idempotent (404 on missing) with input validation and error mapping. CartEndpoint is REDESIGN with the same read-only GET target (src/main/java/com/redhat/coolstore/rest/CartEndpoint.java).
EOF
}
run_case() { mkfix; profile_fixture > p.md; python3 "$HARNESS_DIR/profile-rubric.py" p.md; }
check "profile-rubric accepts a complete cited profile" 0 "PROFILE OK"

# 11g. profile-rubric rejects missing/uncited/plan-leaking profiles
run_case() {
  mkfix; profile_fixture | grep -v "Domain boundaries" | grep -v "bounded context" > p.md
  python3 "$HARNESS_DIR/profile-rubric.py" p.md
}
check "profile-rubric rejects a missing section" 1 "RUBRIC:missing"

run_case() {
  mkfix
  { profile_fixture; printf '\n## Task breakdown\n#### T-001: convert pom\n'; } > p.md
  python3 "$HARNESS_DIR/profile-rubric.py" p.md
}
check "profile-rubric rejects plan leakage" 1 "RUBRIC:plan-leakage"


# 7c. hedge-word lint (V3 S02 T-001 contradiction signature)
run_case() {
  mkfix
  { plan_header; printf '\n#### T-003: Bootstrap\n**Class**: infer\n- Target: src/main/java/com/demo/App.java — convert to a main class if needed.\n'; } > tasks.md
  python3 "$LINT" tasks.md
}
check "lint rejects hedge phrases in infer designs" 1 "LINT:hedge"

# --- harvest-fidelity (B4) -------------------------------------------------
fidelity_fixture() { # $1 = uid for the destination copy
  mkdir -p migration/staging/src/main/java/m src/main/java/m
  printf 'package m;\npublic class C implements java.io.Serializable {\n    private static final long serialVersionUID = -111L;\n    private int x;\n}\n' > migration/staging/src/main/java/m/C.java
  printf 'package m;\npublic class C implements java.io.Serializable {\n    private static final long serialVersionUID = %sL;\n    private int x;\n}\n' "$1" > src/main/java/m/C.java
}
run_case() { mkfix; fidelity_fixture -111; python3 "$HARNESS_DIR/harvest-fidelity.py"; }
check "harvest-fidelity passes a faithful harvest" 0 "GREEN"

run_case() { mkfix; fidelity_fixture 1; python3 "$HARNESS_DIR/harvest-fidelity.py"; }
check "harvest-fidelity catches a serialVersionUID rewrite" 1 "FIDELITY:"

run_case() {
  mkfix; fidelity_fixture 1
  sed -i.bak "s/public class C /@jakarta.enterprise.context.ApplicationScoped public class C /;s/@jakarta.enterprise.context.ApplicationScoped/@ApplicationScoped/" src/main/java/m/C.java
  python3 "$HARNESS_DIR/harvest-fidelity.py"
}
check "harvest-fidelity skips converted (annotated) classes" 0 "GREEN"

# --- roadmap-lint (M2) -----------------------------------------------------

roadmap_fixture() { # $1 = briefs? (yes|no)
  mkdir -p briefs
  cat > roadmap.md <<'EOF'
# Modernization roadmap

## S01: Models and contracts
- scope: src/main/java/com/demo/model/ShoppingCart.java, src/test/java/com/demo/ShoppingCartServiceTest.java
- findings: javaee-pom-to-quarkus-00010
- depends: -
- deploy: false
- done: models compile on jakarta, legacy pricing assertions pinned
- rationale: highest fan-in per dependency-order.md — dependencies first

## S02: Services and surface
- scope: src/main/java/com/demo/service/CartService.java
- findings: springboot-web-to-quarkus-00000
- depends: S01
- deploy: true
- done: API serves, acceptance path returns 200
- rationale: dependents after dependencies
EOF
  if [ "$1" = "yes" ]; then
    for s in S01-models S02-services; do
      cat > "briefs/${s}.md" <<'EOF'
# Story
## Goal & position
x
## In scope
```java
import javax.ws.rs.Path;
```
## Out of scope
x
## Decided target shapes
x
## Contracts owned by this story
x
## Done-criteria
x
EOF
    done
  fi
  cat > inv.md <<'EOF'
## Summary by class
- recipe: 1 — javax-to-jakarta-import-00001
- rewrite: 1 — javaee-pom-to-quarkus-00010
- infer: 1 — springboot-web-to-quarkus-00000
EOF
}

run_case() { mkfix; roadmap_fixture yes; python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md; }
check "roadmap-lint accepts a complete roadmap" 0 "ROADMAP OK"

run_case() {
  mkfix; roadmap_fixture yes
  sed -i.bak "s/findings: springboot-web-to-quarkus-00000/findings: -/" roadmap.md
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint rejects an unowned mandatory finding" 1 "LINT:coverage"

run_case() {
  mkfix; roadmap_fixture yes
  sed -i.bak "s/depends: S01/depends: S09/" roadmap.md
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint rejects forward/unknown dependencies" 1 "LINT:order"

run_case() {
  mkfix; roadmap_fixture yes
  sed -i.bak "s/deploy: true/deploy: false/" roadmap.md
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint requires a deploying last story" 1 "LINT:deploy"

run_case() {
  mkfix; roadmap_fixture yes
  sed -i.bak "s|scope: src/main/java/com/demo/service/CartService.java|scope: run validation and report|" roadmap.md
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint rejects ceremonial stories" 1 "LINT:substance"

run_case() { mkfix; roadmap_fixture no; python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md; }
check "roadmap-lint requires briefs with code excerpts" 1 "LINT:briefs"

run_case() {
  mkfix; roadmap_fixture yes
  sed -i.bak "s/findings: javaee-pom-to-quarkus-00010/findings: javaee-pom-to-quarkus-00010, javax-to-jakarta-import-00001/" roadmap.md
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint rejects owning a recipe-executed finding" 1 "LINT:coverage"

run_case() {
  mkfix; roadmap_fixture yes
  sed -i.bak "s/## S02:/## S03:/; s/depends: S01/depends: S01/" roadmap.md
  mv briefs/S02-services.md briefs/S03-services.md
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint rejects non-contiguous story numbering" 1 "not contiguous"

run_case() {
  mkfix; roadmap_fixture yes
  sed -i.bak "s/findings: springboot-web-to-quarkus-00000/findings: springboot-web-to-quarkus-00000 (CartEndpoint instances)/" roadmap.md
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint rejects prose in the findings field" 1 "non-rule-id token"

# --- K3: non-mandatory decision table + adopt/defer marks ------------------
run_case() {
  mkfix
  printf '[{"violations": {
    "javax-to-jakarta-import-00001": {"category": "mandatory", "description": "javax", "incidents": [{"uri": "file:///a/B.java", "lineNumber": 1}]},
    "optional-logging-00010": {"category": "optional", "effort": 1, "description": "prefer structured logging", "incidents": [{"uri": "file:///a/B.java", "lineNumber": 2}, {"uri": "file:///a/C.java", "lineNumber": 3}]},
    "potential-cache-00020": {"category": "potential", "effort": 3, "description": "consider cache", "incidents": []}
  }}]' > f.json
  printf '## Windup rule joins\n\n| rule id prefix | class | decided target |\n|---|---|---|\n| javax-to-jakarta- | recipe:x | jakarta |\n' > M.md
  out=$(python3 "$HARNESS_DIR/findings-inventory.py" f.json M.md)
  echo "$out" | grep -q 'Non-mandatory findings (decide adopt' \
    && echo "$out" | grep -q 'optional-logging-00010' \
    && echo "$out" | grep -q 'potential-cache-00020' \
    && echo "$out" | grep -q 'non-mandatory: 2' \
    && echo k3-inv-ok
}
check "findings-inventory emits non-mandatory decision table (K3)" 0 "k3-inv-ok"

run_case() {
  mkfix; roadmap_fixture yes
  cat >> inv.md <<'EOF'
- non-mandatory: 1 — optional-logging-00010
EOF
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint rejects unmarked non-mandatory finding (K3)" 1 "LINT:non-mandatory"

run_case() {
  mkfix; roadmap_fixture yes
  cat >> inv.md <<'EOF'
- non-mandatory: 1 — optional-logging-00010
EOF
  cat >> roadmap.md <<'EOF'

## Non-mandatory decisions
- optional-logging-00010: defer (noise for this migration; not in scope)
EOF
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint accepts defer (reason) for non-mandatory (K3)" 0 "ROADMAP OK"

run_case() {
  mkfix; roadmap_fixture yes
  cat >> inv.md <<'EOF'
- non-mandatory: 1 — optional-logging-00010
EOF
  cat >> roadmap.md <<'EOF'

## Non-mandatory decisions
- optional-logging-00010: defer
EOF
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint rejects defer without reason (K3)" 1 "defer requires a reason"

# --- plan-lint story scoping (M3) ------------------------------------------
run_case() {
  mkfix
  plan_header > tasks.md
  printf '[{"violations": {"in-scope-rule-001": {"category": "mandatory", "incidents": []}, "other-story-rule-001": {"category": "mandatory", "incidents": []}}}]' > f.json
  printf '\nT-001 resolves in-scope-rule-001.\n' >> tasks.md
  python3 "$LINT" tasks.md f.json --findings-scope in-scope-rule-001
}
check "plan-lint story scope ignores other stories' findings" 0 "PLAN OK"

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

# 17b. V6 R6 — ExceptionMapper<Exception> forbidden
run_case() {
  sensor_fixture
  mkdir -p src/main/java/com/demo/rest
  printf 'import jakarta.ws.rs.ext.ExceptionMapper;\npublic class M implements ExceptionMapper<Exception> {}\n' \
    > src/main/java/com/demo/rest/ServiceExceptionMapper.java
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject ExceptionMapper<Exception> (V6 R6)" 1 "mapper"

# 17c. V6 R3 — fail-open acceptance catch→Response.ok
run_case() {
  sensor_fixture
  mkdir -p src/main/java/com/demo/rest
  cat > src/main/java/com/demo/rest/CartEndpoint.java <<'EOF'
public class CartEndpoint {
  public Object acceptanceCheck() {
    try { return null; }
    catch (Exception e) { return Response.ok("{}").build(); }
  }
}
EOF
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject fail-open acceptance catch→ok (V6 R3)" 1 "acceptance"

# 17d. V6 R5 — deploy story requires env preserve in k8s/
run_case() {
  sensor_fixture
  STORY_DEPLOY=true SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject CATALOG_ENDPOINT missing from k8s when deploy=true (V6 R5)" 1 "preserve"

# 17e. O-CATALOGDNS — short host in env without Service declaration
run_case() {
  sensor_fixture
  mkdir -p k8s src/main/resources/META-INF/resources src/main/java/com/demo/rest
  printf 'env:\n  - name: CATALOG_ENDPOINT\n    value: http://catalog:8080\n' > k8s/app.yaml
  printf '<html>ok</html>\n' > src/main/resources/META-INF/resources/index.html
  printf 'package com.demo.rest;\nimport jakarta.ws.rs.Path;\n@Path("/api/cart")\npublic class CartEndpoint {\n  @Path("acceptance-check")\n  public Object acceptanceCheck() { return null; }\n}\n' \
    > src/main/java/com/demo/rest/CartEndpoint.java
  STORY_DEPLOY=true SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject catalog host without Service (O-CATALOGDNS)" 1 "O-CATALOGDNS"

# 17e2. O-CATALOGSVC — Deployment named like the host must not satisfy Service check
run_case() {
  sensor_fixture
  mkdir -p k8s src/main/resources/META-INF/resources src/main/java/com/demo/rest
  cat > k8s/app.yaml <<'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: catalog
spec:
  template:
    spec:
      containers:
      - env:
        - name: CATALOG_ENDPOINT
          value: http://catalog:8080
EOF
  printf '<html>ok</html>\n' > src/main/resources/META-INF/resources/index.html
  printf 'package com.demo.rest;\nimport jakarta.ws.rs.Path;\n@Path("/api/cart")\npublic class CartEndpoint {\n  @Path("acceptance-check")\n  public Object acceptanceCheck() { return null; }\n}\n' \
    > src/main/java/com/demo/rest/CartEndpoint.java
  STORY_DEPLOY=true SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject Deployment-named host without Service (O-CATALOGSVC)" 1 "O-CATALOG"

# 17f. root index required when deploy=true
run_case() {
  sensor_fixture
  mkdir -p k8s src/main/java/com/demo/rest
  printf 'env:\n  - name: CATALOG_ENDPOINT\n    value: http://catalog:8080\n' > k8s/app.yaml
  printf 'apiVersion: v1\nkind: Service\nmetadata:\n  name: catalog\nspec:\n  ports: [{port: 8080}]\n' > k8s/catalog-svc.yaml
  printf 'package com.demo.rest;\nimport jakarta.ws.rs.Path;\n@Path("/api/cart")\npublic class CartEndpoint {\n  @Path("acceptance-check")\n  public Object acceptanceCheck() { return null; }\n}\n' \
    > src/main/java/com/demo/rest/CartEndpoint.java
  STORY_DEPLOY=true SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject missing META-INF index when deploy=true" 1 "index.html"

# --- V4 outer-loop instruments --------------------------------------------

roadmap_fixture() {
  cat <<'EOF'
# Modernization roadmap

## S01: Models
- scope: src/main/java/com/demo/model/Product.java, src/main/java/com/demo/model/ShoppingCart.java
- findings: removed-javaee-00010, localhost-http-00001
- depends: -
- deploy: false
- done: models converted

## S02: Hardening
- scope: src/main/java/com/demo/service/Impl.java
- findings: -
- depends: S01
- deploy: true
- done: hardened
EOF
}

# 43. roadmap parser: fields, multi-file scope, findings normalization
run_case() { mkfix; roadmap_fixture > r.md; python3 "$HARNESS_DIR/parse-roadmap.py" r.md; }
check "parse-roadmap emits pipe rows with normalized findings" 0 "S01|false|removed-javaee-00010,localhost-http-00001|src/main/java/com/demo/model/Product.java src/main/java/com/demo/model/ShoppingCart.java"

# 44. roadmap parser: 'findings: -' becomes the literal scope 'none'
run_case() { mkfix; roadmap_fixture > r.md; python3 "$HARNESS_DIR/parse-roadmap.py" r.md; }
check "parse-roadmap maps 'findings: -' to none" 0 "S02|true|none|src/main/java/com/demo/service/Impl.java"

# 45. dependency-order: same-package reference without import is an edge
#     (the S01 blind spot: ShoppingCart -> ShoppingCartItem)
run_case() {
  mkfix; mkdir -p src/main/java/com/demo/model
  printf 'package com.demo.model;\npublic class ShoppingCartItem { }\n' > src/main/java/com/demo/model/ShoppingCartItem.java
  printf 'package com.demo.model;\nimport java.util.List;\npublic class ShoppingCart { List<ShoppingCartItem> items; }\n' > src/main/java/com/demo/model/ShoppingCart.java
  python3 "$HARNESS_DIR/dependency-order.py" . | grep -E "^[0-9]+\." | head -1
}
check "dependency-order resolves same-package references (item before cart)" 0 "1. com.demo.model.ShoppingCartItem"

# 46-47. outer-loop and analyze scripts stay parseable (they gate runs)
run_case() { bash -n "$HARNESS_DIR/outer-loop.sh" && echo syntax-ok; }
check "outer-loop.sh parses" 0 "syntax-ok"
run_case() { bash -n "$HARNESS_DIR/analyze.sh" && bash -n "$HARNESS_DIR/supervisor.sh" && bash -n "$HARNESS_DIR/sensors.sh" && echo syntax-ok; }
check "analyze.sh, supervisor.sh, sensors.sh parse" 0 "syntax-ok"

# 48. fidelity normalizer collapses inner-punctuation spacing (V4 #5):
#     legacy `if ( x )` reformatted to `if (x)` is NOT drift.
fidelity_fixture() {
  mkfix
  mkdir -p migration/staging/src/main/java/com/demo src/main/java/com/demo
  printf 'package com.demo;\npublic class Svc {\n  void m(Object sci) {\n    if ( sci != null ) {\n      foo( sci, 1 );\n    }\n  }\n}\n' > migration/staging/src/main/java/com/demo/Svc.java
  printf 'package com.demo;\npublic class Svc {\n  void m(Object sci) {\n    if (sci != null) {\n      foo(sci, 1);\n    }\n  }\n}\n' > src/main/java/com/demo/Svc.java
}
run_case() { fidelity_fixture; python3 "$HARNESS_DIR/harvest-fidelity.py" migration/staging/src/main/java src/main/java; }
check "fidelity treats inner-paren spacing reformat as GREEN (not drift)" 0 "GREEN"

# 49. but a genuinely dropped line is still caught
run_case() {
  fidelity_fixture
  printf 'package com.demo;\npublic class Svc {\n  void m(Object sci) {\n  }\n}\n' > src/main/java/com/demo/Svc.java
  python3 "$HARNESS_DIR/harvest-fidelity.py" migration/staging/src/main/java src/main/java
}
check "fidelity still catches a genuinely dropped line" 1 "RED"

# 50-52. wiring-check: shared mutable state on a CDI singleton (#1)
singleton_hashmap() { # $1 = collection type
  mkfix; mkdir -p src/main/java/com/demo
  cat > src/main/java/com/demo/Svc.java <<JAVA
package com.demo;
import java.util.Map;
import java.util.$1;
import jakarta.enterprise.context.ApplicationScoped;
@ApplicationScoped
public class Svc {
  private Map<String,String> carts = new $1<>();
  public void add(String k){ carts.put(k, "v"); }
}
JAVA
}
run_case() { singleton_hashmap HashMap; python3 "$HARNESS_DIR/wiring-check.py" src/main/java; }
check "wiring-check flags singleton HashMap mutated outside init" 1 "non-concurrent field"
run_case() { singleton_hashmap ConcurrentHashMap; python3 "$HARNESS_DIR/wiring-check.py" src/main/java; }
check "wiring-check passes a ConcurrentHashMap singleton" 0 ""
run_case() {
  mkfix; mkdir -p src/main/java/com/demo
  cat > src/main/java/com/demo/Cfg.java <<'JAVA'
package com.demo;
import java.util.HashMap;
import java.util.Map;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.annotation.PostConstruct;
@ApplicationScoped
public class Cfg {
  private Map<String,String> t = new HashMap<>();
  @PostConstruct
  void load(){ t.put("a","1"); }
  public String get(String k){ return t.get(k); }
}
JAVA
  python3 "$HARNESS_DIR/wiring-check.py" src/main/java
}
check "wiring-check exempts populate-once in @PostConstruct" 0 ""

# 53-54. plan-lint §7-traceability: redesign class must cite its target shape
pl_profile() { printf '## 7. Class roles & target contract\n- `CartService` — REDESIGN\n  - target: ConcurrentHashMap, 404-on-missing GET.\n' > profile.md; }
run_case() {
  mkfix; pl_profile
  { echo "UI surface: waived (API-only service; no legacy web frontend)."
    printf '#### T-001: Convert CartService\n**Class**: infer\n- Target: src/main/java/com/demo/CartService.java with ConcurrentHashMap and 404-on-missing GET.\n'; } > tasks.md
  python3 "$LINT" tasks.md --profile profile.md
}
check "plan-lint passes a redesign task that cites its target shape" 0 "PLAN OK"
run_case() {
  mkfix; pl_profile
  { echo "UI surface: waived (API-only service; no legacy web frontend)."
    printf '#### T-001: Convert CartService\n**Class**: infer\n- Target: move src/main/java/com/demo/CartService.java to com.demo, keep methods.\n'; } > tasks.md
  python3 "$LINT" tasks.md --profile profile.md
}
check "plan-lint flags a redesign task missing its target shape" 1 "target-trace"

# 55. profile-rubric classification cross-check: CDI/JAX-RS class must be REDESIGN
run_case() {
  mkfix; printf '## 7. Class roles & target contract\n- `Product` — HARVEST\n' > profile.md
  mkdir -p legacy/com/demo
  printf 'package com.demo;\nimport org.springframework.stereotype.Service;\n@Service\npublic class OrderService {}\n' > legacy/com/demo/OrderService.java
  python3 "$HARNESS_DIR/profile-rubric.py" profile.md legacy
}
check "profile-rubric flags a @Service class not classified REDESIGN in §7" 1 "classroles"

# 56-57. §7 with ### HARVEST/REDESIGN subheadings must parse (V5 catch:
# section split truncated §7 at the first ### and false-flagged classroles)
sub7_profile() {
  cat <<'EOF'
## 7. Class roles & target contract
### HARVEST
- `Product` (src/main/java/com/demo/Product.java) — value object, faithful legacy pins.
### REDESIGN
- `CartService` (src/main/java/com/demo/CartService.java) — target: ConcurrentHashMap with compute(), GET returns 404 on missing, dedupe before pricing, validation and error mapping.
EOF
}
run_case() {
  mkfix; sub7_profile > profile.md
  mkdir -p legacy/com/demo
  printf 'package com.demo;\nimport jakarta.enterprise.context.ApplicationScoped;\n@ApplicationScoped\npublic class CartService {}\n' > legacy/com/demo/CartService.java
  out=$(python3 "$HARNESS_DIR/profile-rubric.py" profile.md legacy 2>&1); echo "$out" | grep -q "classroles.*CartService" && echo "CLASSROLES-FIRED" || echo "classroles-clean"
}
check "profile-rubric parses §7 with ### subheadings (REDESIGN under a heading)" 0 "classroles-clean"
run_case() {
  mkfix; sub7_profile > profile.md
  { echo "UI surface: waived (API-only)."
    printf '#### T-001: Convert CartService\n**Class**: infer\n- Move src/main/java/com/demo/CartService.java, keep methods.\n'; } > tasks.md
  python3 "$LINT" tasks.md --profile profile.md
}
check "plan-lint checks §7-subheading REDESIGN classes for target-trace" 1 "target-trace"

# 58-59. forbidden->preserve inversion (V5 T-011: getMockProducts read as
# a preserve contract — a fabrication seed)
run_case() {
  mkfix; printf 'forbidden:\n  - getMockProducts\n' > migration.yaml
  { echo "UI surface: waived."; printf '#### T-011: Catalog contract\n**Class**: infer\n- Maintain getMockProducts preservation requirement from migration.yaml.\n'; } > tasks.md
  python3 "$LINT" tasks.md
}
check "plan-lint flags a forbidden tripwire treated as preserve" 1 "forbidden-inverted"
run_case() {
  mkfix; printf 'forbidden:\n  - getMockProducts\n' > migration.yaml
  { echo "UI surface: waived."; printf '#### T-011: Remove fabrication\n**Class**: infer\n- Remove getMockProducts from src/main/java/com/demo/Svc.java entirely.\n'; } > tasks.md
  out=$(python3 "$LINT" tasks.md 2>&1); echo "$out" | grep -q forbidden-inverted && echo "FP-FIRED" || echo "remove-clean"
}
check "plan-lint does NOT flag a legitimate 'remove forbidden' task" 0 "remove-clean"

# 60-61. targetContract -> §7 hard-pin (V5: enabled flags written as soft
# prose, e.g. 'GET idempotent' without 404). Decisive token required.
ts_yaml() { printf 'targetContract:\n  getIdempotent: true\n  threadSafeState: true\npreserve:\n  - X\n' > migration.yaml; }
run_case() {
  mkfix; ts_yaml
  printf '## 7. Class roles & target contract\n**CartService** — REDESIGN (src/main/CartService.java) — target: ConcurrentHashMap with compute(); GET idempotent read-only.\n' > profile.md
  out=$(python3 "$HARNESS_DIR/profile-rubric.py" profile.md 2>&1); echo "$out" | grep -q "target-soft.*getIdempotent" && echo "soft-flagged" || echo "MISS"
}
check "profile-rubric flags a soft §7 target (getIdempotent without 404)" 0 "soft-flagged"
run_case() {
  mkfix; ts_yaml
  printf '## 7. Class roles & target contract\n**CartService** — REDESIGN (src/main/CartService.java) — target: ConcurrentHashMap with compute(); GET returns 404 on missing.\n' > profile.md
  out=$(python3 "$HARNESS_DIR/profile-rubric.py" profile.md 2>&1); echo "$out" | grep -q "target-soft" && echo "STILL-SOFT" || echo "hard-pinned"
}
check "profile-rubric passes a hard §7 target (404 decided)" 0 "hard-pinned"

# 62-63. later-story-class derivation (V5 T-004 guard): simple class names
# of stories AFTER the current one, stripping FQN/path and .java.
later_classes() { # $1=current SID ; reads $STORIES_FIX
  echo "$STORIES_FIX" | awk -F'|' -v cur="$1" 'seen{print $4} $1==cur{seen=1}' \
    | tr ', ' '\n' | sed -E 's/\.java$//; s#.*[./]##' | grep -E '^[A-Z][A-Za-z0-9]*$' | sort -u | tr '\n' ' '
}
run_case() {
  STORIES_FIX='S01|false|f|com.demo.model.Product
S02|false|f|com.demo.service.CatalogService
S03|true|f|com.demo.service.ShoppingCartServiceImpl, src/main/java/com/demo/rest/CartEndpoint.java'
  later_classes S01
}
check "later-classes for S01 lists later stories (FQN + path, .java stripped)" 0 "CartEndpoint CatalogService ShoppingCartServiceImpl"
run_case() {
  STORIES_FIX='S01|false|f|com.demo.model.Product
S02|true|f|com.demo.rest.CartEndpoint'
  out=$(later_classes S02); [ -z "$out" ] && echo "empty-ok" || echo "GOT:$out"
}
check "last story derives no later classes" 0 "empty-ok"

# 64. fidelity treats statement-continuation reflow as GREEN (V5 #1):
#     a multi-line `+` concat rewrapped (2 fragments/line vs 1) is not drift.
#     Sized so the reflowed fragments are <25% of the class — WITHOUT the
#     continuation-join this fixture is RED (missing lines under the skip
#     threshold); WITH it, the joined logical statements compare equal.
fidelity_reflow_fixture() {
  mkfix
  mkdir -p migration/staging/src/main/java/com/demo src/main/java/com/demo
  printf 'package com.demo;\npublic class C {\n  private int a;\n  private int b;\n  private int c;\n  public int getA() { return a; }\n  public int getB() { return b; }\n  public int getC() { return c; }\n  public String toString() {\n    return "C[a=" + a\n      + ",b=" + b\n      + ",c=" + c + "]";\n  }\n}\n' > migration/staging/src/main/java/com/demo/C.java
  printf 'package com.demo;\npublic class C {\n  private int a;\n  private int b;\n  private int c;\n  public int getA() { return a; }\n  public int getB() { return b; }\n  public int getC() { return c; }\n  public String toString() {\n    return "C[a=" + a + ",b=" + b\n      + ",c=" + c + "]";\n  }\n}\n' > src/main/java/com/demo/C.java
}
run_case() { fidelity_reflow_fixture; python3 "$HARNESS_DIR/harvest-fidelity.py" migration/staging/src/main/java src/main/java; }
check "fidelity treats +-continuation reflow as GREEN (V5 #1)" 0 "GREEN"

# 65-67. legacy-package-under-src/main guard (V5 #3): the package-map
#     inversion the factory build/sonar gate cannot catch.
package_fixture() { # a clean target-package tree with legacyPackage set
  mkfix
  mkdir -p src/main/java/com/demo
  printf 'package com.demo;\npublic class Svc { }\n' > src/main/java/com/demo/Svc.java
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
}
run_case() { package_fixture; SENSOR_ROOT="$FIX" bash "$SENSORS" package; }
check "package guard passes a clean target-package tree (V5 #3)" 0 "PACKAGE SCOPE GREEN"

run_case() { package_fixture; mkdir -p src/main/java/com/redhat/coolstore/model; printf 'package com.redhat.coolstore.model;\npublic class P { }\n' > src/main/java/com/redhat/coolstore/model/P.java; SENSOR_ROOT="$FIX" bash "$SENSORS" package; }
check "package guard rejects a legacy-package dir under src/main (V5 #3)" 1 "package"

run_case() { package_fixture; printf 'package com.redhat.coolstore;\npublic class Leak { }\n' > src/main/java/com/demo/Leak.java; SENSOR_ROOT="$FIX" bash "$SENSORS" package; }
check "package guard rejects a legacy package declaration in src/main (V5 #3)" 1 "package"

run_case() { package_fixture; mkdir -p "src/main/java/com.demo/model"; printf 'package com.demo.model;\npublic class Product { }\n' > "src/main/java/com.demo/model/Product.java"; SENSOR_ROOT="$FIX" bash "$SENSORS" package; }
check "package guard rejects a dotted package dir under src/main (V5 #3 gap)" 1 "package"

# 69. harvest-from-staging builds a '/'-joined dest (never a dotted dir) and
#     renames the package — the option-1 durable fix for the path confusion.
HARVEST_SH="$HARNESS_DIR/../skills/migration-harness/scripts/harvest-from-staging.sh"
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/com/redhat/coolstore/model
  printf 'package com.redhat.coolstore.model;\nimport com.redhat.coolstore.model.Foo;\npublic class Product { }\n' > migration/staging/src/main/java/com/redhat/coolstore/model/Product.java
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  bash "$HARVEST_SH" model/Product.java >/dev/null 2>&1
  { [ -f src/main/java/com/demo/model/Product.java ] && [ ! -d src/main/java/com.demo ] \
    && grep -q "package com.demo.model" src/main/java/com/demo/model/Product.java \
    && ! grep -rq "com.redhat.coolstore" src/main/java; } && echo "HARVEST OK slash-path renamed" || echo "FAIL"
}
check "harvest-from-staging writes '/'-joined dest + renames package (V5 opt1)" 0 "HARVEST OK"

# 70. parse-roadmap translates legacy scope paths to target (V5 scope-path bug:
#     the roadmap names classes by legacy path, but src/main is target-package,
#     so the scope sensor reverted legitimate harvests as out-of-scope).
run_case() {
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  printf '## S02: models\n- scope: src/main/java/com/redhat/coolstore/model/Product.java, src/main/java/com/redhat/coolstore/model/ShoppingCart.java\n- findings: -\n- deploy: false\n' > r.md
  python3 "$HARNESS_DIR/parse-roadmap.py" r.md
}
check "parse-roadmap translates legacy scope paths to target (V5 scope-path)" 0 "src/main/java/com/demo/model/Product.java src/main/java/com/demo/model/ShoppingCart.java"

# 71-72. brief-fidelity: methods/annotations a brief QUOTES as legacy must
#     exist in the legacy source (V5 run-4: M2 fabricated a JPA layer in S02
#     and an invented service API in S03).
brief_fab_fixture() { # $1 = fabricate? (yes|no)
  mkfix
  mkdir -p briefs legacy/src/main/java/com/x
  printf 'package com.x;\npublic class Svc {\n  @Deprecated\n  public void realMethod() { }\n}\n' > legacy/src/main/java/com/x/Svc.java
  printf '## S01: The service\n- scope: src/main/java/com/x/Svc.java\n- findings: -\n- depends: -\n- deploy: true\n- done: it works\n- rationale: only story\n' > roadmap.md
  cat > briefs/S01-svc.md <<'EOF'
# Story
## Goal & position
x
## In scope
- `src/main/java/com/x/Svc.java` — the service
  ```java
  __BODY__
  ```
## Out of scope
x
## Decided target shapes
x
## Contracts owned by this story
x
## Done-criteria
x
EOF
  if [ "$1" = "yes" ]; then
    sed -i.bak 's/__BODY__/@Entity public void fakeMethod() { }/' briefs/S01-svc.md
  else
    sed -i.bak 's/__BODY__/@Deprecated public void realMethod() { }/' briefs/S01-svc.md
  fi
  printf '## Summary by class\n- infer: 0 — \n' > inv.md
}
run_case() { brief_fab_fixture yes; python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md legacy; }
check "roadmap-lint flags a brief quoting a method/annotation absent from legacy (V5 M2)" 1 "LINT:fabrication"
run_case() {
  brief_fab_fixture no
  out=$(python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md legacy 2>&1)
  echo "$out" | grep -q "LINT:fabrication" && echo "FABRICATION-FOUND" || echo "no-fabrication-clean"
}
check "roadmap-lint does NOT flag a faithful brief quoting real legacy (V5 M2)" 0 "no-fabrication-clean"

# 73. plan-lint preserve slice stops at the next top-level key — a forbidden:
#     item below preserve: must NOT be read as a preserve item (V5 run-4:
#     getMockProducts over-read, failing every plan not naming it; bounced S03 M3).
run_case() {
  mkfix
  { plan_header; printf '\nT-002 also preserves CATALOG_ENDPOINT via the REST client url.\n'; } > tasks.md
  printf 'preserve:\n  - CATALOG_ENDPOINT\nforbidden:\n  - getMockProducts\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "plan-lint preserve slice does not sweep forbidden: into preserve (V5)" 0 "PLAN OK"

# 74. wiring check must NOT false-RED on a @RegisterRestClient interface that
#     has NO injector yet (interface-only story) — the pipefail empty-grep bug
#     that started the V5 run-4 S03 cascade (grep finds no injection point →
#     `| while … done || exit 1` exits 1 silently → empty-log RED).
run_case() {
  sensor_fixture
  mkdir -p src/main/java/com/demo/client
  printf 'package com.demo.client;\nimport org.eclipse.microprofile.rest.client.inject.RegisterRestClient;\n@RegisterRestClient\npublic interface CatalogClient {\n}\n' > src/main/java/com/demo/client/CatalogClient.java
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring passes a @RegisterRestClient interface with no injector (V5 pipefail false-RED)" 0 "STATIC CHECKS GREEN"

# 75. V6 P1.4 — constructor @RestClient qualifier required (no @Inject window)
run_case() {
  sensor_fixture
  mkdir -p src/main/java/com/demo/client src/main/java/com/demo/service
  printf 'package com.demo.client;\nimport org.eclipse.microprofile.rest.client.inject.RegisterRestClient;\n@RegisterRestClient\npublic interface CatalogClient {\n}\n' \
    > src/main/java/com/demo/client/CatalogClient.java
  printf 'package com.demo.service;\nimport com.demo.client.CatalogClient;\npublic class CartService {\n  public CartService(CatalogClient catalog) {}\n}\n' \
    > src/main/java/com/demo/service/CartService.java
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring rejects ctor CatalogClient without @RestClient (V6 P1.4)" 1 "wiring"

run_case() {
  sensor_fixture
  mkdir -p src/main/java/com/demo/client src/main/java/com/demo/service
  printf 'package com.demo.client;\nimport org.eclipse.microprofile.rest.client.inject.RegisterRestClient;\n@RegisterRestClient\npublic interface CatalogClient {\n}\n' \
    > src/main/java/com/demo/client/CatalogClient.java
  printf 'package com.demo.service;\nimport com.demo.client.CatalogClient;\nimport org.eclipse.microprofile.rest.client.inject.RestClient;\npublic class CartService {\n  public CartService(@RestClient CatalogClient catalog) {}\n}\n' \
    > src/main/java/com/demo/service/CartService.java
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring passes ctor CatalogClient with @RestClient (V6 P1.4)" 0 "STATIC CHECKS GREEN"

# 76. V6 R7 / P0c — handler-before-deploy when STORY_DEPLOY=true
run_case() {
  sensor_fixture
  mkdir -p k8s src/main/resources/META-INF/resources
  printf 'env:\n  - name: CATALOG_ENDPOINT\n    value: http://catalog:8080\n' > k8s/app.yaml
  printf 'apiVersion: v1\nkind: Service\nmetadata:\n  name: catalog\nspec:\n  ports: [{port: 8080}]\n' > k8s/catalog-svc.yaml
  printf '<html>ok</html>\n' > src/main/resources/META-INF/resources/index.html
  printf 'preserve:\n  - CATALOG_ENDPOINT\nacceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  STORY_DEPLOY=true SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject missing acceptance.path handler when deploy=true (V6 P0c)" 1 "acceptance"

run_case() {
  sensor_fixture
  mkdir -p k8s src/main/java/com/demo/rest src/main/resources/META-INF/resources
  printf 'env:\n  - name: CATALOG_ENDPOINT\n    value: http://catalog:8080\n' > k8s/app.yaml
  printf 'apiVersion: v1\nkind: Service\nmetadata:\n  name: catalog\nspec:\n  ports: [{port: 8080}]\n' > k8s/catalog-svc.yaml
  printf '<html>ok</html>\n' > src/main/resources/META-INF/resources/index.html
  printf 'preserve:\n  - CATALOG_ENDPOINT\nacceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  printf 'package com.demo.rest;\nimport jakarta.ws.rs.Path;\n@Path("/api/cart")\npublic class CartEndpoint {\n  @Path("acceptance-check")\n  public Object acceptanceCheck() { return null; }\n}\n' \
    > src/main/java/com/demo/rest/CartEndpoint.java
  STORY_DEPLOY=true SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors accept acceptance.path handler when deploy=true (V6 P0c)" 0 "STATIC CHECKS GREEN"

# 77. V6 R7 — ceremonial acceptance path cite without Java substance
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived.

#### T-001: Swap javax imports
**Class**: rewrite
- Mechanical jakarta rename across src/main/java sources.

#### T-002: Note acceptance
**Class**: infer
- Remember /api/cart/acceptance-check for later; no resource work this story.
EOF
  printf 'acceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "plan-lint rejects ceremonial acceptance path without @Path substance (V6 R7)" 1 "LINT:acceptance"

# 78. V6 P3.1 — §7 add() oracle must decide additive→qty 4
run_case() {
  mkfix
  printf '## 1. Purpose & domain\nCart service with pricing pinned by ShoppingCartServiceTest at src/test/java/X.java:1 and enough words to clear the thin bar for purpose domain section here.\n## 2. Components & relationships\nREST CartEndpoint at src/main/java/com/demo/rest/CartEndpoint.java depends on the service layer with enough words here for the thin bar.\n## 3. Integration surfaces\nCATALOG_ENDPOINT preserve at src/main/resources/application.properties:1 with enough words here for the thin bar check to pass cleanly.\n## 4. Behavioral contract sources\nLegacy suite pins totals at src/test/java/com/demo/ShoppingCartServiceTest.java:40 with enough words here for thin bar.\n## 5. Modernization surface\nPom moves to Quarkus per javaee-pom-to-quarkus-00010 with enough words here for the thin bar check.\n## 6. Domain boundaries\nSingle bounded context around the cart model at src/main/java/com/demo with enough words here for thin bar.\n## 7. Class roles & target contract\nShoppingCartServiceImpl is REDESIGN (src/main/java/com/demo/service/ShoppingCartServiceImpl.java) — add() is idempotent for duplicate lines.\n' > p.md
  out=$(python3 "$HARNESS_DIR/profile-rubric.py" p.md 2>&1); echo "$out" | grep -q "target-soft.*additive" && echo "add-oracle-soft" || echo "MISS:$out"
}
check "profile-rubric flags soft add() oracle without additive→4 (V6 P3.1)" 0 "add-oracle-soft"

run_case() {
  mkfix
  printf '## 1. Purpose & domain\nCart service with pricing pinned by ShoppingCartServiceTest at src/test/java/X.java:1 and enough words to clear the thin bar for purpose domain section here.\n## 2. Components & relationships\nREST CartEndpoint at src/main/java/com/demo/rest/CartEndpoint.java depends on the service layer with enough words here for the thin bar.\n## 3. Integration surfaces\nCATALOG_ENDPOINT preserve at src/main/resources/application.properties:1 with enough words here for the thin bar check to pass cleanly.\n## 4. Behavioral contract sources\nLegacy suite pins totals at src/test/java/com/demo/ShoppingCartServiceTest.java:40 with enough words here for thin bar.\n## 5. Modernization surface\nPom moves to Quarkus per javaee-pom-to-quarkus-00010 with enough words here for the thin bar check.\n## 6. Domain boundaries\nSingle bounded context around the cart model at src/main/java/com/demo with enough words here for thin bar.\n## 7. Class roles & target contract\nShoppingCartServiceImpl is REDESIGN (src/main/java/com/demo/service/ShoppingCartServiceImpl.java) — add() is additive: two add(cart,item,2) calls yield quantity 4 after dedupe.\n' > p.md
  out=$(python3 "$HARNESS_DIR/profile-rubric.py" p.md 2>&1); echo "$out" | grep -q "target-soft" && echo "STILL-SOFT" || echo "add-oracle-hard"
}
check "profile-rubric passes additive→quantity 4 add() oracle (V6 P3.1)" 0 "add-oracle-hard"

# 79. V6 abort — package sensor rejects partial rewrite com.demo.coolstore
run_case() {
  package_fixture
  mkdir -p src/main/java/com/demo/coolstore/service
  printf 'package com.demo.coolstore.service;\npublic class PromoService { }\n' \
    > src/main/java/com/demo/coolstore/service/PromoService.java
  SENSOR_ROOT="$FIX" bash "$SENSORS" package
}
check "package guard rejects wrong rewrite prefix com.demo.coolstore (V6 abort)" 1 "package"

# 80. V6 abort — plan-lint rejects Target paths under com.demo.coolstore
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived.

#### T-001: Port PromoService
**Class**: infer
- Target: src/main/java/com/demo/coolstore/service/PromoService.java CDI conversion.
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "plan-lint rejects com.demo.coolstore TARGET paths (V6 abort)" 1 "LINT:package"

# 81-82. V6 P2.4 — already-complete must not treat Convert/Port as class names
AC_PY="$HARNESS_DIR/already-complete.py"
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/service
  printf 'package com.demo.service;\npublic class X { }\n' > src/main/java/com/demo/service/X.java
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Convert PromoService to CDI constructor injection
**Class**: infer
- Convert PromoService from Spring @Autowired to CDI.
- Target: src/main/java/com/demo/service/PromoService.java
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-001; echo "rc=$?"
}
check "already-complete does not skip Convert CDI tasks (V6 P2.4 abort)" 0 "rc=1"

run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/rest
  # JerseyConfig already absent — removal task may skip.
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Remove JerseyConfig
**Class**: rewrite
- Delete src/main/java/com/demo/rest/JerseyConfig.java — must not exist after migration.
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  out=$(ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-002); echo "$out"
}
check "already-complete skips explicit Remove when .java absent (V6 P2.4)" 0 "absent:JerseyConfig"

# O-AC2 — preserve token in Story Scope Waivers must not skip unrelated tasks
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/model k8s
  printf 'package com.demo.model;\npublic class Product {}\n' > src/main/java/com/demo/model/Product.java
  printf 'env:\n  - name: CATALOG_ENDPOINT\n    value: http://catalog:8080\n' > k8s/app.yaml
  cat > tasks.md <<'EOF'
# Tasks
#### T-007: Package rename verification
**Class**: rewrite
**Goal**: Verify no legacy package references remain in src/main/java
**Acceptance**: Verification command returns 0; legacy package references eliminated

## Story Scope Waivers

**CATALOG_ENDPOINT Integration**: Explicitly waived - External catalog service.
EOF
  printf 'preserve:\n  - CATALOG_ENDPOINT\nlegacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-007; echo "rc=$?"
}
check "already-complete does not skip on waiver-only CATALOG_ENDPOINT (O-AC2)" 0 "rc=1"

run_case() {
  mkfix
  mkdir -p src/main/resources k8s
  printf 'quarkus.rest-client.catalog.url=${CATALOG_ENDPOINT}\n' > src/main/resources/application.properties
  printf 'env:\n  - name: CATALOG_ENDPOINT\n    value: http://catalog:8080\n' > k8s/app.yaml
  cat > tasks.md <<'EOF'
# Tasks
#### T-008: Wire CATALOG_ENDPOINT into application.properties
**Class**: rewrite
**Goal**: Preserve CATALOG_ENDPOINT via REST client url in application.properties
**Acceptance**: CATALOG_ENDPOINT present in src/main/resources/application.properties
EOF
  printf 'preserve:\n  - CATALOG_ENDPOINT\n' > migration.yaml
  out=$(ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-008); echo "$out"
}
check "already-complete still skips real preserve-subject tasks (O-AC2)" 0 "present:CATALOG_ENDPOINT"

# O-AC3 — class conversion mentioning CATALOG_ENDPOINT must not skip when .java missing
run_case() {
  mkfix
  mkdir -p src/main/resources k8s
  printf 'quarkus.rest-client."catalog-service".url=${CATALOG_ENDPOINT:http://localhost:8081}\n' \
    > src/main/resources/application.properties
  printf 'env:\n  - name: CATALOG_ENDPOINT\n    value: http://catalog:8080\n' > k8s/app.yaml
  cat > tasks.md <<'EOF'
# Tasks
#### T-006: CatalogService conversion with REST client
**Class**: infer
**Findings**: springboot-web-to-quarkus-00000 (1), demo-env-integration-00001 (1)
**Goal**: Convert CatalogService from FeignClient to Quarkus REST client; keep CATALOG_ENDPOINT
**Target design**:
- Legacy CatalogService → src/main/java/com/demo/service/CatalogService.java
- Configuration: Environment-driven CATALOG_ENDPOINT via configKey catalog-service
**Acceptance**: CatalogService compiles with @RegisterRestClient; CATALOG_ENDPOINT preserved
EOF
  printf 'preserve:\n  - CATALOG_ENDPOINT\n' > migration.yaml
  ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-006; echo "rc=$?"
}
check "already-complete does not skip missing CatalogService.java (O-AC3)" 0 "rc=1"

# O-T6d — characterization task must not mechan-commit main-only dirty tree
MM_PY="$HARNESS_DIR/mechan-match.py"
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-006: Add domain model characterization tests
**Class**: rewrite
**Goal**: Add characterization tests to verify domain model behavior
**Target design**:
- Test: src/test/java/com/demo/model/DomainModelTest.java
**Acceptance**: All domain model characterization tests pass
EOF
  printf 'src/main/java/com/demo/model/Product.java\n' | python3 "$MM_PY" tasks.md T-006; echo "rc=$?"
}
check "mechan-match refuses characterization without src/test (O-T6d)" 0 "rc=1"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-006: Add domain model characterization tests
**Class**: rewrite
**Goal**: Add characterization tests
**Target design**:
- Test: src/test/java/com/demo/model/DomainModelTest.java
**Acceptance**: tests pass
EOF
  printf 'src/test/java/com/demo/model/DomainModelTest.java\n' | python3 "$MM_PY" tasks.md T-006; echo "rc=$?"
}
check "mechan-match accepts characterization with src/test (O-T6d)" 0 "rc=0"

# 83. V6 abort — ceremonial status-map acceptance is rejected statically
run_case() {
  sensor_fixture
  mkdir -p src/main/java/com/demo/rest
  printf 'package com.demo.rest;\nimport java.util.Map;\nimport jakarta.ws.rs.Path;\n@Path("/api/cart")\npublic class AcceptanceEndpoint {\n  @Path("acceptance-check")\n  public Map<String,String> acceptanceCheck() {\n    return Map.of("status", "service_interfaces_ready", "story", "S02");\n  }\n}\n' \
    > src/main/java/com/demo/rest/AcceptanceEndpoint.java
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject ceremonial status-map acceptance (V6 abort)" 1 "acceptance"

# 84-86. V7 model routing — mechanical M4 via OpenCode/Qwen, not MiniMax
TP_PY="$HARNESS_DIR/task-packet.py"
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-010: Harvest PromoService from staging
**Class**: rewrite
**Goal**: Copy transformed PromoService into target package
**Findings**: spring-javaformat
**Acceptance**: src/main/java/com/demo/service/PromoService.java exists; mvn -q test
**Target design**: harvest migration/staging/.../PromoService.java → src/main/java/com/demo/service/
EOF
  python3 "$TP_PY" tasks.md T-010 qwen27b/qwen3-6-27b
}
check "task-packet.py builds rewrite packet for OpenCode worker (V7)" 0 "Class: rewrite"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-011: Convert CartService to CDI
**Class**: infer
**Goal**: CDI constructor injection for CartService
**Findings**: spring-di
**Acceptance**: CartService uses @Inject; tests pass
EOF
  out=$(python3 "$TP_PY" tasks.md T-011 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'Class: infer' && echo "$out" | grep -q 'qwen27b/qwen3-6-27b' && echo packet-ok
}
check "task-packet.py builds infer packet naming worker model (V7)" 0 "packet-ok"

run_case() {
  grep -q 'WORKER_FIRST' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'run_worker_task' "$HARNESS_DIR/supervisor.sh" \
    && ! grep -qE 'apply it directly per the EXECUTION' "$HARNESS_DIR/supervisor.sh" \
    && echo routing-ok
}
check "supervisor worker-first; no MiniMax apply-directly rewrite batch (V7)" 0 "routing-ok"

# 87-91. V8 polish bank (G-OK, G-FAKE, S-FND, S-SOFT, L-H1)
run_case() {
  sensor_fixture
  mkdir -p src/main/java/com/demo/rest
  printf 'package com.demo.rest;\nimport jakarta.ws.rs.GET;\nimport jakarta.ws.rs.Path;\n@Path("/api/cart/acceptance-check")\npublic class AcceptanceEndpoint {\n  @GET\n  public String check() { return "OK"; }\n}\n' \
    > src/main/java/com/demo/rest/AcceptanceEndpoint.java
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject ceremonial String/OK acceptance (G-OK)" 1 "acceptance"

run_case() {
  out=$(printf '%s\n' '[{"name":"Car"},{"name":"Bike"}]' | python3 "$HARNESS_DIR/acceptance-products.py")
  echo "count=$out"
}
check "acceptance-products rejects products without id/itemId (G-FAKE)" 0 "count=0"

run_case() {
  mkfix
  mkdir -p briefs
  # Minimal briefs with a legacy code fence so LINT:briefs doesn't dominate
  for s in S01-platform S02-rest; do
    cat > "briefs/${s}.md" <<'BEOF'
# brief
## In scope
```java
public void realMethod() { }
```
BEOF
  done
  cat > roadmap.md <<'EOF'
# Modernization roadmap
## S01: Platform
- scope: pom.xml
- findings:
- depends: -
- deploy: false
- done: build passes
- rationale: foundation
## S02: REST
- scope: src/main/java/com/demo/rest/CartEndpoint.java
- findings: jakarta-jaxrs-to-quarkus-00010
- depends: S01
- deploy: true
- done: API live
- rationale: surface
EOF
  printf '# inv\n- rewrite: 1 — jakarta-jaxrs-to-quarkus-00010\n' > inv.md
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint rejects empty findings field (S-FND)" 1 "findings field is empty"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Prepare for quality gate
**Class**: rewrite
- Prepare for the sonar gate; touch pom.xml if needed.
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "plan-lint rejects soft prepare-for tasks (S-SOFT)" 1 "S-SOFT"

run_case() {
  grep -q 'outer-loop-heartbeat' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'OUTER_LOOP_PLAIN' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'RUN COMPLETE' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'mode=SHIP_ONLY' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'waiting on MiniMax rate limit' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'try_mechan_commit' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-T6b' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'git reset -q -- .hermes' "$HARNESS_DIR/supervisor.sh" \
    && echo polish-ok
}
check "outer-loop/supervisor carry V8 polish hooks (L-H1/L-P1/L-R1/L-SHIPLOG/O-T6/O-T6b)" 0 "polish-ok"

# G-PLACE: placeholder/ceremonial unit tests must RED (V8 S02 T-005 abort)
run_case() {
  sensor_fixture
  mkdir -p src/test/java/com/demo
  cat > src/test/java/com/demo/PlaceholderTest.java <<'EOF'
package com.demo;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;
class PlaceholderTest {
  @Test void ceremonial() { assertThat(true).isTrue(); }
}
EOF
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject assertThat(true) placeholder tests (G-PLACE)" 1 "G-PLACE"

# S-CHAR: model harvest plan without src/test paths
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Product Model Harvest
**Class**: rewrite
- Destination: `src/main/java/com/demo/model/Product.java`
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "plan-lint rejects model harvest with no src/test tasks (S-CHAR)" 1 "S-CHAR"

run_case() {
  grep -q 'L-M5e' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'm5-evaluate-preflight' "$HARNESS_DIR/supervisor.sh" \
    && echo m5e-ok
}
check "supervisor carries L-M5e evaluate preflight honesty check" 0 "m5e-ok"

run_case() {
  grep -q 'O-ESCW' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'try_worker_verified_noop' "$HARNESS_DIR/supervisor.sh" \
    && echo escw-ok
}
check "supervisor carries O-ESCW worker-verified noop (no MiniMax)" 0 "escw-ok"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Create acceptance endpoint placeholder
**Class**: rewrite
- Destination: `src/main/java/com/demo/AcceptanceEndpoint.java`
- Acceptance: endpoint returns simple status response for web surface validation
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "plan-lint rejects ceremonial acceptance placeholder tasks (S-AC1)" 1 "S-AC1"

run_case() {
  # G-AC3: acceptance_ship_contract invoked inside milestone_sensor body
  awk '/^milestone_sensor\(\)/,/^sonar_check\(\)|^fidelity_check\(\)|^preflight\(\)/' "$SENSORS" \
    | grep -q 'acceptance_ship_contract' && echo gac3-ok
}
check "milestone sensor runs acceptance_ship_contract (G-AC3)" 0 "gac3-ok"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Create service package structure
**Class**: rewrite
- Destination: `src/main/java/com/demo/service/`
- Acceptance: directory exists for service classes
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "plan-lint rejects package-structure task without .gitkeep (S-PKGDIR)" 1 "S-PKGDIR"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Create service package structure
**Class**: rewrite
- Destination: `src/main/java/com/demo/service/.gitkeep`
- Acceptance: package directory trackable via .gitkeep
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "plan-lint accepts package-structure task with .gitkeep (S-PKGDIR)" 0 "PLAN OK"

run_case() {
  grep -q 'sensor-fix-mode' "$SENSORS" \
    && grep -q 'O-SFIXLOOP' "$SENSORS" \
    && grep -q 's1066-collapse' "$HARNESS_DIR/style-autofix.sh" \
    && test -f "$HARNESS_DIR/s1066-collapse.py" \
    && grep -q 'app_dirt' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-M3KILL' "$HARNESS_DIR/outer-loop.sh" \
    && test -f "$HARNESS_DIR/freeze-harness.sh" \
    && echo v9-bank-ok
}
check "V9 bank wiring O-SFIXLOOP/S1066/ESCW2/M3KILL/KILLREL present" 0 "v9-bank-ok"

run_case() {
  grep -q 'O-DEBTFRZ' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'debt-freeze' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'debt-freeze' "$HARNESS_DIR/outer-loop.sh" \
    && echo debtfrz-ok
}
check "O-DEBTFRZ supervisor freeze + outer-loop hold" 0 "debtfrz-ok"

run_case() {
  local exec_md="$HARNESS_DIR/../skills/migration-harness/EXECUTION.md"
  grep -q 'O-OCERR' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'refuse_red_task_commit' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SFIXSCOPE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-RESTJSON' "$exec_md" \
    && echo ocerr-rest-ok
}
check "O-OCERR + RestAssured EXECUTION + O-SFIXSCOPE reset" 0 "ocerr-rest-ok"

run_case() {
  mkfix
  mkdir -p src/main/java/com/demo
  cat > src/main/java/com/demo/N.java <<'EOF'
package com.demo;
class N {
  void t(boolean a, boolean b) {
    if (a) {
      if (b) {
        System.out.println(1);
      }
    }
  }
}
EOF
  python3 "$HARNESS_DIR/s1066-collapse.py" "$PWD" >/tmp/s1066.out
  grep -q 'a && b' src/main/java/com/demo/N.java && echo collapse-ok
}
check "s1066-collapse collapses nested if (O-S1066)" 0 "collapse-ok"

run_case() {
  mkfix
  touch /tmp/sensor-fix-mode
  out=$(SENSOR_ROOT="$PWD" bash "$SENSORS" milestone 2>&1) || rc=$?
  rm -f /tmp/sensor-fix-mode
  rc=${rc:-0}
  echo "$out"
  [ "$rc" -eq 2 ] && echo refused-ok
}
check "sensors.sh milestone refused in sensor-fix mode (O-SFIXLOOP)" 0 "refused-ok"

ESCW_PY="$HARNESS_DIR/escw-eligible.py"
run_case() {
  mkfix
  mkdir -p src/test/java/com/demo/model
  echo 'class DomainModelTest {}' > src/test/java/com/demo/model/DomainModelTest.java
  cat > tasks.md <<'EOF'
# Tasks
#### T-008: Add service layer characterization tests
**Class**: infer
- Characterization tests for PromoService / ShippingService under src/test/java/com/demo/service/
EOF
  ALREADY_COMPLETE_ROOT="$PWD" python3 "$ESCW_PY" tasks.md T-008; echo rc=$?
}
check "escw-eligible refuses service characterization without service tests (O-ESCW3)" 0 "need-service-tests"

run_case() {
  mkfix
  mkdir -p src/test/java/com/demo/service
  echo 'class PromoServiceTest {}' > src/test/java/com/demo/service/PromoServiceTest.java
  cat > tasks.md <<'EOF'
# Tasks
#### T-008: Add service layer characterization tests
**Class**: infer
- Characterization tests for service layer under src/test/java/com/demo/service/
EOF
  ALREADY_COMPLETE_ROOT="$PWD" python3 "$ESCW_PY" tasks.md T-008
}
check "escw-eligible allows service characterization when service tests exist (O-ESCW3)" 0 "tests-present"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Convert CartEndpoint from Spring REST to Quarkus JAX-RS
**Class**: infer
**Goal**: Modernize CartEndpoint
**Target design**:
- → `src/main/java/com/demo/rest/CartEndpoint.java`
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-001 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'CartEndpoint.java' \
    && echo "$out" | grep -q 'O-TGTNAME' \
    && echo "$out" | grep -q 'O-HERMNEST' \
    && echo tgtname-ok
}
check "task-packet mandates Target basename and no .hermes commit (O-TGTNAME/O-HERMNEST)" 0 "tgtname-ok"

run_case() {
  grep -q 'scrub_hermes_from_git' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-HERMNEST' "$HARNESS_DIR/supervisor.sh" \
    && echo hermnest-ok
}
check "supervisor carries O-HERMNEST scrub_hermes_from_git" 0 "hermnest-ok"

# --- K1: incident-file ownership in plan-lint ------------------------------
run_case() {
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Harvest CartService
**Class**: rewrite
**Findings**: javax-to-jakarta-import-00001
**Goal**: harvest service
- Target: → `src/main/java/com/demo/service/CartService.java` from staging
EOF
  cat > f.json <<'EOF'
[{"violations": {"javax-to-jakarta-import-00001": {
  "category": "mandatory",
  "incidents": [
    {"uri": "file:///projects/legacy/src/main/java/com/redhat/coolstore/service/CartService.java", "lineNumber": 3}
  ]
}}}]
EOF
  python3 "$LINT" tasks.md f.json
}
check "plan-lint accepts incident owned via target path (K1)" 0 "PLAN OK"

run_case() {
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Mention rule only
**Class**: rewrite
**Findings**: javax-to-jakarta-import-00001
**Goal**: rename imports somewhere
- Touches src/main/java/com/demo/service/Other.java
EOF
  cat > f.json <<'EOF'
[{"violations": {"javax-to-jakarta-import-00001": {
  "category": "mandatory",
  "incidents": [
    {"uri": "file:///projects/legacy/src/main/java/com/redhat/coolstore/service/CartService.java", "lineNumber": 3}
  ]
}}}]
EOF
  python3 "$LINT" tasks.md f.json
}
check "plan-lint rejects unowned incident file (K1)" 1 "LINT:incident-unowned"

run_case() {
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Harvest CartService
**Class**: rewrite
- Target: → `src/main/java/com/demo/service/CartService.java`

#### T-002: Also touch CartService
**Class**: rewrite
- Also edits src/main/java/com/demo/service/CartService.java for imports
EOF
  cat > f.json <<'EOF'
[{"violations": {"javax-to-jakarta-import-00001": {
  "category": "mandatory",
  "incidents": [
    {"uri": "file:///projects/legacy/src/main/java/com/redhat/coolstore/service/CartService.java", "lineNumber": 3}
  ]
}}}]
EOF
  python3 "$LINT" tasks.md f.json
}
check "plan-lint rejects incident file claimed by two tasks (K1)" 1 "LINT:incident-conflict"

run_case() {
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Fold OldHelper into CartService
**Class**: infer
**Goal**: absorb helper
**Absorbs**: src/main/java/com/redhat/coolstore/rest/OldHelper.java
- Target: → `src/main/java/com/demo/service/CartService.java`
EOF
  cat > f.json <<'EOF'
[{"violations": {"custom-delete-00001": {
  "category": "mandatory",
  "incidents": [
    {"uri": "file:///projects/legacy/src/main/java/com/redhat/coolstore/rest/OldHelper.java", "lineNumber": 1}
  ]
}}}]
EOF
  python3 "$LINT" tasks.md f.json
}
check "plan-lint accepts Absorbs: for deleted/merged incident files (K1)" 0 "PLAN OK"

# K1-OWN: Out of scope path must NOT count as ownership
run_case() {
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Convert Alpha
**Class**: rewrite
**Findings**: r-mand-00001
**Goal**: convert Alpha
**Target design**: → `src/main/java/com/demo/Alpha.java`
**Out of scope:** do NOT touch src/main/java/com/demo/Beta.java — later story
EOF
  cat > f.json <<'EOF'
[{"violations": {"r-mand-00001": {"category": "mandatory", "incidents": [
  {"uri": "file:///projects/legacy/src/main/java/com/redhat/coolstore/Alpha.java", "lineNumber": 1},
  {"uri": "file:///projects/legacy/src/main/java/com/redhat/coolstore/Beta.java", "lineNumber": 2}
]}}}]
EOF
  python3 "$LINT" tasks.md f.json
}
check "plan-lint Out-of-scope path does not own incident (K1-OWN)" 1 "LINT:incident-unowned"

# K1-CONF: disclaimer must not manufacture conflict with real owner
run_case() {
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Convert Beta
**Class**: rewrite
**Findings**: r-mand-00001
**Goal**: convert Beta
- Target: → `src/main/java/com/demo/Beta.java`

#### T-002: Characterize Alpha
**Class**: infer
**Goal**: pin Alpha
**Out of scope:** src/main/java/com/demo/Beta.java is owned by T-001
- Target: → `src/test/java/com/demo/AlphaTest.java`
EOF
  cat > f.json <<'EOF'
[{"violations": {"r-mand-00001": {"category": "mandatory", "incidents": [
  {"uri": "file:///projects/legacy/src/main/java/com/redhat/coolstore/Beta.java", "lineNumber": 2}
]}}}]
EOF
  python3 "$LINT" tasks.md f.json
}
check "plan-lint OOS disclaimer does not conflict with real owner (K1-CONF)" 0 "PLAN OK"

# --- K2: Analysis evidence from mta-findings.json in task packets ----------
run_case() {
  mkfix
  mkdir -p migration
  cat > migration/mta-findings.json <<'EOF'
[{"violations": {
  "javax-to-jakarta-import-00001": {
    "category": "mandatory",
    "description": "Replace javax.* with jakarta.*",
    "incidents": [
      {
        "uri": "file:///projects/legacy/src/main/java/com/demo/CartService.java",
        "lineNumber": 12,
        "message": "Import javax.inject.Inject must become jakarta.inject.Inject",
        "codeSnip": "import javax.inject.Inject;"
      },
      {
        "uri": "file:///projects/legacy/src/main/java/com/demo/CartEndpoint.java",
        "lineNumber": 8,
        "message": "Import javax.ws.rs.Path must become jakarta.ws.rs.Path",
        "codeSnip": "import javax.ws.rs.Path;"
      }
    ]
  },
  "other-rule-99999": {
    "category": "mandatory",
    "description": "unrelated",
    "incidents": [{"uri": "file:///a/B.java", "lineNumber": 1, "message": "noise"}]
  }
}}]
EOF
  cat > tasks.md <<'EOF'
# Tasks
#### T-020: Swap javax imports
**Class**: rewrite
**Goal**: Mechanical jakarta rename
**Findings**: javax-to-jakarta-import-00001
**Acceptance**: no javax.inject left; mvn -q test
EOF
  out=$(python3 "$TP_PY" tasks.md T-020 qwen27b/qwen3-6-27b migration/mta-findings.json)
  echo "$out" | grep -q 'Analysis evidence (from MTA' \
    && echo "$out" | grep -q 'javax-to-jakarta-import-00001 at' \
    && echo "$out" | grep -q 'Import javax.inject.Inject must become jakarta.inject.Inject' \
    && echo "$out" | grep -q 'import javax.inject.Inject;' \
    && ! echo "$out" | grep -q 'other-rule-99999' \
    && echo k2-ok
}
check "task-packet injects MTA analysis evidence for Findings ids (K2)" 0 "k2-ok"

run_case() {
  mkfix
  mkdir -p migration
  # 8 incidents — packet must hard-cap at 6
  python3 - <<'PY'
import json
incs = []
for i in range(8):
    incs.append({
        "uri": f"file:///projects/legacy/src/main/java/com/demo/F{i}.java",
        "lineNumber": i + 1,
        "message": f"incident message number {i} " + ("x" * 500),
        "codeSnip": f"code snip {i} " + ("y" * 500),
    })
json.dump([{"violations": {"rule-cap-00001": {
    "category": "mandatory",
    "description": "cap test",
    "incidents": incs,
}}}], open("migration/mta-findings.json", "w"))
PY
  cat > tasks.md <<'EOF'
# Tasks
#### T-021: Cap evidence
**Class**: infer
**Findings**: rule-cap-00001
**Goal**: prove hard caps
EOF
  out=$(python3 "$TP_PY" tasks.md T-021 qwen27b/qwen3-6-27b migration/mta-findings.json)
  n=$(echo "$out" | grep -c 'rule-cap-00001 at' || true)
  # ≤6 incidents; each message/code field trimmed to ≤400 (ellipsis allowed).
  # Combined content budget (K2-CAP) may render fewer than 6 headers.
  long=$(echo "$out" | grep -E 'message:|code:' | awk 'length($0)>420 {print; exit 1}')
  [ "$n" -le 6 ] && [ "$n" -ge 1 ] && [ -z "${long:-}" ] && echo k2-cap-ok
}
check "task-packet hard-caps evidence at ≤6×400 chars (K2)" 0 "k2-cap-ok"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-022: No findings file
**Class**: infer
**Findings**: some-rule-00001
**Goal**: omit evidence section when json absent
EOF
  out=$(python3 "$TP_PY" tasks.md T-022 qwen27b/qwen3-6-27b)
  ! echo "$out" | grep -q 'Analysis evidence' && echo k2-absent-ok
}
check "task-packet omits evidence when mta-findings.json absent (K2)" 0 "k2-absent-ok"

run_case() {
  grep -q 'Analysis evidence' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'Worker packet (authoritative' "$HARNESS_DIR/supervisor.sh" \
    && echo k2-esc-ok
}
check "supervisor escalation prompt carries K2 packet/evidence" 0 "k2-esc-ok"

# K2-RR: round-robin — later Findings rule must appear when first rule is huge
run_case() {
  mkfix
  mkdir -p migration
  python3 - <<'PY'
import json
incs_a = [{"uri": f"file:///a/A{i}.java", "lineNumber": i, "message": f"A{i}", "codeSnip": "x"} for i in range(8)]
incs_b = [{"uri": "file:///b/B.java", "lineNumber": 1, "message": "RULE-B-REMEDIATION", "codeSnip": "y"}]
json.dump([{
  "violations": {
    "rule-aaa-00001": {"category": "mandatory", "description": "A", "incidents": incs_a},
    "rule-bbb-00002": {"category": "mandatory", "description": "B", "incidents": incs_b},
  }
}], open("migration/mta-findings.json", "w"))
PY
  cat > tasks.md <<'EOF'
# Tasks
#### T-030: Two findings
**Class**: infer
**Findings**: rule-aaa-00001, rule-bbb-00002
**Goal**: both rules get evidence
EOF
  out=$(python3 "$TP_PY" tasks.md T-030 qwen27b/qwen3-6-27b migration/mta-findings.json)
  echo "$out" | grep -q 'rule-bbb-00002' \
    && echo "$out" | grep -q 'RULE-B-REMEDIATION' \
    && echo k2-rr-ok
}
check "task-packet round-robins evidence across Findings rules (K2-RR)" 0 "k2-rr-ok"

# K2-MATCH: short prose token must not pull unrelated rules
run_case() {
  mkfix
  mkdir -p migration
  cat > migration/mta-findings.json <<'EOF'
[{"violations": {
  "springboot-web-to-quarkus-00000": {
    "category": "mandatory",
    "description": "springboot",
    "incidents": [{"uri": "file:///a/S.java", "lineNumber": 1, "message": "SPRINGBOOT-HIT", "codeSnip": "x"}]
  }
}}]
EOF
  cat > tasks.md <<'EOF'
# Tasks
#### T-031: Loose token
**Class**: infer
**Findings**: springboot
**Goal**: must not match via bare substring
EOF
  out=$(python3 "$TP_PY" tasks.md T-031 qwen27b/qwen3-6-27b migration/mta-findings.json)
  ! echo "$out" | grep -q 'Analysis evidence' && echo k2-match-ok
}
check "task-packet rejects short Findings token substring match (K2-MATCH)" 0 "k2-match-ok"

# K2-CAP: combined message+code content ≤ 2400
run_case() {
  mkfix
  mkdir -p migration
  python3 - <<'PY'
import json
incs = []
for i in range(6):
    incs.append({
        "uri": f"file:///a/F{i}.java",
        "lineNumber": i + 1,
        "message": "m" * 400,
        "codeSnip": "c" * 400,
    })
json.dump([{"violations": {"rule-cap-00002": {
    "category": "mandatory", "description": "cap", "incidents": incs,
}}}], open("migration/mta-findings.json", "w"))
PY
  cat > tasks.md <<'EOF'
# Tasks
#### T-032: Content budget
**Class**: infer
**Findings**: rule-cap-00002
**Goal**: combined content budget
EOF
  out=$(python3 "$TP_PY" tasks.md T-032 qwen27b/qwen3-6-27b migration/mta-findings.json)
  evid=$(echo "$out" | sed -n '/^Analysis evidence/,/^Target Design:/p' | sed '$d')
  # Sum lengths of message:/code: payloads only
  content=$(echo "$evid" | python3 -c '
import sys,re
n=0
for ln in sys.stdin:
    m=re.match(r"\s+(message|code):\s*(.*)$", ln)
    if m: n+=len(m.group(2))
print(n)
')
  [ "$content" -le 2400 ] && echo "k2-cap2-ok content=$content"
}
check "task-packet enforces 2400-char combined evidence budget (K2-CAP)" 0 "k2-cap2-ok"

echo "----"
echo "$PASS/$N passed"
[ "$FAIL" -eq 0 ]

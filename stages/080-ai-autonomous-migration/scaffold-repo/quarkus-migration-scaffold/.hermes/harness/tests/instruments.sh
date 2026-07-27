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
run_case() { bash -n "$HARNESS_DIR/analyze.sh" && bash -n "$HARNESS_DIR/supervisor.sh" && echo syntax-ok; }
check "analyze.sh and supervisor.sh parse" 0 "syntax-ok"

echo "----"
echo "$PASS/$N passed"
[ "$FAIL" -eq 0 ]

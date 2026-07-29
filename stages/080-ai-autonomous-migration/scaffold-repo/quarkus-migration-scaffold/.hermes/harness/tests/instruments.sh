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

echo "----"
echo "$PASS/$N passed"
[ "$FAIL" -eq 0 ]

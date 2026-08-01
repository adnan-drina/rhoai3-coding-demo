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
# O-INSTQUAL (instrument-quality standard): prefer behavioural fixtures
# (fixture → run helper/sensor → assert outcome) over name-greps of
# supervisor.sh. Name-greps may remain as wiring smoke checks alongside a
# behavioural case for the same ID — never as the sole proof.
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
    # Emit TAP `not ok` so `grep '^not ok'` catches red suites (R-216).
    FAIL=$((FAIL+1)); echo "not ok $N - $name"
    echo "FAIL $N - $name (rc=$rc want=$want_rc; output below)"
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

# O-ACCEPTGEN — collection key from migration.yaml (petclinic-shaped vetList)
run_case() {
  mkfix
  printf 'acceptance:\n  path: /api/vets/acceptance-check\n  collection: vetList\n  service: VetService\n  itemType: Vet\n' > migration.yaml
  printf '%s\n' '{"vetList":[{"id":"1"},{"id":"2"}]}' | python3 "$HARNESS_DIR/acceptance-products.py" --yaml migration.yaml
}
check "acceptance-products counts vetList from migration.yaml (O-ACCEPTGEN)" 0 "2"

run_case() {
  mkfix
  printf 'acceptance:\n  path: /api/vets/acceptance-check\n  collection: vetList\n' > migration.yaml
  out=$(printf '%s\n' '{"products":[{"id":"1"}]}' | python3 "$HARNESS_DIR/acceptance-products.py" --yaml migration.yaml)
  [ "$out" = "0" ]
}
check "acceptance-products ignores products key when collection is vetList (O-ACCEPTGEN)" 0 ""

# Poll 81 / B1 — REST petclinic: bare JSON array (not {vetList:[…]})
run_case() {
  mkfix
  printf 'acceptance:\n  path: /petclinic/api/vets\n  collection: _array\n  getter: getAllVets\n  service: ClinicService\n  itemType: VetDto\n  idFields: [id]\n' > migration.yaml
  printf '%s\n' '[{"id":1,"firstName":"James","lastName":"Carter"},{"id":2,"firstName":"Helen","lastName":"Leary"}]' \
    | python3 "$HARNESS_DIR/acceptance-products.py" --yaml migration.yaml
}
check "acceptance-products counts bare vet array (Poll 81 B1)" 0 "2"

run_case() {
  mkfix
  printf 'acceptance:\n  path: /petclinic/api/vets\n  collection: _array\n  getter: getAllVets\n' > migration.yaml
  out=$(printf '%s\n' '{"vetList":[{"id":1}]}' | python3 "$HARNESS_DIR/acceptance-products.py" --yaml migration.yaml)
  [ "$out" = "0" ]
}
check "acceptance-products rejects vetList wrapper when collection is _array (Poll 81 B1)" 0 ""

# R-83 P2 / O-DEVDBURL — default JDBC host/db embed PROJECT_KEY when yaml omits db*
run_case() {
  mkfix
  printf 'acceptance:\n  path: /api/x\n  needsDatabase: true\n' > migration.yaml
  PROJECT_KEY=petclinic
  eval "$(python3 "$HARNESS_DIR/acceptance_config.py" --yaml migration.yaml --export-shell)"
  DB_SERVICE="${ACC_DB_SERVICE:-${PROJECT_KEY}-postgres}"
  DB_NAME="${ACC_DB_NAME:-${PROJECT_KEY}}"
  url="jdbc:postgresql://${DB_SERVICE}.${PROJECT_KEY}-dev.svc:5432/${DB_NAME}"
  echo "$url" | grep -q 'petclinic-postgres.petclinic-dev.svc:5432/petclinic' \
    && ! grep -qE 'coolstore-postgres' "$HARNESS_DIR/sensors.sh" \
    && echo devdburl-ok
}
check "DEV_DB_URL defaults embed PROJECT_KEY-postgres (O-DEVDBURL / R-83 P2)" 0 "devdburl-ok"

run_case() {
  mkfix
  printf 'acceptance:\n  path: /api/x\n  dbService: myapp-postgres\n  dbName: mydb\n' > migration.yaml
  PROJECT_KEY=petclinic
  eval "$(python3 "$HARNESS_DIR/acceptance_config.py" --yaml migration.yaml --export-shell)"
  DB_SERVICE="${ACC_DB_SERVICE:-${PROJECT_KEY}-postgres}"
  DB_NAME="${ACC_DB_NAME:-${PROJECT_KEY}}"
  [ "$DB_SERVICE" = "myapp-postgres" ] && [ "$DB_NAME" = "mydb" ] && echo dboverride-ok
}
check "acceptance dbService/dbName override PROJECT_KEY defaults (O-DEVDBURL)" 0 "dboverride-ok"

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

# O-FIDELITYVALID — Spring BindingResult → Jakarta ConstraintViolation is conversion
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/m src/main/java/m
  cat > migration/staging/src/main/java/m/BindingErrorsResponse.java <<'EOF'
package m;
import org.springframework.validation.BindingResult;
import org.springframework.validation.FieldError;
public class BindingErrorsResponse {
  public void addAllErrors(BindingResult bindingResult){
    for(FieldError fieldError : bindingResult.getFieldErrors()){
      error.setObjectName(fieldError.getObjectName());
    }
  }
}
EOF
  cat > src/main/java/m/BindingErrorsResponse.java <<'EOF'
package m;
import jakarta.validation.ConstraintViolation;
import java.util.List;
public class BindingErrorsResponse {
  public void addAllErrors(List<ConstraintViolation<?>> violations){
    for(ConstraintViolation<?> violation : violations){
      error.setObjectName(violation.getRootBeanClass().getSimpleName());
    }
  }
}
EOF
  python3 "$HARNESS_DIR/harvest-fidelity.py"; echo "rc=$?"
}
check "harvest-fidelity skips Spring→Jakarta validation conversion (O-FIDELITYVALID)" 0 "GREEN"

# O-FIDELITYDAO — Spring DAO throws + PropertyComparator drops are approved
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/m src/main/java/m
  cat > migration/staging/src/main/java/m/OwnerRepository.java <<'EOF'
package m;
import org.springframework.dao.DataAccessException;
public interface OwnerRepository {
  void save(Owner owner) throws DataAccessException;
}
EOF
  cat > src/main/java/m/OwnerRepository.java <<'EOF'
package m;
public interface OwnerRepository {
  void save(Owner owner);
}
EOF
  cat > migration/staging/src/main/java/m/Owner.java <<'EOF'
package m;
import org.springframework.beans.support.MutableSortDefinition;
import org.springframework.beans.support.PropertyComparator;
import java.util.*;
public class Owner {
  public List<Pet> getPets() {
    List<Pet> sortedPets = new ArrayList<>(getPetsInternal());
    PropertyComparator.sort(sortedPets, new MutableSortDefinition("name", true, true));
    return sortedPets;
  }
}
EOF
  cat > src/main/java/m/Owner.java <<'EOF'
package m;
import java.util.*;
public class Owner {
  public List<Pet> getPets() {
    List<Pet> sortedPets = new ArrayList<>(getPetsInternal());
    sortedPets.sort(Comparator.comparing(Pet::getName, Comparator.nullsLast(String::compareTo)));
    return sortedPets;
  }
}
EOF
  python3 "$HARNESS_DIR/harvest-fidelity.py"; echo "rc=$?"
}
check "harvest-fidelity allows Spring DAO/support drops (O-FIDELITYDAO)" 0 "GREEN"

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

# Quarkus-shaped pom for O-PLANEXISTS (already-migrated BOM/plugin, no Spring)
quarkus_pom() {
  cat <<'EOF'
<project>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>io.quarkus.platform</groupId>
        <artifactId>quarkus-bom</artifactId>
        <version>3.15.1</version>
        <type>pom</type>
        <scope>import</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>
  <build><plugins>
    <plugin>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-maven-plugin</artifactId>
      <version>3.15.1</version>
    </plugin>
  </plugins></build>
</project>
EOF
}

# O-PLANEXISTS (N10/F-66): already-Quarkus tree → Spring→Quarkus convert tasks are dead
run_case() {
  mkfix
  quarkus_pom > pom.xml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Convert Spring Boot Parent to Quarkus Platform BOM
**Class**: rewrite
- Replace spring-boot-starter-parent with quarkus platform BOM.

#### T-002: Design the cart endpoint
**Class**: infer
- Target: → src/main/java/com/demo/rest/CartEndpoint.java with @Path("/api/cart")
EOF
  python3 "$LINT" tasks.md
}
check "lint rejects dead Spring-parent convert on Quarkus pom (O-PLANEXISTS)" 1 "O-PLANEXISTS"

run_case() {
  mkfix
  quarkus_pom > pom.xml
  mkdir -p src/main/java/com/demo
  printf 'package com.demo;\npublic class App {}\n' > src/main/java/com/demo/App.java
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Swap javax imports
**Class**: rewrite
- Mechanical jakarta rename across src/main/java sources.

#### T-010: Remove Spring Boot Application Class
**Class**: infer
**Shape**: remove
- Remove @SpringBootApplication entrypoint; Quarkus uses generated main.
EOF
  python3 "$LINT" tasks.md
}
check "lint rejects dead @SpringBootApplication remove (O-PLANEXISTS)" 1 "O-PLANEXISTS"

run_case() {
  mkfix
  cat > pom.xml <<'EOF'
<project>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>io.quarkus.platform</groupId>
        <artifactId>quarkus-bom</artifactId>
        <version>3.15.1</version>
        <type>pom</type>
        <scope>import</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-smallrye-health</artifactId>
    </dependency>
  </dependencies>
  <build><plugins>
    <plugin>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-maven-plugin</artifactId>
      <version>3.15.1</version>
    </plugin>
  </plugins></build>
</project>
EOF
  mkdir -p src/main/java/com/demo
  printf 'package com.demo;\npublic class App {}\n' > src/main/java/com/demo/App.java
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Swap javax imports
**Class**: rewrite
- Mechanical jakarta rename across src/main/java sources.

#### T-011: Convert Actuator to Quarkus Health Endpoints
**Class**: infer
- Replace spring-boot-starter-actuator with quarkus-smallrye-health (/q/health).
EOF
  python3 "$LINT" tasks.md
}
check "lint rejects dead actuator→health convert (O-PLANEXISTS/O-PLANHEALTH)" 1 "O-PLANEXISTS"

# O-PLANEXISTSSKIP: delivered T-NNN commits suppress dead-work RED (mid-story re-lint)
run_case() {
  mkfix
  git init -q
  git config user.email t@t
  git config user.name t
  cat > pom.xml <<'EOF'
<project>
  <dependencyManagement>
    <dependencies>
      <dependency>
        <groupId>io.quarkus.platform</groupId>
        <artifactId>quarkus-bom</artifactId>
        <version>3.15.1</version>
        <type>pom</type>
        <scope>import</scope>
      </dependency>
    </dependencies>
  </dependencyManagement>
  <build><plugins>
    <plugin>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-maven-plugin</artifactId>
      <version>3.15.1</version>
    </plugin>
  </plugins></build>
</project>
EOF
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Convert Spring Boot Parent to Quarkus Platform BOM
**Class**: rewrite
- Replace spring-boot-starter-parent with quarkus platform BOM.

#### T-002: Design the cart endpoint
**Class**: infer
- Target: → src/main/java/com/demo/rest/CartEndpoint.java with @Path("/api/cart")
EOF
  git add pom.xml tasks.md
  git commit -q -m "T-001: Convert Spring Boot Parent to Quarkus Platform BOM"
  # T-001 is delivered → must NOT O-PLANEXISTS; T-002 still needs design (OK)
  out=$(python3 "$LINT" tasks.md 2>&1) || true
  echo "$out" | grep -q 'O-PLANEXISTS: T-001' && echo 'leak-t001' && return 1
  echo "$out" | grep -q 'O-PLANEXISTS' && echo 'other-exists' && return 1
  echo skip-ok
}
check "lint skips O-PLANEXISTS for already-committed tasks (O-PLANEXISTSSKIP)" 0 "skip-ok"

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

# O-FAILOPEN-DTO (Poll 52): catch→status DTO is also fail-open 200
run_case() {
  sensor_fixture
  mkdir -p src/main/java/com/demo/rest
  cat > src/main/java/com/demo/rest/AcceptanceEndpoint.java <<'EOF'
package com.demo.rest;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import java.util.List;
@Path("/api/cart")
public class AcceptanceEndpoint {
  CatalogService catalog;
  @GET @Path("acceptance-check")
  public List acceptanceCheck() {
    try { return catalog.products(); }
    catch (Exception e) { return java.util.Collections.emptyList(); }
  }
}
EOF
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject fail-open acceptance catch→emptyList (O-FAILOPEN-DTO)" 1 "O-FAILOPEN-DTO"

# O-RESTGUIDE (Poll 53): root-level body("find { must RED
run_case() {
  sensor_fixture
  mkdir -p src/test/java/com/demo/rest
  cat > src/test/java/com/demo/rest/CartEndpointTest.java <<'EOF'
package com.demo.rest;
import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;
import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.is;
@QuarkusTest
class CartEndpointTest {
  @Test void a() { given().when().get("/cart/1").then().body("find { it.x == 1 }.y", is(1)); }
  @Test void b() { given().when().get("/cart/2").then().statusCode(200); }
}
EOF
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject RestAssured root find{} (O-RESTGUIDE/O-RESTJSON)" 1 "O-RESTJSON"

# O-QJACOCO (Poll 55 / O-INSTQUAL): behavioural — qjacoco dimension RED when missing
run_case() {
  mkfix
  SENSOR_ROOT="$FIX" bash "$SENSORS" qjacoco
}
check "qjacoco RED when quarkus-jacoco report missing (O-QJACOCO behavioural)" 1 "O-QJACOCO"

run_case() {
  mkfix
  mkdir -p target/jacoco-report
  printf '<report/>\n' > target/jacoco-report/jacoco.xml
  SENSOR_ROOT="$FIX" bash "$SENSORS" qjacoco
}
check "qjacoco GREEN when jacoco.xml present (O-QJACOCO behavioural)" 0 "qjacoco check GREEN"

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
# G-CAT-FIXTURES (Poll 51): acceptance surface must reference catalog so G-CAT
# does not mask the missing-index assertion.
run_case() {
  sensor_fixture
  mkdir -p k8s src/main/java/com/demo/rest
  printf 'env:\n  - name: CATALOG_ENDPOINT\n    value: http://catalog:8080\n' > k8s/app.yaml
  printf 'apiVersion: v1\nkind: Service\nmetadata:\n  name: catalog\nspec:\n  ports: [{port: 8080}]\n' > k8s/catalog-svc.yaml
  printf 'package com.demo.rest;\nimport jakarta.ws.rs.Path;\n@Path("/api/cart")\npublic class CartEndpoint {\n  CatalogService catalog;\n  @Path("acceptance-check")\n  public Object acceptanceCheck() { return catalog.products(); }\n}\n' \
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

# O-MAPPINGS-PETCLINIC — @Aspect classes must be §7 REDESIGN (Quarkus has no AOP)
run_case() {
  mkfix; printf '## 7. Class roles & target contract\n- `CallMonitoringAspect` — HARVEST\n' > profile.md
  mkdir -p legacy/com/demo
  printf 'package com.demo;\nimport org.aspectj.lang.annotation.Aspect;\n@Aspect\npublic class CallMonitoringAspect {}\n' \
    > legacy/com/demo/CallMonitoringAspect.java
  python3 "$HARNESS_DIR/profile-rubric.py" profile.md legacy
}
check "profile-rubric flags @Aspect class not classified REDESIGN (O-MAPPINGS-PETCLINIC)" 1 "classroles"

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

run_case() {
  # O-DTOSTAGING: harvest falls back to OpenAPI generated-sources
  mkfix
  mkdir -p .hermes/skills/migration-harness/scripts
  cp "$HARVEST_SH" .hermes/skills/migration-harness/scripts/harvest-from-staging.sh
  cat > migration.yaml <<'EOF'
legacyPackage: org.springframework.samples.petclinic
targetPackage: com.demo
EOF
  mkdir -p /tmp/openapi-dto-fix/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto
  # Use relative openapi_alt path under repo: target/generated-sources/...
  mkdir -p target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto
  cat > target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/OwnerDto.java <<'EOF'
package org.springframework.samples.petclinic.dto;
import javax.validation.Valid;
import javax.annotation.Generated;
public class OwnerDto { @Valid String name; }
EOF
  out=$(bash .hermes/skills/migration-harness/scripts/harvest-from-staging.sh dto/OwnerDto.java)
  echo "$out"
  grep -q 'jakarta.validation' src/main/java/com/demo/dto/OwnerDto.java \
    && grep -q 'package com.demo.dto' src/main/java/com/demo/dto/OwnerDto.java \
    && echo DTOSTAGING_OK
}
check "harvest-from-staging OpenAPI fallback + jakarta (O-DTOSTAGING)" 0 "DTOSTAGING_OK"

# restore note: prior harvest check above — continue O-HARVESTSTALL

# O-HARVESTSTALL — harvest src/test + mechan preseed missing Target tests
run_case() {
  mkfix
  mkdir -p migration/staging/src/test/java/com/redhat/coolstore/service
  printf 'package com.redhat.coolstore.service;\npublic class ShoppingCartServiceTest { }\n' \
    > migration/staging/src/test/java/com/redhat/coolstore/service/ShoppingCartServiceTest.java
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  bash "$HARVEST_SH" service/ShoppingCartServiceTest.java >/dev/null 2>&1
  { [ -f src/test/java/com/demo/service/ShoppingCartServiceTest.java ] \
    && grep -q "package com.demo.service" src/test/java/com/demo/service/ShoppingCartServiceTest.java; } \
    && echo "HARVEST TEST OK" || echo "FAIL"
}
check "harvest-from-staging harvests src/test targets (O-HARVESTSTALL)" 0 "HARVEST TEST OK"

# O-PKGPREFIX — petclinic legacyPackage must not rewrite Spring Boot imports
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/org/springframework/samples/petclinic/model
  cat > migration/staging/src/main/java/org/springframework/samples/petclinic/model/Owner.java <<'EOF'
package org.springframework.samples.petclinic.model;
import org.springframework.boot.SpringApplication;
import org.springframework.samples.petclinic.model.Person;
public class Owner extends Person { }
EOF
  printf 'legacyPackage: org.springframework.samples.petclinic\ntargetPackage: com.demo\n' > migration.yaml
  bash "$HARVEST_SH" model/Owner.java >/dev/null 2>&1
  dest=src/main/java/com/demo/model/Owner.java
  { [ -f "$dest" ] \
    && grep -q 'package com.demo.model' "$dest" \
    && grep -q 'import org.springframework.boot.SpringApplication' "$dest" \
    && grep -q 'import com.demo.model.Person' "$dest" \
    && ! grep -q 'org.springframework.samples.petclinic' "$dest"; } \
    && echo "PKGPREFIX OK boot untouched" || echo "FAIL"
}
check "harvest rename leaves org.springframework.boot untouched (O-PKGPREFIX)" 0 "PKGPREFIX OK"

run_case() {
  mkfix
  mkdir -p .hermes/skills/migration-harness/scripts .hermes/harness \
    migration/staging/src/test/java/com/redhat/coolstore/service
  cp "$HARVEST_SH" .hermes/skills/migration-harness/scripts/harvest-from-staging.sh
  cp "$HARNESS_DIR/preseed-targets.py" .hermes/harness/preseed-targets.py
  printf 'package com.redhat.coolstore.service;\npublic class ShoppingCartServiceTest { }\n' \
    > migration/staging/src/test/java/com/redhat/coolstore/service/ShoppingCartServiceTest.java
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Test migration to Quarkus
**Class**: rewrite
**Target design**:
- → `src/test/java/com/demo/service/ShoppingCartServiceTest.java`
**Goal**: Port staging unit tests
**Acceptance**: ShoppingCartServiceTest exists under target package
EOF
  out=$(PRESEED_ROOT="$FIX" python3 .hermes/harness/preseed-targets.py tasks.md T-001)
  echo "$out"
  [ -f src/test/java/com/demo/service/ShoppingCartServiceTest.java ] && echo "$out" | grep -q seeded
}
check "preseed-targets harvests missing rewrite test Target (O-HARVESTSTALL)" 0 "seeded:"

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

# O-HTTPPORT — legacy server.port copy vs k8s containerPort (R-220 / Petclinic 9966)
run_case() {
  sensor_fixture
  mkdir -p src/main/resources k8s
  printf 'quarkus.http.port=9966\nquarkus.http.root-path=/petclinic\n' > src/main/resources/application.properties
  printf 'containers:\n  - ports:\n      - containerPort: 8080\n        name: http\n' > k8s/app.yaml
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring rejects quarkus.http.port≠k8s containerPort (O-HTTPPORT)" 1 "O-HTTPPORT"

run_case() {
  sensor_fixture
  mkdir -p src/main/resources k8s
  printf 'quarkus.http.port=8080\n' > src/main/resources/application.properties
  printf 'containers:\n  - ports:\n      - containerPort: 8080\n        name: http\n' > k8s/app.yaml
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring passes matching quarkus.http.port and containerPort (O-HTTPPORT)" 0 "STATIC CHECKS GREEN"

run_case() {
  sensor_fixture
  mkdir -p src/main/resources k8s
  printf 'quarkus.http.port=9966\n' > src/main/resources/application.properties
  printf 'env:\n  - name: QUARKUS_HTTP_PORT\n    value: "8080"\ncontainers:\n  - ports:\n      - containerPort: 8080\n' > k8s/app.yaml
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring passes QUARKUS_HTTP_PORT env override aligned with containerPort (O-HTTPPORT)" 0 "STATIC CHECKS GREEN"

# O-GENSEED (R-225/R-226): sql-load-script + validate/none is a fresh-DB break
run_case() {
  sensor_fixture
  mkdir -p src/main/resources
  printf 'quarkus.hibernate-orm.database.generation=validate\nquarkus.hibernate-orm.sql-load-script=import.sql\n' \
    > src/main/resources/application.properties
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring rejects sql-load-script with generation=validate (O-GENSEED)" 1 "O-GENSEED"

run_case() {
  sensor_fixture
  mkdir -p src/main/resources
  printf 'quarkus.hibernate-orm.database.generation=update\nquarkus.hibernate-orm.sql-load-script=import.sql\n' \
    > src/main/resources/application.properties
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring passes sql-load-script with generation=update (O-GENSEED)" 0 "STATIC CHECKS GREEN"

# O-PCTFILE (R-230/T-012): literal % in application-%*.properties filename is not a profile
run_case() {
  sensor_fixture
  mkdir -p src/main/resources
  printf 'quarkus.datasource.db-kind=hsql\n' > src/main/resources/'application-%hsqldb.properties'
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring rejects application-%profile.properties filename (O-PCTFILE)" 1 "O-PCTFILE"

run_case() {
  sensor_fixture
  mkdir -p src/main/resources
  printf 'quarkus.datasource.db-kind=hsql\n' > src/main/resources/application-hsqldb.properties
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring accepts application-profile.properties without percent (O-PCTFILE)" 0 "STATIC CHECKS GREEN"

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
  # G-CAT-FIXTURES (Poll 51): P0c green path must also satisfy G-CAT catalog fetch
  printf 'package com.demo.rest;\nimport jakarta.ws.rs.Path;\n@Path("/api/cart")\npublic class CartEndpoint {\n  CatalogService catalog;\n  @Path("acceptance-check")\n  public Object acceptanceCheck() { return catalog.products(); }\n}\n' \
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

# O-ACCREATE — Create *Test with "removal" in body must NOT skip when target absent
run_case() {
  mkfix
  mkdir -p src/test/java/com/demo/util
  # deliberately NO EntityUtilsMigrationTest.java
  cat > tasks.md <<'EOF'
# Tasks
#### T-009: Create EntityUtils migration integration tests
**Class**: infer
**Target design**: → `src/test/java/com/demo/util/EntityUtilsMigrationTest.java`
**Evidence**: EntityUtils removal requires integration testing
**Task Details**:
- Create integration tests verifying Stream API replacement works correctly
- **Absorbs**: EntityUtils removal verification
**Target**: → `src/test/java/com/demo/util/EntityUtilsMigrationTest.java`
EOF
  printf 'legacyPackage: org.springframework.samples.petclinic\ntargetPackage: com.demo\n' > migration.yaml
  ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-009; echo "rc=$?"
}
check "already-complete does not skip Create *Test when absent (O-ACCREATE)" 0 "rc=1"

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

# O-AC-K8S — k8s comment/sample must not satisfy preserve when props lack token (V10 T-003)
run_case() {
  mkfix
  mkdir -p src/main/resources k8s
  printf 'quarkus.http.port=8080\n' > src/main/resources/application.properties
  printf '# Legacy clients call GET ${CATALOG_ENDPOINT}/api/products\n' > k8s/catalog-service.yaml
  cat > tasks.md <<'EOF'
# Tasks
#### T-003: Harvest and convert application.properties configuration
**Class**: rewrite
**Target design**: → `src/main/resources/application.properties`
**Goal**: Migrate configuration; preserve CATALOG_ENDPOINT environment variable
**Acceptance**: CATALOG_ENDPOINT present in application.properties
EOF
  printf 'preserve:\n  - CATALOG_ENDPOINT\n' > migration.yaml
  ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-003; echo "rc=$?"
}
check "already-complete does not skip on k8s-only CATALOG_ENDPOINT (O-AC-K8S)" 0 "rc=1"

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


# O-AC-NONJAVA — Target application.properties must not preserve-skip on token alone
run_case() {
  mkfix
  mkdir -p src/main/resources
  printf 'CATALOG_ENDPOINT=http://localhost:8081\n' > src/main/resources/application.properties
  cat > tasks.md <<'EOF'
# Tasks
#### T-007: Environment Configuration Validation
**Class**: infer
**Findings**: demo-env-integration-00001
**Target design**: → `src/main/resources/application.properties`
**Goal**: Validate CATALOG_ENDPOINT; create test configuration for property resolution
**Acceptance**: test config demonstrates env fallback
EOF
  printf 'preserve:\n  - CATALOG_ENDPOINT\n' > migration.yaml
  ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-007; echo "rc=$?"
}
check "already-complete does not skip props Target on preserve token (O-AC-NONJAVA)" 0 "rc=1"

# O-ACVERIFY — Verify/Ensure tasks must not preserve-skip on ENV token alone
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/rest src/main/resources k8s
  printf 'quarkus.rest-client.catalog.url=${CATALOG_ENDPOINT}\n' > src/main/resources/application.properties
  printf 'env:\n  - name: CATALOG_ENDPOINT\n    value: http://catalog:8080\n' > k8s/app.yaml
  printf 'package com.demo.rest;\npublic class AcceptanceEndpoint {}\n' \
    > src/main/java/com/demo/rest/AcceptanceEndpoint.java
  cat > tasks.md <<'EOF'
# Tasks
#### T-003: Verify existing catalog-backed acceptance (S04)
**Class**: infer
**Goal**: Confirm AcceptanceEndpoint still returns catalog products[]; preserve CATALOG_ENDPOINT
**Target design**: → `src/main/java/com/demo/rest/AcceptanceEndpoint.java`
**Acceptance**: /api/cart/acceptance-check returns products[]; CATALOG_ENDPOINT remains wired
EOF
  printf 'preserve:\n  - CATALOG_ENDPOINT\nacceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-003; echo "rc=$?"
}
check "already-complete does not skip Verify acceptance on CATALOG_ENDPOINT (O-ACVERIFY)" 0 "rc=1"

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

# O-SCAFFOLDDIR — structure task + gitkeep tree must not fail on discovered.md noise
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Create target package directory structure
**Class: rewrite**
**Target design**: Create `src/main/java/com/demo` directory structure with `.gitkeep` files
**Target**: → `src/main/java/com/demo/`
**Owns**: Empty directory creation
EOF
  printf '%s\n' \
    'src/main/java/com/demo/.gitkeep' \
    'src/main/java/com/demo/model/.gitkeep' \
    'src/test/java/com/demo/model/.gitkeep' \
    'migration/discovered.md' \
    | python3 "$MM_PY" tasks.md T-001; echo "rc=$?"
}
check "mechan-match accepts structure gitkeeps despite discovered.md (O-SCAFFOLDDIR)" 0 "rc=0"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Create target package directory structure
**Class: rewrite**
**Target design**: Create package directory structure with `.gitkeep` files
EOF
  printf '%s\n' \
    'src/main/java/com/demo/model/BaseEntity.java' \
    'src/main/java/com/demo/model/.gitkeep' \
    | python3 "$MM_PY" tasks.md T-001; echo "rc=$?"
}
check "mechan-match refuses structure task when real java outside soft scope (O-SCAFFOLDDIR)" 0 "rc=1"

# O-STRUCTINFO — package-info *tasks* must not be classified as gitkeep-only
# structure (Wave2 T-003: Target text "package structure" → structure-non-gitkeep).
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-003: Update package-info files with Jakarta documentation
**Class: rewrite**
**Target design**: Updated package-info.java files in com.demo package structure
**Target**: → `src/main/java/com/demo/*/package-info.java`
EOF
  printf '%s\n' \
    'src/main/java/com/demo/model/package-info.java' \
    'src/main/java/com/demo/rest/package-info.java' \
    | python3 "$MM_PY" tasks.md T-003; echo "rc=$?"
}
check "mechan-match accepts package-info.java for package-info task (O-STRUCTINFO)" 0 "rc=0"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Create target package directory structure
**Class: rewrite**
**Target design**: Create directory structure with `.gitkeep` or package-info.java
EOF
  printf '%s\n' \
    'src/main/java/com/demo/model/package-info.java' \
    'src/main/java/com/demo/rest/.gitkeep' \
    | python3 "$MM_PY" tasks.md T-001; echo "rc=$?"
}
check "mechan-match accepts package-info.java on structure task (O-STRUCTINFO)" 0 "rc=0"

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

# O-ACCEPTREC / G-CAT (Poll 50): Java record status DTO evades G-OK/G-AC2 greps
run_case() {
  sensor_fixture
  mkdir -p src/main/java/com/demo/rest
  cat > src/main/java/com/demo/rest/AcceptanceEndpoint.java <<'EOF'
package com.demo.rest;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;
@Path("/api/cart")
public class AcceptanceEndpoint {
  @GET @Path("acceptance-check") @Produces(MediaType.APPLICATION_JSON)
  public AcceptanceStatus acceptanceCheck() {
    return new AcceptanceStatus("accepted", "cart service is healthy");
  }
  public record AcceptanceStatus(String status, String message) {}
}
EOF
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject ceremonial record acceptance (G-CAT/O-ACCEPTREC)" 1 "G-CAT"

# G-CATBODY: catalog fetch side-effect + status DTO still ships products=0
run_case() {
  sensor_fixture
  mkdir -p src/main/java/com/demo/rest
  cat > src/main/java/com/demo/rest/AcceptanceEndpoint.java <<'EOF'
package com.demo.rest;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import java.util.List;
@Path("/api/cart")
public class AcceptanceEndpoint {
  CatalogService catalogService;
  @GET @Path("acceptance-check")
  public AcceptanceStatus acceptanceCheck() {
    List products = catalogService.getProducts();
    return new AcceptanceStatus("accepted", "products: " + products.size());
  }
  public record AcceptanceStatus(String status, String message) {}
}
EOF
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject catalog-fetch status DTO acceptance (G-CATBODY)" 1 "G-CATBODY"

# O-ACCEPTGEN — G-CAT tokens follow acceptance.collection (vetList specimen)
run_case() {
  sensor_fixture
  mkdir -p src/main/java/com/demo/rest
  printf 'acceptance:\n  path: /api/vets/acceptance-check\n  collection: vetList\n  service: VetService\n  itemType: Vet\n' > migration.yaml
  cat > src/main/java/com/demo/rest/AcceptanceEndpoint.java <<'EOF'
package com.demo.rest;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import java.util.List;
@Path("/api/vets")
public class AcceptanceEndpoint {
  VetService vets;
  @GET @Path("acceptance-check")
  public List acceptanceCheck() { return vets.vetList(); }
}
EOF
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors accept vetList collection proof (O-ACCEPTGEN G-CAT)" 0 "STATIC CHECKS GREEN"

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
  # S-SOFT-NARROW: title "Verify X" must fail even when body cites a path
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-009: Verify existing catalog-backed acceptance
**Class**: infer
**Target design**: → `src/main/java/com/demo/rest/AcceptanceEndpoint.java`
**Goal**: Confirm products[] still returned
**Acceptance**: /api/cart/acceptance-check returns catalog products
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\nacceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  python3 "$LINT" tasks.md --story-deploy true
}
check "plan-lint rejects Verify-title tasks (S-SOFT-NARROW)" 1 "S-SOFT"

run_case() {
  grep -q 'O-DELTASTAGING' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'kantra-after-src' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'exclude.*migration/staging' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-RESTCLIENTDEP' "$HARNESS_DIR/../skills/migration-harness/MAPPINGS.md" \
    && grep -q 'rest.client.inject.RegisterRestClient' \
         "$HARNESS_DIR/../skills/migration-harness/MAPPINGS.md" \
    && echo deltarest-ok
}
check "O-DELTASTAGING after-scan excludes + O-RESTCLIENTDEP import tip" 0 "deltarest-ok"

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
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Acceptance Path Implementation
**Class**: infer
**Target design**: → `src/main/java/com/demo/rest/MinimalAcceptanceEndpoint.java`
- Create MinimalAcceptanceEndpoint.java with @Path("/api/cart")
- Return JSON response with status information / platform readiness verification
```java
public Map<String, String> acceptanceCheck() {
    return Map.of("status", "platform_ready", "story", "S01");
}
```
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\nacceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "plan-lint rejects MinimalAcceptanceEndpoint status-map (S-AC1 V10)" 1 "S-AC1"

run_case() {
  # S-AC1-NEG: negation prose must not trip S-AC1
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).
Do NOT schedule MinimalAcceptanceEndpoint / status-map placeholders (S-AC1/G-OK).

#### T-001: Convert pom to Quarkus BOM
**Class**: rewrite
**Owns**: pom.xml
- Replace Spring Boot parent with Quarkus BOM in `pom.xml`.
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\nacceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  python3 "$LINT" tasks.md --story-deploy false
}
check "plan-lint accepts No MinimalAcceptanceEndpoint defer prose (S-AC1-NEG)" 0 "PLAN OK"

run_case() {
  grep -q 'sensor autofix:' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SFIXCREDIT' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SFIXDIRTY' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'PRE_SFIX_HEAD' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'ParameterizedTest' "$HARNESS_DIR/sensors.sh" \
    && echo sfix-ok
}
check "O-SFIXCREDIT/DIRTY/COUNT wiring in supervisor+sensors" 0 "sfix-ok"

run_case() {
  # O-M3GOK: status/ok acceptance on CartEndpoint must fail plan-lint
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-004: Add acceptance status/ok on CartEndpoint
**Class**: infer
**Target design**: → `src/main/java/com/demo/rest/CartEndpoint.java`
- Add `@Path("acceptance-check")` returning status/ok for deploy verification
- Method may `return "ok"` until catalog wiring lands
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\nacceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  python3 "$LINT" tasks.md --story-deploy true
}
check "plan-lint rejects status/ok acceptance on CartEndpoint (O-M3GOK)" 1 "S-AC1"

run_case() {
  # O-M3ACCEPT: non-deploy story may omit acceptance.path entirely
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Convert pom to Quarkus BOM
**Class**: rewrite
**Owns**: pom.xml
- Replace Spring Boot parent with Quarkus BOM in `pom.xml`.
EOF
  printf 'acceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  python3 "$LINT" tasks.md --story-deploy false
}
check "plan-lint accepts non-deploy plan without acceptance.path (O-M3ACCEPT)" 0 "PLAN OK"

run_case() {
  # O-M3ACCEPT: non-deploy must not task endpoint substance for acceptance.path
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Acceptance endpoint early
**Class**: infer
**Owns**: MinimalAcceptanceEndpoint.java
- Serve `/api/cart/acceptance-check` via `@Path` on
  `src/main/java/com/demo/rest/MinimalAcceptanceEndpoint.java` Endpoint.
EOF
  printf 'acceptance:\n  path: /api/cart/acceptance-check\n' > migration.yaml
  python3 "$LINT" tasks.md --story-deploy false
}
check "plan-lint rejects acceptance endpoint on non-deploy story (O-M3ACCEPT)" 1 "O-M3ACCEPT"

run_case() {
  # O-M3EVID / O-M3ACCEPT / O-M3QUOTA wiring in outer-loop
  ! grep -nE 'plan-lint\.py.*"\$SPEC_TASKS".*\|\|.*tasks\.md missing' \
    "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-M3EVID' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'story-deploy' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-M3QUOTA' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-M3QUOTA-GATE' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'sleep 900' "$HARNESS_DIR/outer-loop.sh" \
    && echo om3evid-ok
}
check "outer-loop O-M3EVID + O-M3ACCEPT + O-M3QUOTA wiring" 0 "om3evid-ok"

run_case() {
  # K2-LABEL: Finds: alias must still inject evidence; plan-lint rejects non-canonical
  mkfix
  mkdir -p migration
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived.

#### T-001: Convert pom
**Class**: rewrite
**Finds**: springboot-parent-pom-to-quarkus-00000
**Owns**: pom.xml
- Edit `pom.xml` parent to Quarkus BOM.
EOF
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > migration/mta-findings.json <<'JSON'
[{"violations":{"springboot-parent-pom-to-quarkus-00000":{"category":"mandatory","incidents":[{"uri":"file:///projects/legacy/pom.xml","message":"replace parent with Quarkus BOM","codeSnip":"<parent>spring</parent>"}]}}}]
JSON
  n=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-001 qwen 2>/dev/null \
    | sed -n '/Analysis evidence/,/Target Design/p' | grep -cE '^- ' || true)
  lint_out=$(python3 "$LINT" tasks.md migration/mta-findings.json --story-deploy false 2>&1 || true)
  [ "$n" -ge 1 ] && echo "$lint_out" | grep -q K2-LABEL && echo k2label-ok
}
check "K2-LABEL alias injects evidence and plan-lint requires Findings" 0 "k2label-ok"

run_case() {
  grep -q 'story-deploy' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'DEPLOY_ARGS' "$HARNESS_DIR/supervisor.sh" \
    && echo osupaccept-ok
}
check "supervisor passes --story-deploy to plan-lint (O-SUPACCEPT)" 0 "osupaccept-ok"

run_case() {
  # G-AC3: acceptance_ship_contract invoked inside milestone_sensor body.
  # Capture the function body first — `awk | grep -q` under `set -o pipefail`
  # SIGPIPEs when the old range stretched to preflight (~400 lines) and
  # grep -q exited early (empty out + rc=1 flake, ~40% of runs).
  local body
  body=$(awk '/^milestone_sensor\(\)/{on=1} on{print} on && /^}$/{exit}' "$SENSORS")
  grep -q 'acceptance_ship_contract' <<<"$body" && echo gac3-ok
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
    && grep -q 'RenameLocalVariablesToCamelCase' "$HARNESS_DIR/style-autofix.sh" \
    && grep -q 'RenamePrivateFieldsToCamelCase' "$HARNESS_DIR/style-autofix.sh" \
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
    && grep -q 'O-ESCALGPLACE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-NOPUSHPR' "$HARNESS_DIR/supervisor.sh" \
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
  mkdir -p src/main/java/com/demo/rest
  # JAX-RS stub without session/inject — must NOT ESCW for Convert+session task
  cat > src/main/java/com/demo/rest/CartEndpoint.java <<'EOF'
package com.demo.rest;
import jakarta.ws.rs.Path;
@Path("/cart")
public class CartEndpoint { }
EOF
  cat > tasks.md <<'EOF'
# Tasks
#### T-005: Convert CartEndpoint to JAX-RS with Quarkus session management
**Class**: infer
- Replace session scope with Quarkus session management
- Convert @Autowired field injection to constructor injection
**Target design**: → `src/main/java/com/demo/rest/CartEndpoint.java`
EOF
  ALREADY_COMPLETE_ROOT="$PWD" python3 "$ESCW_PY" tasks.md T-005; echo rc=$?
}
check "escw-eligible refuses Convert session stub without @SessionScoped (O-ESCWCONVERT)" 0 "need-session-scope"


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
  # K1-SHARED: pom claimed by two tasks must NOT incident-conflict
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Quarkus BOM
**Class**: rewrite
- Target: → `pom.xml`

#### T-002: Add rest-client dep
**Class**: rewrite
**Owns**: pom.xml
- Also edits pom.xml for quarkus-rest-client-jackson
EOF
  cat > f.json <<'EOF'
[{"violations": {"javaee-pom-to-quarkus-00010": {
  "category": "mandatory",
  "incidents": [
    {"uri": "file:///projects/legacy/pom.xml", "lineNumber": 1}
  ]
}}}]
EOF
  python3 "$LINT" tasks.md f.json
}
check "plan-lint allows shared pom ownership without conflict (K1-SHARED)" 0 "PLAN OK"

run_case() {
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-004: Package rename legacy→target
**Class**: rewrite
**Goal**: Apply package rename across sources
**Acceptance**: no legacyPackage under src/main
EOF
  python3 "$LINT" tasks.md
}
check "plan-lint rejects package-rename with no harvested java (O-PKGORD)" 1 "O-PKGORD"

run_case() {
  # O-DTOFIRST: mapper harvest before DTO harvest must RED
  # mkfix required — prior cases leave migration.yaml with preserve/acceptance
  # (K4) that would false-RED the ordering accept fixtures (R-216).
  mkfix
  cat > tasks.md <<'EOF'
UI surface: waived (API-only).

#### T-005: Harvest MapStruct mappers with Jakarta updates
**Class**: rewrite
**Findings**: javax-to-jakarta-import-00001
**Goal**: Update mapper interfaces
**Target**: `src/main/java/com/demo/mapper/*.java`

#### T-006: Harvest DTOs with Jakarta validation imports
**Class**: rewrite
**Findings**: javax-to-jakarta-import-00001
**Goal**: Harvest DTOs
**Target**: `src/main/java/com/demo/dto/*.java`
EOF
  python3 "$LINT" tasks.md
}
check "plan-lint rejects mapper-before-DTO order (O-DTOFIRST)" 1 "O-DTOFIRST"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
UI surface: waived (API-only).

#### T-005: Harvest DTOs with Jakarta validation imports
**Class**: rewrite
**Findings**: javax-to-jakarta-import-00001
**Goal**: Harvest DTOs
**Target**: `src/main/java/com/demo/dto/*.java`

#### T-006: Harvest MapStruct mappers with Jakarta updates
**Class**: rewrite
**Findings**: javax-to-jakarta-import-00001
**Goal**: Update mapper interfaces
**Target**: `src/main/java/com/demo/mapper/*.java`
EOF
  python3 "$LINT" tasks.md
}
check "plan-lint accepts DTO-before-mapper order (O-DTOFIRST)" 0 "PLAN OK"

run_case() {
  # O-CDIORDER: service CDI before repository CDI must RED
  mkfix
  cat > tasks.md <<'EOF'
UI surface: waived (API-only).

#### T-007: Convert ClinicServiceImpl to Quarkus CDI
**Class**: rewrite
**Findings**: springboot-di-to-quarkus-00003
**Goal**: Convert Spring @Service to Quarkus @ApplicationScoped with CDI injection
**Target**: `src/main/java/com/demo/service/ClinicServiceImpl.java`

#### T-010: Convert JPA repository implementations to CDI
**Class**: rewrite
**Findings**: springboot-di-to-quarkus-00003
**Goal**: Convert JPA repository implementations to CDI
**Target**: `src/main/java/com/demo/repository/jpa/*.java`
EOF
  python3 "$LINT" tasks.md
}
check "plan-lint rejects service-CDI-before-repo order (O-CDIORDER)" 1 "O-CDIORDER"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
UI surface: waived (API-only).

#### T-009: Convert JPA repository implementations to CDI
**Class**: rewrite
**Findings**: springboot-di-to-quarkus-00003
**Goal**: Convert JPA repository implementations to CDI
**Target**: `src/main/java/com/demo/repository/jpa/*.java`

#### T-010: Convert ClinicServiceImpl to Quarkus CDI
**Class**: rewrite
**Findings**: springboot-di-to-quarkus-00003
**Goal**: Convert Spring @Service to Quarkus @ApplicationScoped with CDI injection
**Target**: `src/main/java/com/demo/service/ClinicServiceImpl.java`
EOF
  python3 "$LINT" tasks.md
}
check "plan-lint accepts repo-before-service-CDI order (O-CDIORDER)" 0 "PLAN OK"

run_case() {
  grep -q 'O-HARVESTREPO\|@Repository' \
    "$HARNESS_DIR/../skills/migration-harness/scripts/harvest-from-staging.sh" \
    && echo harvestrepo-ok
}
check "O-HARVESTREPO wiring in harvest-from-staging" 0 "harvestrepo-ok"

run_case() {
  grep -q 'commit-hygiene.py' "$HARNESS_DIR/supervisor.sh" \
    && test -f "$HARNESS_DIR/commit-hygiene.py" \
    && grep -q 'O-COMMITHYGIENE\|O-GITBAK\|O-POMUNC' "$HARNESS_DIR/supervisor.sh" \
    && echo hygiene-wire-ok
}
check "O-GITBAK/O-SIMPLEDTO/O-POMUNC commit-hygiene wiring" 0 "hygiene-wire-ok"

run_case() {
  mkfix
  git init -q
  git config user.email t@t; git config user.name t
  mkdir -p src/main/java/com/demo/dto src/main/java/com/demo/mapper
  printf '<project></project>\n' > pom.xml
  git add -A && git commit -q -m 'init'
  printf 'package com.demo.dto;\npublic class OwnerDto {}\n' > src/main/java/com/demo/dto/OwnerDto.java
  printf 'package com.demo.dto;\n@Generated public class OwnerAllOfDto {}\n' > src/main/java/com/demo/dto/OwnerAllOfDto.java.bak
  printf 'package com.demo.mapper;\nimport org.mapstruct.Mapper;\n@Mapper\npublic interface OwnerMapper {}\n' \
    > src/main/java/com/demo/mapper/OwnerMapper.java
  git add -A && git commit -q -m 'T-005: bad harvest'
  python3 "$HARNESS_DIR/commit-hygiene.py" HEAD; echo "rc=$?"
}
check "commit-hygiene rejects bak+mapstruct-without-pom (O-GITBAK/O-POMUNC)" 0 "rc=1"

run_case() {
  grep -q 'O-M4REPLAY' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-WORKERREAD' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'worker-read-watch.py' "$HARNESS_DIR/supervisor.sh" \
    && echo m4worker-ok
}
check "O-M4REPLAY + O-WORKERREAD wiring" 0 "m4worker-ok"

run_case() {
  grep -q 'O-MSGCLAIM' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'msgclaim-check.py' "$HARNESS_DIR/supervisor.sh" \
    && test -f "$HARNESS_DIR/msgclaim-check.py" \
    && echo msgclaim-ok
}
check "O-MSGCLAIM wiring" 0 "msgclaim-ok"

run_case() {
  # msgclaim-check: subject claims CatalogService but diff only touches Other.java
  mkfix
  git init -q
  git config user.email t@t; git config user.name t
  mkdir -p src/main/java/com/demo
  printf 'class Other {}\n' > src/main/java/com/demo/Other.java
  git add -A && git commit -q -m 'init'
  printf 'class Other { int x; }\n' > src/main/java/com/demo/Other.java
  git add -A && git commit -q -m 'T-002: CatalogService Feign to REST convert'
  python3 "$HARNESS_DIR/msgclaim-check.py" HEAD; echo "rc=$?"
}
check "msgclaim-check rejects subject class absent from diff (O-MSGCLAIM)" 0 "rc=1"

run_case() {
  local top detect
  top=$(git -C "$HARNESS_DIR/../../../../.." rev-parse --show-toplevel 2>/dev/null || true)
  detect="${top}/scripts/track-b/v9-handfix-detect.sh"
  [ -n "$top" ] && [ -f "$detect" ] \
    && grep -qE 'O-HANDCOMMIT|RECENT_BEGIN' "$detect" \
    && echo handcommit-ok
}
check "O-HANDCOMMIT recent-commit detect wiring" 0 "handcommit-ok"

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

# O-DESTBASE — scaffold-presatisfied omit + already-complete (via K6 oracle)
run_case() {
  mkfix
  mkdir -p .hermes/harness migration
  cp "$HARNESS_DIR/scaffold-presatisfied.txt" .hermes/harness/
  cp "$HARNESS_DIR/already-complete.py" .hermes/harness/
  cp "$HARNESS_DIR/findings-oracle.py" .hermes/harness/
  printf '<project><build><plugins><plugin><artifactId>quarkus-maven-plugin</artifactId></plugin></plugins></build></project>\n' > pom.xml
  cat > migration/mta-findings.json <<'EOF'
[{"violations":{
  "springboot-parent-pom-to-quarkus-00000":{"description":"p","incidents":[{"uri":"file:///pom.xml","lineNumber":1}]}
}}]
EOF
  cat > tasks.md <<'EOF'
#### T-001: Convert Spring Boot parent to Quarkus
**Findings**: springboot-parent-pom-to-quarkus-00000
**Goal**: Use Quarkus parent
**Acceptance**: pom has quarkus-maven-plugin
EOF
  ALREADY_COMPLETE_ROOT="$FIX" python3 .hermes/harness/already-complete.py tasks.md T-001
}
check "already-complete skips scaffold-presatisfied Findings (O-DESTBASE)" 0 "oracle-absent:"

# O-HARVESTBRK — Spring REST into src/main without spring-boot
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/com/redhat/coolstore/rest
  printf 'package com.redhat.coolstore.rest;\n@RestController\npublic class CartEndpoint {}\n' \
    > migration/staging/src/main/java/com/redhat/coolstore/rest/CartEndpoint.java
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  printf '<project></project>\n' > pom.xml
  out=$(bash "$HARVEST_SH" rest/CartEndpoint.java 2>&1 || true)
  echo "$out" | grep -q O-HARVESTBRK && echo harvestbrk-ok
}
check "harvest refuses Spring REST without spring-boot (O-HARVESTBRK)" 0 "harvestbrk-ok"

# O-REDESIGNREVERT — refuse overwrite of converted dest
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/com/redhat/coolstore/service \
    src/main/java/com/demo/service
  printf 'package com.redhat.coolstore.service;\n@Service\npublic class CatalogService { public void products(){} }\n' \
    > migration/staging/src/main/java/com/redhat/coolstore/service/CatalogService.java
  printf 'package com.demo.service;\n@ApplicationScoped\npublic class CatalogService { public void products(){} }\n' \
    > src/main/java/com/demo/service/CatalogService.java
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  printf '<project><dependency>spring-boot</dependency></project>\n' > pom.xml
  out=$(bash "$HARVEST_SH" service/CatalogService.java 2>&1 || true)
  echo "$out" | grep -q O-REDESIGNREVERT && echo redesignrevert-ok
}
check "harvest refuses overwrite of CDI dest (O-REDESIGNREVERT)" 0 "redesignrevert-ok"

# O-REDESIGNSIG / O-IFACERENAME
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/com/redhat/coolstore/service \
    src/main/java/com/demo/service
  printf 'package com.redhat.coolstore.service;\npublic interface CatalogService { java.util.List products(); }\n' \
    > migration/staging/src/main/java/com/redhat/coolstore/service/CatalogService.java
  printf 'package com.demo.service;\n@RegisterRestClient\npublic interface CatalogService { java.util.List getProducts(); }\n' \
    > src/main/java/com/demo/service/CatalogService.java
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  python3 "$HARNESS_DIR/redesign-sig.py" >/dev/null; echo "rc=$?"
}
check "redesign-sig catches interface method rename (O-IFACERENAME)" 0 "rc=1"

# O-HOTSWAP wiring
run_case() {
  grep -q 'harness-update-ack' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-HOTSWAP' "$HARNESS_DIR/outer-loop.sh" \
    && echo hotswap-ok
}
check "O-HOTSWAP wiring (pause + outer re-enter)" 0 "hotswap-ok"

# O-HOTSWAPRELOAD: after harness-update, exit for outer re-exec (not in-process resume)
run_case() {
  grep -q 'hotswap_pause_gate' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-HOTSWAPRELOAD' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'hotswap-inflight' "$HARNESS_DIR/supervisor.sh" \
    && echo hotswapreload-ok
}
check "O-HOTSWAPRELOAD wiring (exit after harness-update for fresh load)" 0 "hotswapreload-ok"

run_case() {
  grep -q 'O-HOTSWAPLOCK' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'supervisor.lock' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'sleep 15' "$HARNESS_DIR/outer-loop.sh" \
    && echo hotswaplock-ok
}
check "O-HOTSWAPLOCK wiring (drop flock + settle before re-enter)" 0 "hotswaplock-ok"

run_case() {
  grep -q 'O-WEDGERESUME' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'clearing stale worker-wedge-skip' "$HARNESS_DIR/supervisor.sh" \
    && echo wedgeresume-ok
}
check "O-WEDGERESUME wiring (clear wedge-skip at supervisor start)" 0 "wedgeresume-ok"

run_case() {
  grep -q 'O-INFERABSENT' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'task_oracle' "$HARNESS_DIR/supervisor.sh" \
    && echo inferabsent-ok
}
check "O-INFERABSENT wiring (skip worker on infer+absent)" 0 "inferabsent-ok"

run_case() {
  grep -q 'O-ESCREOPENCODE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'YOU OWN all file-changing work' "$HARNESS_DIR/supervisor.sh" \
    && echo escreopencode-ok
}
check "O-ESCREOPENCODE wiring (no opencode re-dispatch after wedge)" 0 "escreopencode-ok"

run_case() {
  grep -q 'O-ANTISCOPE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'Other problems will be solved in subsequent steps' "$HARNESS_DIR/supervisor.sh" \
    && echo antiscope-ok
}
check "O-ANTISCOPE wiring (prompt scope discipline)" 0 "antiscope-ok"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Convert Spring Boot Parent
**Class**: rewrite
- Replace spring-boot-starter-parent.

#### T-002: Something infer
**Class: infer**
- Infer design work.
EOF
  out=$(python3 - "$FIX/tasks.md" <<'PY'
import re, sys
def field(body, *names):
    for name in names:
        m = re.search(rf"^\*\*{re.escape(name)}\s*:\s*(.+?)\*\*\s*$", body, re.M | re.I)
        if m: return m.group(1).strip()
        m = re.search(rf"^\*\*{re.escape(name)}\*\*\s*:?\s*(.+)$", body, re.M | re.I)
        if m: return m.group(1).strip()
        m = re.search(rf"^{re.escape(name)}\s*:\s*(.+)$", body, re.M | re.I)
        if m: return m.group(1).strip()
    return ""
text = open(sys.argv[1], encoding="utf-8").read()
blocks = re.split(r"^#{2,6} +(T[-A-Za-z0-9]*\d+):", text, flags=re.M)
for i in range(1, len(blocks) - 1, 2):
    cls = field(blocks[i + 1], "Class", "Type") or "infer"
    m = re.search(r"\b(rewrite|infer)\b", cls, re.I)
    print(f"{blocks[i]}:{(m.group(1).lower() if m else 'infer')}")
PY
)
  echo "$out" | grep -qx 'T-001:rewrite' || { echo "bad-t001:$out"; return 1; }
  echo "$out" | grep -qx 'T-002:infer' || { echo "bad-t002:$out"; return 1; }
  echo classprompt-ok
}
check "O-CLASSPROMPT parses **Class**: rewrite form (not false infer)" 0 "classprompt-ok"

run_case() {
  python3 "$HARNESS_DIR/sensor-gate.py" decide 0 && echo allow || echo bad
  python3 "$HARNESS_DIR/sensor-gate.py" decide 1; [ $? -eq 1 ] || return 1
  python3 "$HARNESS_DIR/sensor-gate.py" needs-gate "T-012: foo" || return 1
  python3 "$HARNESS_DIR/sensor-gate.py" needs-gate "chore: ignore"; [ $? -eq 1 ] || return 1
  echo sensorgate-ok
}
check "O-SENSORGATE decide/needs-gate both directions (N12)" 0 "sensorgate-ok"

run_case() {
  grep -q 'O-SENSORGATE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'refusing checkpoint commit' "$HARNESS_DIR/supervisor.sh" \
    && echo sensorgate-wire-ok
}
check "O-SENSORGATE wiring (hook install + refuse RED checkpoint)" 0 "sensorgate-wire-ok"

run_case() {
  mkfix
  git init -q
  git config user.email t@t; git config user.name t
  mkdir -p src/main/java/com/demo/service src/main/java/com/demo/other
  printf 'package com.demo.service;\npublic class Svc {}\n' > src/main/java/com/demo/service/Svc.java
  printf 'package com.demo.other;\npublic class Oth {}\n' > src/main/java/com/demo/other/Oth.java
  git add -A && git commit -q -m init
  printf 'package com.demo.service;\npublic class Svc { int x; }\n' > src/main/java/com/demo/service/Svc.java
  printf 'package com.demo.other;\npublic class Oth { int y; }\n' > src/main/java/com/demo/other/Oth.java
  git add -A && git commit -q -m 'T-001: touch both'
  sha2=$(git rev-parse HEAD)
  # Relative arch/ — run_case runs under command-substitution; avoid $FIX races.
  mkdir -p arch
  printf '%s\n' "$sha2" > arch/sha.txt
  git reset --hard HEAD~1 >/dev/null
  cat > tasks.md <<'EOF'
#### T-001: Convert Svc
**Class**: rewrite
**Shape**: modify
**Target**: → `src/main/java/com/demo/service/Svc.java`
EOF
  out=$(python3 "$HARNESS_DIR/sfix-partial-salvage.py" "$PWD/arch" tasks.md T-001)
  echo "$out" | grep -q 'SALVAGED' || { echo "$out"; return 1; }
  echo "$out" | grep -q 'Svc.java' || { echo "$out"; return 1; }
  echo "$out" | grep -q 'dropped_oos' || { echo "expected oos drop: $out"; return 1; }
  grep -q 'int x' src/main/java/com/demo/service/Svc.java || return 1
  grep -q 'int y' src/main/java/com/demo/other/Oth.java 2>/dev/null && return 1
  echo sfixpartial-ok
}
check "O-SFIXPARTIAL salvages in-scope only (drops out-of-scope)" 0 "sfixpartial-ok"

run_case() {
  mkfix
  printf 'COVERAGE new_coverage=38.6%% (gate requires >= 80%%) — see SHIPPING.md\n' > log.txt
  python3 "$HARNESS_DIR/gate-achievability.py" log.txt; [ $? -eq 10 ] || return 1
  printf 'COMPILATION ERROR\nCOVERAGE new_coverage=38.6%% (gate requires >= 80%%)\n' > log2.txt
  python3 "$HARNESS_DIR/gate-achievability.py" log2.txt; [ $? -eq 0 ] || return 1
  echo gateachieve-ok
}
check "O-GATEACHIEVE decision-needed vs code-fixable (N14/D2)" 0 "gateachieve-ok"

run_case() {
  mkfix
  mkdir -p migration
  printf 'legacyPackage: com.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  cat > migration/dependency-order.md <<'EOF'
# Legacy dependency analysis
## Conversion order (dependencies first — the tree must compile at every commit)
1. com.example.legacy.dto.ItemDto (src/main/java/com/example/legacy/dto/ItemDto.java)
2. com.example.legacy.mapper.ItemMapper (src/main/java/com/example/legacy/mapper/ItemMapper.java)
EOF
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only service; no legacy web frontend).

#### T-001: Harvest ItemMapper types
**Class**: rewrite
**Shape**: create
**Goal**: mapper first (bad order)
**Target**: → `src/main/java/com/demo/mapper/ItemMapper.java`

#### T-002: Harvest ItemDto types
**Class**: rewrite
**Shape**: create
**Goal**: dto second (should be first)
**Target**: → `src/main/java/com/demo/dto/ItemDto.java`
EOF
  echo '[]' > f.json
  out=$(PLAN_LINT_REQUIRE_SHAPE=0 python3 "$LINT" tasks.md f.json 2>&1 || true)
  echo "$out" | grep -q 'O-PLANORDER' || { echo "expected PLANORDER: $out"; return 1; }
  echo planorder-red-ok
}
check "O-PLANORDER refuses dep-order inversion (DTO after mapper)" 0 "planorder-red-ok"

run_case() {
  mkfix
  mkdir -p migration
  printf 'legacyPackage: com.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  cat > migration/dependency-order.md <<'EOF'
## Conversion order (dependencies first — the tree must compile at every commit)
1. com.example.legacy.dto.ItemDto (src/main/java/com/example/legacy/dto/ItemDto.java)
2. com.example.legacy.mapper.ItemMapper (src/main/java/com/example/legacy/mapper/ItemMapper.java)
EOF
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only service; no legacy web frontend).

#### T-001: Harvest ItemDto types
**Class**: rewrite
**Shape**: create
**Goal**: dto first
**Target**: → `src/main/java/com/demo/dto/ItemDto.java`

#### T-002: Harvest ItemMapper types
**Class**: rewrite
**Shape**: create
**Goal**: mapper second
**Target**: → `src/main/java/com/demo/mapper/ItemMapper.java`
EOF
  echo '[]' > f.json
  out=$(PLAN_LINT_REQUIRE_SHAPE=0 python3 "$LINT" tasks.md f.json 2>&1) || true
  echo "$out" | grep -q 'LINT:O-PLANORDER' && { echo "unexpected: $out"; return 1; }
  echo "$out" | grep -q 'PLAN OK' || { echo "want PLAN OK: $out"; return 1; }
  echo planorder-ok
}
check "O-PLANORDER accepts dependency-first task order" 0 "planorder-ok"

run_case() {
  grep -q 'O-NULLACTION' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-ADDLINFO' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SFIXPARTIAL' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-GATEACHIEVE' "$HARNESS_DIR/supervisor.sh" \
    && echo f70-prompts-ok
}
check "F-70 prompt/wiring (NULLACTION/ADDLINFO/SFIXPARTIAL/GATEACHIEVE)" 0 "f70-prompts-ok"

# O-SPECFROZEN: stage_for_task_commit restores complete-story specs (R-229)
run_case() {
  mkfix
  git init -q
  git config user.email t@t
  git config user.name t
  mkdir -p specs/S01-foundation specs/S03-platform migration
  printf '# S01\n#### T-001: Keep me\n#### T-002: Keep me too\n' > specs/S01-foundation/tasks.md
  printf '# S03\n#### T-012: Profiles\n' > specs/S03-platform/tasks.md
  printf 'S01,complete,1\nS03,running,2\n' > migration/story-state.csv
  git add .
  git commit -q -m "base"
  # Gut S01 like the confused M3/worker did
  printf '# S01 gutted\n#### T-001: only one left\n' > specs/S01-foundation/tasks.md
  STORY_TASKS=specs/S03-platform/tasks.md
  eval "$(sed -n '/^complete_story_ids()/,/^stage_for_task_commit()/{ /^stage_for_task_commit()/q; p; }' "$HARNESS_DIR/supervisor.sh")"
  eval "$(sed -n '/^stage_for_task_commit()/,/^}/p' "$HARNESS_DIR/supervisor.sh")"
  stage_for_task_commit
  grep -c '^#### T-0' specs/S01-foundation/tasks.md | grep -qx 2 || { echo "s01-not-restored"; return 1; }
  git diff --cached --name-only | grep -q 'S01-foundation' && { echo "s01-still-staged"; return 1; }
  echo specfrozen-ok
}
check "stage_for_task_commit restores complete-story specs (O-SPECFROZEN)" 0 "specfrozen-ok"

# O-REDATTRIB wiring
run_case() {
  grep -q '_redattrib_gcat' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'CURRENT_TASK' "$HARNESS_DIR/supervisor.sh" \
    && echo redattrib-ok
}
check "O-REDATTRIB wiring" 0 "redattrib-ok"

# O-DELTABASE — absence without src/ is not resolved
run_case() {
  mkfix
  mkdir -p migration .hermes/harness src/main/java
  cp "$HARNESS_DIR/findings-delta.py" .hermes/harness/
  cp "$HARNESS_DIR/scaffold-presatisfied.txt" .hermes/harness/
  # before: springboot rule on a class that was never harvested + one presat rule
  cat > migration/mta-findings.json <<'EOF'
[{"violations":{
  "springboot-web-to-quarkus-99999":{"description":"x","incidents":[{"uri":"file:///legacy/Foo.java","lineNumber":1}]},
  "springboot-parent-pom-to-quarkus-00000":{"description":"y","incidents":[{"uri":"file:///pom.xml","lineNumber":1}]},
  "custom-landed-00001":{"description":"z","incidents":[{"uri":"file:///src/main/java/com/demo/Bar.java","lineNumber":1}]}
}}]
EOF
  # after: only custom-landed gone (and we plant Bar.java) + parent gone
  printf 'package com.demo;\npublic class Bar {}\n' > src/main/java/Bar.java
  cat > migration/mta-findings-after.json <<'EOF'
[{"violations":{}}]
EOF
  out=$(FINDINGS_DELTA_ROOT="$FIX" python3 .hermes/harness/findings-delta.py)
  echo "$out" | grep -q 'absent_not_landed=1' \
    && echo "$out" | grep -q 'scaffold_presatisfied=1' \
    && echo "$out" | grep -q 'resolved=1' \
    && echo "$out" | grep -q 'DELTABASE:resolved=1:absent=1' \
    && echo deltabases-ok
}
check "findings-delta splits absent vs resolved (O-DELTABASE)" 0 "deltabases-ok"

# O-FGRETRO wiring + reopen list
run_case() {
  grep -q 'fgretro-reeval.py' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'probe-reeval-needed' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'fgretro-reopen.txt' "$HARNESS_DIR/supervisor.sh" \
    && echo fgretro-ok
}
check "O-FGRETRO wiring (reeval + reopen + HOTSWAP touch)" 0 "fgretro-ok"

# K6 — findings oracle + dest-presatisfied
run_case() {
  mkfix
  mkdir -p migration .hermes/harness src/main/java
  cp "$HARNESS_DIR/findings-oracle.py" .hermes/harness/
  cp "$HARNESS_DIR/scaffold-presatisfied.txt" .hermes/harness/
  printf '<project><build><plugins><plugin><artifactId>quarkus-maven-plugin</artifactId></plugin></plugins></build></project>\n' > pom.xml
  cat > migration/mta-findings.json <<'EOF'
[{"violations":{
  "springboot-parent-pom-to-quarkus-00000":{"description":"p","incidents":[{"uri":"file:///pom.xml","lineNumber":1}]}
}}]
EOF
  cat > tasks.md <<'EOF'
#### T-001: Convert Spring Boot parent to Quarkus
**Findings**: springboot-parent-pom-to-quarkus-00000
**Goal**: Quarkus parent
EOF
  ORACLE_ROOT="$FIX" python3 .hermes/harness/findings-oracle.py tasks.md T-001; echo "rc=$?"
}
check "findings-oracle absent on Quarkus pom (K6)" 0 "rc=0"

run_case() {
  mkfix
  mkdir -p migration .hermes/harness
  cp "$HARNESS_DIR/findings-oracle.py" .hermes/harness/
  cp "$HARNESS_DIR/escw-eligible.py" .hermes/harness/
  # after-scan still has the rule → present → ESCW blocked
  cat > migration/mta-findings-after.json <<'EOF'
[{"violations":{
  "custom-still-00001":{"description":"x","incidents":[{"uri":"file:///src/main/java/Foo.java","lineNumber":1}]}
}}]
EOF
  cat > migration/mta-findings.json <<'EOF'
[{"violations":{
  "custom-still-00001":{"description":"x","incidents":[{"uri":"file:///src/main/java/Foo.java","lineNumber":1}]}
}}]
EOF
  cat > tasks.md <<'EOF'
#### T-002: Convert Foo
**Findings**: custom-still-00001
**Goal**: convert
**Target design**:
- → `src/main/java/com/demo/Foo.java`
EOF
  mkdir -p src/main/java/com/demo
  printf 'package com.demo;\npublic class Foo {}\n' > src/main/java/com/demo/Foo.java
  ALREADY_COMPLETE_ROOT="$FIX" python3 .hermes/harness/escw-eligible.py tasks.md T-002; echo "rc=$?"
}
check "escw-eligible blocks when findings still present (K6)" 0 "rc=1"

run_case() {
  mkfix
  mkdir -p migration .hermes/harness
  cp "$HARNESS_DIR/dest-presatisfied.py" .hermes/harness/
  cat > migration/mta-findings.json <<'EOF'
[{"violations":{
  "springboot-parent-pom-to-quarkus-00000":{"description":"p","incidents":[{"uri":"file:///pom.xml","lineNumber":1}]},
  "spring-ann-on-missing-00001":{"description":"j","incidents":[{"uri":"file:///Foo.java","lineNumber":1}]}
}}]
EOF
  cat > migration/mta-findings-dest-baseline.json <<'EOF'
[{"violations":{}}]
EOF
  ORACLE_ROOT="$FIX" python3 .hermes/harness/dest-presatisfied.py
  grep -q 'springboot-parent-pom-to-quarkus-00000' migration/scaffold-presatisfied.generated.txt \
    && ! grep -q 'spring-ann-on-missing-00001' migration/scaffold-presatisfied.generated.txt \
    && echo destpresat-ok
}
check "dest-presatisfied only config/landed rules (K6)" 0 "destpresat-ok"

run_case() {
  grep -q 'mta-findings-dest-baseline' "$HARNESS_DIR/analyze.sh" \
    && grep -q 'findings-oracle.py' "$HARNESS_DIR/already-complete.py" \
    && echo k6wire-ok
}
check "K6 wiring (analyze dest-baseline + already-complete oracle)" 0 "k6wire-ok"

# K7 — failure-sig capture/diff
run_case() {
  mkfix
  printf '%s\n' \
    '[ERROR] com.demo.FooTest.bar Time elapsed: 0.1 s <<< FAILURE!' \
    'src/main/java/com/demo/Foo.java:[10,1] error: cannot find symbol' \
    'S1066 FooTest.java' \
    > before.log
  printf '%s\n' \
    '[ERROR] com.demo.FooTest.bar Time elapsed: 0.1 s <<< FAILURE!' \
    '[ERROR] com.demo.FooTest.baz Time elapsed: 0.1 s <<< FAILURE!' \
    'src/main/java/com/demo/Foo.java:[10,1] error: cannot find symbol' \
    'S1066 FooTest.java' \
    > after.log
  python3 "$HARNESS_DIR/failure-sig.py" capture before.sig before.log
  python3 "$HARNESS_DIR/failure-sig.py" capture after.sig after.log
  out=$(python3 "$HARNESS_DIR/failure-sig.py" diff before.sig after.sig; echo rc=$?)
  echo "$out" | grep -q 'NEW:test:com.demo.FooTest.baz' \
    && echo "$out" | grep -q 'rc=1' \
    && echo k7diff-ok
}
check "failure-sig diffs NEW test failures (K7)" 0 "k7diff-ok"

run_case() {
  grep -q 'failure-sig.py' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'K7 FAILURE DELTA\|k7_refute_preexisting\|failure-delta' "$HARNESS_DIR/supervisor.sh" \
    && echo k7wire-ok
}
check "K7 wiring (baseline + sfix delta + refute)" 0 "k7wire-ok"

# K2-SNIP — dedup code + drop config head snips
run_case() {
  mkfix
  mkdir -p migration
  cat > migration/mta-findings.json <<'EOF'
[{"violations": {
  "cfg-00001": {
    "category": "mandatory",
    "description": "cfg",
    "incidents": [
      {"uri": "file:///pom.xml", "lineNumber": 1, "message": "POM-MSG", "codeSnip": "<?xml version=\"1.0\"?>"},
      {"uri": "file:///a/A.java", "lineNumber": 10, "message": "A-MSG", "codeSnip": "SAME_SNIP_BODY"},
      {"uri": "file:///a/B.java", "lineNumber": 20, "message": "B-MSG", "codeSnip": "SAME_SNIP_BODY"}
    ]
  }
}}]
EOF
  cat > tasks.md <<'EOF'
# Tasks
#### T-040: Snip budget
**Class**: infer
**Findings**: cfg-00001
**Goal**: snip hygiene
EOF
  out=$(python3 "$TP_PY" tasks.md T-040 qwen27b/qwen3-6-27b migration/mta-findings.json)
  echo "$out" | grep -q 'POM-MSG' \
    && ! echo "$out" | grep -q '<?xml' \
    && [ "$(echo "$out" | grep -c 'SAME_SNIP_BODY')" -eq 1 ] \
    && echo k2snip-ok
}
check "task-packet dedups snips and skips pom head (K2-SNIP)" 0 "k2snip-ok"

# K8 — verify-dep advisory
run_case() {
  out=$(python3 "$HARNESS_DIR/verify-dep.py" org.apache.commons commons-lang3 2>&1 || true)
  echo "$out" | grep -qE 'OK:verify-dep|WARN:verify-dep' && echo verifydep-ok
}
check "verify-dep advisory exits soft (K8)" 0 "verifydep-ok"

run_case() {
  grep -q 'verify-dep.py' "$HARNESS_DIR/task-packet.py" && echo k8wire-ok
}
check "K8 wiring in task-packet" 0 "k8wire-ok"

# K9 — discovered channel
run_case() {
  mkfix
  mkdir -p migration .hermes/harness
  cp "$HARNESS_DIR/append-discovered.py" .hermes/harness/
  ORACLE_ROOT="$FIX" python3 .hermes/harness/append-discovered.py T-001 src/main/Foo.java "needs Quarkus REST client"
  grep -q 'T-001' migration/discovered.md && grep -q 'needs Quarkus' migration/discovered.md && echo k9ok
}
check "append-discovered writes structured row (K9)" 0 "k9ok"

run_case() {
  grep -q 'append-discovered.py' "$HARNESS_DIR/task-packet.py" \
    && grep -q 'discovered.md' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'ensure_discovered' "$HARNESS_DIR/supervisor.sh" \
    && echo k9wire-ok
}
check "K9 wiring (packet + brief-refresh + seed)" 0 "k9wire-ok"

# K11 — rule outcome ledger wiring
run_case() {
  grep -q 'record_rule_outcomes' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'Per-rule outcomes' "$HARNESS_DIR/supervisor.sh" \
    && echo k11wire-ok
}
check "K11 wiring (record + run-report table)" 0 "k11wire-ok"

# K5 — findings-diff
run_case() {
  mkfix
  mkdir -p migration .hermes/harness
  cp "$HARNESS_DIR/findings-diff.py" .hermes/harness/
  cp "$HARNESS_DIR/scaffold-presatisfied.txt" .hermes/harness/
  cat > migration/mta-findings.json <<'EOF'
[{"violations":{
  "custom-survive-00001":{"description":"x","incidents":[{"uri":"file:///Foo.java","lineNumber":1,"message":"still here"}]},
  "springboot-parent-pom-to-quarkus-00000":{"description":"p","incidents":[{"uri":"file:///pom.xml","lineNumber":1}]}
}}]
EOF
  cat > migration/mta-findings-current.json <<'EOF'
[{"violations":{
  "custom-survive-00001":{"description":"x","incidents":[{"uri":"file:///Foo.java","lineNumber":1,"message":"still here"}]}
}}]
EOF
  ! python3 .hermes/harness/findings-diff.py migration/mta-findings.json migration/mta-findings-current.json --scope custom-survive-00001 \
    && python3 .hermes/harness/findings-diff.py migration/mta-findings.json migration/mta-findings-current.json --scope springboot-parent-pom-to-quarkus-00000 \
    && echo k5diff-ok
}
check "findings-diff RED on surviving scope (K5)" 0 "k5diff-ok"

run_case() {
  grep -q 'findings_sensor' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'findings)' "$HARNESS_DIR/sensors.sh" \
    && echo k5wire-ok
}
check "K5 wiring (milestone/preflight findings sensor)" 0 "k5wire-ok"

# --- O-RETROAPPEND / O-INSTQUAL / O-WORKERWEDGE-RCA (Poll 76 F3) ------------

run_case() {
  mkfix
  mkdir -p migration
  printf '# Retro misdiagnosis: blame coverage on test authoring\n' > migration/retro-proposals.md
  out=$(python3 "$HARNESS_DIR/archive-retro.py" --label S04 --root "$FIX")
  echo "$out" | grep -q 'retro-history/' || { echo "archive path missing: $out"; return 1; }
  grep -q 'misdiagnosis' migration/retro-history/*.md \
    && printf '# Retro story S05 — corrected\n' > migration/retro-proposals.md \
    && grep -q 'misdiagnosis' migration/retro-history/*.md \
    && grep -q 'S05' migration/retro-proposals.md \
    && echo retroappend-ok
}
check "archive-retro preserves prior proposals (O-RETROAPPEND)" 0 "retroappend-ok"

run_case() {
  grep -q 'archive-retro.py' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-RETROAPPEND' "$HARNESS_DIR/supervisor.sh" \
    && echo retroappend-wire
}
check "O-RETROAPPEND wired in phase_f_retro" 0 "retroappend-wire"

run_case() {
  python3 "$HARNESS_DIR/early-commit-gate.py" 0 && \
    ! python3 "$HARNESS_DIR/early-commit-gate.py" 1 && \
    echo escalgplace-ok
}
check "early-commit-gate refuses RED sensor_rc (O-ESCALGPLACE behavioural)" 0 "escalgplace-ok"

run_case() {
  # run_stage early path: committed → refuse_red before success (order check)
  awk '/# O-ESCALGPLACE/,/attempt=\$\(\(attempt\+1\)\)/' "$HARNESS_DIR/supervisor.sh" \
    | grep -q 'refuse_red_task_commit' && echo escalgplace-path
}
check "run_stage early-committed path calls refuse_red (O-ESCALGPLACE)" 0 "escalgplace-path"

run_case() {
  d1=$(python3 "$HARNESS_DIR/nopushpr-decide.py" 0 prev prev)
  d2=$(python3 "$HARNESS_DIR/nopushpr-decide.py" 1 prev prev)
  d3=$(python3 "$HARNESS_DIR/nopushpr-decide.py" 0 prev newrun)
  [ "$d1" = "no-trigger" ] && [ "$d2" = "judge-existing" ] && [ "$d3" = "proceed" ] \
    && echo nopushpr-ok
}
check "nopushpr-decide refuses stale PR after push (O-NOPUSHPR behavioural)" 0 "nopushpr-ok"

run_case() {
  grep -q 'nopushpr-decide.py' "$HARNESS_DIR/supervisor.sh" && echo nopushpr-wire
}
check "wait_pipeline uses nopushpr-decide.py (O-NOPUSHPR)" 0 "nopushpr-wire"

run_case() {
  mkfix
  printf 'worker wedged — no session output for 300s (O-WORKERWEDGE)\nsession JSON size frozen at 195408 bytes\n' > err.txt
  c=$(python3 "$HARNESS_DIR/wedge-classify.py" err.txt)
  [ "$c" = "JSON_STALE" ] || { echo "got $c"; return 1; }
  printf 'worker read-thrash — reads=30 globs=3 mutates=0 (O-WORKERREAD)\n' > err2.txt
  c2=$(python3 "$HARNESS_DIR/wedge-classify.py" err2.txt)
  [ "$c2" = "READ_THRASH" ] || { echo "got $c2"; return 1; }
  printf 'O-OCERR: no error pattern; session appears truncated.\nfinal text: Now I have full context. Let me\n' > err3.txt
  c3=$(python3 "$HARNESS_DIR/wedge-classify.py" err3.txt)
  [ "$c3" = "TRUNCATION" ] && echo wedge-rca-ok
}
check "wedge-classify READ_THRASH/JSON_STALE/TRUNCATION (O-WORKERWEDGE-RCA)" 0 "wedge-rca-ok"

run_case() {
  grep -q 'wedge-classify.py' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'worker-wedge-skip' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'FIRST mutate' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && echo wedge-rca-wire
}
check "O-WORKERWEDGE-RCA skip + EXECUTION FIRST-mutate tip" 0 "wedge-rca-wire"

# O-FIRSTMUT (R-222/N13): bash alone must NOT exempt read-thrash (T-007: 23 read + 2 bash + 0 edit)
run_case() {
  mkfix
  # Synthetic OpenCode-shaped events: 22 reads + 2 bash + 0 edit/write
  python3 - <<'PY' > oc.json
import json
evs = []
for i in range(22):
    evs.append({"type": "tool_use", "part": {"type": "tool", "tool": "read", "callID": f"r{i}"}})
for i in range(2):
    evs.append({"type": "tool_use", "part": {"type": "tool", "tool": "bash", "callID": f"b{i}"}})
print(json.dumps(evs))
PY
  out=$(python3 "$HARNESS_DIR/worker-read-watch.py" oc.json); rc=$?
  [ "$rc" -eq 0 ] && echo "$out" | grep -q 'read-thrash' && echo firstmut-kill
}
check "worker-read-watch kills read+bash with zero edit (O-FIRSTMUT)" 0 "firstmut-kill"

run_case() {
  mkfix
  python3 - <<'PY' > oc.json
import json
evs = [{"type": "tool_use", "part": {"type": "tool", "tool": "read", "callID": "r0"}}]
for i in range(5):
    evs.append({"type": "tool_use", "part": {"type": "tool", "tool": "read", "callID": f"r{i}"}})
evs.append({"type": "tool_use", "part": {"type": "tool", "tool": "edit", "callID": "e0"}})
print(json.dumps(evs))
PY
  python3 "$HARNESS_DIR/worker-read-watch.py" oc.json; echo "rc=$?"
}
check "worker-read-watch continues after first edit (O-FIRSTMUT)" 0 "rc=1"

run_case() {
  grep -q 'clear_worker_wedge_skip' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-WEDGESKIP' "$HARNESS_DIR/supervisor.sh" \
    && echo wedgeskip-ok
}
check "O-WEDGESKIP clears worker-wedge-skip after commit" 0 "wedgeskip-ok"

# K7 wiring audit (O-INSTQUAL): keep name-grep only as companion to behavioural
run_case() {
  # Behavioural failure-sig already above; confirm refute path is not grep-only.
  grep -q 'k7_refute_preexisting\|K7 FAILURE DELTA\|failure-delta' "$HARNESS_DIR/supervisor.sh" \
    && python3 "$HARNESS_DIR/failure-sig.py" capture /tmp/k7a.sig /dev/null 2>/dev/null || true
  printf '[ERROR] com.demo.NewTest.x Time elapsed: 0.1 s <<< FAILURE!\n' > /tmp/k7b.log
  python3 "$HARNESS_DIR/failure-sig.py" capture /tmp/k7b.sig /tmp/k7b.log
  out=$(python3 "$HARNESS_DIR/failure-sig.py" diff /tmp/k7a.sig /tmp/k7b.sig; echo rc=$?)
  echo "$out" | grep -q 'rc=1\|NEW' && echo k7beh-ok || echo "$out"
}
check "K7 failure-sig behavioural NEW delta (O-INSTQUAL audit)" 0 "k7beh-ok"

# K4 — contract-as-rules from migration.yaml
run_case() {
  mkfix
  cat > migration.yaml <<'EOF'
preserve:
  - CATALOG_ENDPOINT
  - PAYMENT_URL
forbidden:
  - getMockProducts
  - "Fallback to mock"
acceptance:
  path: /api/cart/acceptance-check
EOF
  python3 "$HARNESS_DIR/gen-contract-rules.py" --yaml migration.yaml --out out.yaml
  grep -q 'demo-preserve-catalog-endpoint-00001' out.yaml \
    && grep -q 'demo-preserve-payment-url-00001' out.yaml \
    && grep -q 'demo-forbidden-getmockproducts-00001' out.yaml \
    && grep -q 'demo-forbidden-exception-mapper-00001' out.yaml \
    && grep -q 'demo-acceptance-surface-00001' out.yaml \
    && echo k4gen-ok
}
check "gen-contract-rules emits preserve/forbidden/acceptance (K4)" 0 "k4gen-ok"

run_case() {
  grep -q 'gen-contract-rules.py' "$HARNESS_DIR/analyze.sh" && echo k4wire-ok
}
check "analyze.sh runs gen-contract-rules before kantra (K4)" 0 "k4wire-ok"

# O-STAMP-AUTO / O-STAMP-GATE (F-4)
STAMP_FIX="$HARNESS_DIR/tests/fixtures"
run_case() {
  mkfix
  legacy="$STAMP_FIX/stamp-petclinic"
  python3 "$HARNESS_DIR/contract-stamp.py" stamp --legacy "$legacy" --yaml migration.yaml --write --json \
    | python3 -c "import json,sys; d=json.load(sys.stdin); a=d['acceptance']; m=d['migration']; \
assert m['legacyPackage']=='org.springframework.samples.petclinic'; \
assert a['path']=='/petclinic/api/vets'; assert a['collection']=='_array'; \
assert a['getter']=='getAllVets'; assert a['service']=='ClinicService'; \
assert a['itemType']=='VetDto'; \
assert 'endpointEnv' not in a; print('stamp-petclinic-ok')"
}
check "contract-stamp petclinic fixture matches F-2 acceptance (O-STAMP-AUTO)" 0 "stamp-petclinic-ok"

run_case() {
  mkfix
  legacy="$STAMP_FIX/stamp-petclinic"
  python3 "$HARNESS_DIR/contract-stamp.py" stamp --legacy "$legacy" --yaml migration.yaml --write >/dev/null
  python3 "$HARNESS_DIR/contract-stamp-gate.py" --legacy "$legacy" --yaml migration.yaml \
    && echo stamp-petclinic-gate-ok
}
check "contract-stamp petclinic gate GREEN (O-STAMP-GATE)" 0 "stamp-petclinic-gate-ok"

run_case() {
  mkfix
  legacy="$STAMP_FIX/stamp-cart"
  python3 "$HARNESS_DIR/contract-stamp.py" stamp --legacy "$legacy" --yaml migration.yaml --write --json \
    | python3 -c "import json,sys; d=json.load(sys.stdin); a=d['acceptance']; m=d['migration']; \
assert m['legacyPackage']=='com.redhat.coolstore' and m['targetPackage']=='com.demo'; \
assert a['path']=='/api/cart/acceptance-check' and a['collection']=='products'; \
assert a['getter']=='getProducts' and a['service']=='CatalogService'; \
assert a['itemType']=='Product' and a['endpointEnv']=='CATALOG_ENDPOINT'; \
assert a['needsDatabase'] is False; print('stamp-cart-ok')"
}
check "contract-stamp cart fixture regression (O-STAMP-AUTO)" 0 "stamp-cart-ok"

run_case() {
  mkfix
  legacy="$STAMP_FIX/stamp-surfaceless"
  python3 "$HARNESS_DIR/contract-stamp.py" stamp --legacy "$legacy" --yaml migration.yaml --write --json \
    | python3 -c "import json,sys; d=json.load(sys.stdin); \
assert d['contract']['status']=='UNDECIDED'; assert d['acceptance']['path']=='UNDECIDED'; \
print('stamp-undecided-ok')"
  rc=0
  python3 "$HARNESS_DIR/contract-stamp-gate.py" --legacy "$legacy" --yaml migration.yaml >/dev/null 2>&1 || rc=$?
  [ "$rc" = "1" ] && echo gate-hold-ok
}
check "contract-stamp surface-less → UNDECIDED + gate hold (O-STAMP-GATE)" 0 "gate-hold-ok"

run_case() {
  grep -q 'O-STAMP-AUTO' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'contract-stamp.py' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'contract-stamp-gate.py' "$HARNESS_DIR/outer-loop.sh" \
    && echo stamp-wire-ok
}
check "outer-loop wires contract-stamp before M1 analyze (O-STAMP-AUTO)" 0 "stamp-wire-ok"

# K12 — adversarial refute
run_case() {
  mkfix
  cat > bad.diff <<'EOF'
diff --git a/src/test/java/T.java b/src/test/java/T.java
--- a/src/test/java/T.java
+++ b/src/test/java/T.java
@@ -1,3 +1,4 @@
+    assertThat(true).isTrue();
EOF
  out=$(python3 "$HARNESS_DIR/refute-diff.py" --diff bad.diff 2>&1) || true
  echo "$out" | grep -q 'G-PLACE' && echo k12place-ok
}
check "refute-diff REFUTES ceremonial assertThat(true) (K12)" 0 "k12place-ok"

run_case() {
  mkfix
  cat > bad.diff <<'EOF'
diff --git a/src/main/java/M.java b/src/main/java/M.java
--- a/src/main/java/M.java
+++ b/src/main/java/M.java
@@ -1,2 +1,3 @@
+public class M implements ExceptionMapper<Exception> {
EOF
  out=$(python3 "$HARNESS_DIR/refute-diff.py" --diff bad.diff 2>&1) || true
  echo "$out" | grep -q 'MAPPER-EXCEPTION' && echo k12map-ok
}
check "refute-diff REFUTES ExceptionMapper<Exception> (K12)" 0 "k12map-ok"

run_case() {
  mkfix
  cat > ok.diff <<'EOF'
diff --git a/src/main/java/Ok.java b/src/main/java/Ok.java
--- a/src/main/java/Ok.java
+++ b/src/main/java/Ok.java
@@ -1,2 +1,3 @@
+  public List<Product> products() { return catalog.products(); }
EOF
  python3 "$HARNESS_DIR/refute-diff.py" --diff ok.diff
}
check "refute-diff PASS on honest catalog call (K12)" 0 "PASS"

# O-K12WEAKTEST: annotation isNotNull + strong asserts must PASS; bare isNotNull REFUTES
run_case() {
  mkfix
  cat > test.diff <<'EOF'
diff --git a/src/test/java/com/demo/model/OwnerTest.java b/src/test/java/com/demo/model/OwnerTest.java
--- a/src/test/java/com/demo/model/OwnerTest.java
+++ b/src/test/java/com/demo/model/OwnerTest.java
@@ -1,2 +1,6 @@
+        assertThat(addressField.getAnnotation(NotEmpty.class)).isNotNull();
+        assertThat(foundPet).isNotNull();
+        assertThat(foundPet.getName()).isEqualTo("Spot");
EOF
  out=$(python3 "$HARNESS_DIR/refute-diff.py" --diff test.diff 2>&1) || true
  echo "$out" | grep -q 'PASS' && echo k12weaktest-ok
}
check "refute-diff PASS on characterization isNotNull+isEqualTo (O-K12WEAKTEST)" 0 "k12weaktest-ok"

# O-K12NEST: nested getOwner() must not defeat strong-assert detection
run_case() {
  mkfix
  cat > nest.diff <<'EOF'
diff --git a/src/test/java/com/demo/CircularGroupIntegrationTest.java b/src/test/java/com/demo/CircularGroupIntegrationTest.java
--- a/src/test/java/com/demo/CircularGroupIntegrationTest.java
+++ b/src/test/java/com/demo/CircularGroupIntegrationTest.java
@@ -1,2 +1,5 @@
+        assertThat(owner).isNotNull();
+        assertThat(pet.getOwner()).isSameAs(owner);
+        assertThat(pet.getVisits()).isNotEmpty();
EOF
  out=$(python3 "$HARNESS_DIR/refute-diff.py" --diff nest.diff 2>&1) || true
  echo "$out" | grep -q 'PASS' && echo k12nest-ok
}
check "refute-diff PASS on nested-paren AssertJ (O-K12NEST)" 0 "k12nest-ok"

run_case() {
  mkfix
  cat > weak.diff <<'EOF'
diff --git a/src/test/java/com/demo/WeakTest.java b/src/test/java/com/demo/WeakTest.java
--- a/src/test/java/com/demo/WeakTest.java
+++ b/src/test/java/com/demo/WeakTest.java
@@ -1,2 +1,3 @@
+        assertThat(result).isNotNull();
EOF
  out=$(python3 "$HARNESS_DIR/refute-diff.py" --diff weak.diff 2>&1) || true
  echo "$out" | grep -q 'WEAK-ASSERT' && echo k12weakonly-ok
}
check "refute-diff REFUTES bare isNotNull-only test (O-K12WEAKTEST)" 0 "k12weakonly-ok"

run_case() {
  grep -q 'refute_high_stakes' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'refute-diff.py' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'ship-blocked-k12' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'K12 refused escalation' "$HARNESS_DIR/supervisor.sh" \
    && echo k12wire-ok
}
check "K12 wired on escalation + pre-push ship" 0 "k12wire-ok"

# K10 — solved-example hints
run_case() {
  mkfix
  mkdir -p migration/hints
  printf 'Replace javax.* with jakarta.* via harvest; keep package rename from migration.yaml.\n' \
    > migration/hints/springboot-javax-to-jakarta-00000.md
  cat > tasks.md <<'EOF'
#### T-001: Jakarta rename
**Class**: rewrite
**Findings**: springboot-javax-to-jakarta-00000
**Goal**: Rename javax imports
**Acceptance**: compiles
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-001)
  echo "$out" | grep -q 'Solved-example hints' \
    && echo "$out" | grep -q 'springboot-javax-to-jakarta-00000' \
    && echo k10inj-ok
}
check "task-packet injects migration/hints (K10)" 0 "k10inj-ok"

run_case() {
  mkfix
  mkdir -p migration/hints
  ! python3 "$HARNESS_DIR/write-hint.py" demo-rule-00001 'use coolstore CartEndpoint' \
    && python3 "$HARNESS_DIR/write-hint.py" demo-rule-00001 'Feign → @RegisterRestClient + @RestClient inject' \
    && grep -q 'RegisterRestClient' migration/hints/demo-rule-00001.md \
    && echo k10write-ok
}
check "write-hint rejects specimen ids and writes clean hint (K10)" 0 "k10write-ok"

# O-UXLOG Wave A (Poll 77)
run_case() {
  # Must not unconditionally truncate; must resume-append.
  ! grep -qE '^: > "\$LOG"$' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-UXLOG-TRUNC' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'RESUME outer-loop' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'Resuming:.*stories complete' "$HARNESS_DIR/outer-loop.sh" \
    && echo uxtrunc-ok
}
check "outer-loop appends log + RESUME banner (O-UXLOG-TRUNC)" 0 "uxtrunc-ok"

run_case() {
  grep -q 'O-UXLOG-SENSE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'SENSE task sensor GREEN' "$HARNESS_DIR/supervisor.sh" \
    && echo uxsense-ok
}
check "post_commit_verify mirrors GREEN sense (O-UXLOG-SENSE)" 0 "uxsense-ok"

run_case() {
  grep -q 'O-UXLOG-SHIP' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'waiting for factory pipeline' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'acceptance probe:' "$HARNESS_DIR/supervisor.sh" \
    && echo uxship-ok
}
check "M5 ship milestones mirrored to outer_log (O-UXLOG-SHIP)" 0 "uxship-ok"

run_case() {
  grep -q 'O-SPECREBASE' "$HARNESS_DIR/outer-loop.sh" && echo specrebase-ok
}
check "O-SPECREBASE wiring in outer-loop" 0 "specrebase-ok"

run_case() {
  grep -q 'O-JDBCREGRESS' "$HARNESS_DIR/commit-hygiene.py" \
    && grep -q 'present:JpaRepositoryImpl-cdi\|jdbc.repository' "$HARNESS_DIR/already-complete.py" \
    && echo jdbcregress-ok
}
check "O-JDBCREGRESS / O-JDBCSKIP wiring" 0 "jdbcregress-ok"

run_case() {
  grep -q 'is_convert_task\|O-ACRESTABS' "$HARNESS_DIR/already-complete.py" \
    && grep -q 'throws\\s\*Exception\|O-FIDSONAR' "$HARNESS_DIR/harvest-fidelity.py" \
    && echo acrestabs-ok
}
check "O-ACRESTABS / O-FIDSONAR wiring" 0 "acrestabs-ok"

# O-ESCALORACLE: Shape + Oracle on packet; escalation prompt forbids fabricate-delete
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-090: Remove Spring Boot main application class
**Class**: rewrite
**Goal**: Delete PetClinicApplication — Quarkus has no main
**Owns**: src/main/java/org/springframework/samples/petclinic/PetClinicApplication.java
**Acceptance**: PetClinicApplication.java absent; mvn -q test
EOF
  out=$(python3 "$TP_PY" tasks.md T-090 qwen27b/qwen3-6-27b)
  echo "$out" | grep -qE '^Shape:[[:space:]]*remove' \
    && echo "$out" | grep -qE '^Oracle:[[:space:]]*absent' \
    && echo "$out" | grep -q 'O-ESCALORACLE' \
    && grep -q 'O-ESCALORACLE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'esc_oracle' "$HARNESS_DIR/supervisor.sh" \
    && echo escaloracle-ok
}
check "task-packet+supervisor carry Shape/Oracle on escalation (O-ESCALORACLE)" 0 "escaloracle-ok"

# O-ACCEPTPROBE: acceptance log names the index URL that scored 200
run_case() {
  grep -q 'ACC_INDEX_URL' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-ACCEPTPROBE' "$HARNESS_DIR/supervisor.sh" \
    && echo acceptprobe-ok
}
check "acceptance probe logs winning index URL (O-ACCEPTPROBE)" 0 "acceptprobe-ok"

# O-SFIXWORKER / O-M3WORKER: Qwen-first routing with MiniMax rescue/backstop
run_case() {
  grep -q 'WORKER_SFIX_FIRST' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'run_worker_prompt' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SFIXWORKER' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'sfix_minimax_rescue' "$HARNESS_DIR/supervisor.sh" \
    && echo sfixworker-ok
}
check "sensor-fix Qwen-first + MiniMax rescue wiring (O-SFIXWORKER)" 0 "sfixworker-ok"

run_case() {
  grep -q 'SFIX_MINIMAX_RESCUE_MAX' "$HARNESS_DIR/supervisor.sh" \
    && grep -qE 'while \[ "\$_sfix_rescue" -lt "\$\{SFIX_MINIMAX_RESCUE_MAX' "$HARNESS_DIR/supervisor.sh" \
    && echo sfixcap-ok
}
check "sfix MiniMax rescue capped by SFIX_MINIMAX_RESCUE_MAX (R-218)" 0 "sfixcap-ok"

# O-T1FINDINGS behavioural (R-223): stage_for_task_commit must leave findings unstaged
run_case() {
  mkfix
  git init -q
  git config user.email t@test.local
  git config user.name t
  mkdir -p migration src/main/resources .hermes
  printf 'quarkus.http.port=8080\n' > src/main/resources/application.properties
  printf '{"ok":true}\n' > migration/mta-findings-current.json
  git add -A && git commit -q -m init
  printf 'quarkus.http.port=8080\n# touched\n' > src/main/resources/application.properties
  printf '{"stale":true,"port":9966}\n' > migration/mta-findings-current.json
  # Inline the staging helper (same as supervisor stage_for_task_commit)
  git add -A
  git reset -q -- .hermes migration/staging migration/mta-findings-current.json 2>/dev/null || true
  git commit -q -m "T-007: Convert Database Configuration Properties"
  if git diff-tree --no-commit-id --name-only -r HEAD | grep -qx 'migration/mta-findings-current.json'; then
    echo "FAIL: findings still in tip"; return 1
  fi
  git diff-tree --no-commit-id --name-only -r HEAD | grep -q 'application.properties' \
    && echo t1findings-ok
}
check "stage_for_task_commit excludes mta-findings-current.json (O-T1FINDINGS behavioural)" 0 "t1findings-ok"

# O-T1FINDESC behavioural: scrub_findings_from_tip rewrites a tip that swept findings
run_case() {
  mkfix
  git init -q
  git config user.email t@test.local
  git config user.name t
  mkdir -p migration src/main/resources
  printf 'port=8080\n' > src/main/resources/application.properties
  printf '{"base":true}\n' > migration/mta-findings-current.json
  git add -A && git commit -q -m init
  printf 'port=8080\nx\n' > src/main/resources/application.properties
  printf '{"stale":9966}\n' > migration/mta-findings-current.json
  git add -A
  git commit -q -m "T-007: Convert Database Configuration Properties"
  # Extract + run scrub (LOG required by helper)
  LOG=/dev/null
  # shellcheck disable=SC1090
  eval "$(sed -n '/^scrub_findings_from_tip()/,/^}/p' "$HARNESS_DIR/supervisor.sh")"
  scrub_findings_from_tip
  if git diff-tree --no-commit-id --name-only -r HEAD | grep -qx 'migration/mta-findings-current.json'; then
    echo "FAIL: findings still in tip after scrub"; return 1
  fi
  grep -q '"base":true' migration/mta-findings-current.json \
    && git log -1 --format=%s | grep -q '^T-007:' \
    && echo t1findesc-ok
}
check "scrub_findings_from_tip removes findings from escalation tip (O-T1FINDESC)" 0 "t1findesc-ok"

run_case() {
  grep -q 'WORKER_M3_FIRST' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-M3WORKER' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q '^wchat()' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M3_ORCH_BACKSTOP' "$HARNESS_DIR/outer-loop.sh" \
    && echo m3worker-ok
}
check "M3 Qwen draft + MiniMax backstop wiring (O-M3WORKER)" 0 "m3worker-ok"

run_case() {
  mkfix
  mkdir -p migration src/main/java/com/demo
  printf 'package com.demo; class A {}\n' > src/main/java/com/demo/A.java
  cat > migration/mta-findings.json <<'J'
[{"violations": {
  "rule-landed-00001": {"category":"mandatory","incidents":[{"uri":"file:///x/A.java"}]},
  "localhost-jdbc-00002": {"category":"mandatory","incidents":[{"uri":"file:///x/Db.java"}]},
  "rule-absent-00003": {"category":"mandatory","incidents":[{"uri":"file:///x/Missing.java"}]}
}}]
J
  echo '[]' > migration/mta-findings-after.json
  printf 'localhost-jdbc-00002\n' > migration/deferred-by-decision.txt
  out=$(python3 "$HARNESS_DIR/findings-delta.py" 2>&1)
  echo "$out" | grep -q 'deferred_by_decision=1' || { echo "$out"; return 1; }
  echo "$out" | grep -q 'absent_not_landed=1' || { echo "$out"; return 1; }
  echo "$out" | grep -q 'resolved=1' || { echo "$out"; return 1; }
  echo "$out" | grep -q 'DEFERRED-BY-DECISION' || { echo "$out"; return 1; }
  echo deferred-ok
}
check "O-LEDGERFALSE deferred_by_decision class (F-60)" 0 "deferred-ok"

run_case() {
  grep -q 'O-PREFLIGHTDIM' "$SENSORS" \
    && grep -q 'preflight-count' "$SENSORS" \
    && grep -q 'preflight-count' "$HARNESS_DIR/supervisor.sh" \
    && echo preflightdim-ok
}
check "O-PREFLIGHTDIM wiring (cap + ship reset)" 0 "preflightdim-ok"

echo "----"
echo "$PASS/$N passed"
if [ "$FAIL" -ne 0 ]; then
  echo "# instruments FAIL count=$FAIL" >&2
  exit 1
fi
exit 0

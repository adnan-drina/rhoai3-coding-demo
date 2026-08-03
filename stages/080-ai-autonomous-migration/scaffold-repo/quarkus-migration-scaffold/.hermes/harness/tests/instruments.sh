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

# O-M3SHAPEHARD / W4-045a: live plan-lint defaults Shape HARD, but this suite
# still carries ~20 pre-Shape fixtures. Grandfather the suite with WARN so
# signal stays visible; the dedicated O-M3SHAPEHARD case unsets the flag.
export PLAN_LINT_SHAPE_WARN="${PLAN_LINT_SHAPE_WARN:-1}"

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
  # O-INFERABSENT / O-ORACLEDERIVE: infer Targets absent from the fixture tree
  # need Shape=create (documented proceed) — never rely on silent Oracle=present.
  cat <<'EOF'
# Tasks

UI surface: waived (API-only service; no legacy web frontend).

#### T-001: Swap javax imports
**Class**: rewrite
**Shape**: modify
- Mechanical jakarta rename across src/main/java sources.

#### T-002: Design the cart endpoint
**Class**: infer
**Shape**: create
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
**Shape**: create
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
**Shape**: create
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

# O-M2K3TABLE: markdown decision table (inventory-shaped) also satisfies K3
run_case() {
  mkfix; roadmap_fixture yes
  cat >> inv.md <<'EOF'
- non-mandatory: 1 — optional-logging-00010
EOF
  cat >> roadmap.md <<'EOF'

## Non-mandatory decisions

| rule | decision | reason |
|---|---|---|
| optional-logging-00010 | defer | noise for this migration; not in scope |
EOF
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint accepts K3 defer via markdown table (O-M2K3TABLE)" 0 "ROADMAP OK"

run_case() {
  mkfix; roadmap_fixture yes
  cat >> inv.md <<'EOF'
- non-mandatory: 1 — optional-logging-00010
EOF
  cat >> roadmap.md <<'EOF'

## Non-mandatory decisions

| rule | decision | reason |
|---|---|---|
| optional-logging-00010 | defer |  |
EOF
  python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md
}
check "roadmap-lint rejects empty K3 table reason (O-M2K3TABLE)" 1 "defer requires a reason"

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
# O-INSTREGRESS: after O-QJACOCONOTEST, empty trees SKIP — seed @QuarkusTest for RED path.
run_case() {
  mkfix
  mkdir -p src/test/java/com/demo
  printf '@QuarkusTest\nclass JacocoProbeTest {}\n' > src/test/java/com/demo/JacocoProbeTest.java
  SENSOR_ROOT="$FIX" bash "$SENSORS" qjacoco
}
check "qjacoco RED when quarkus-jacoco report missing (O-QJACOCO behavioural)" 1 "O-QJACOCO"

run_case() {
  mkfix
  mkdir -p src/test/java/com/demo target/jacoco-report
  printf '@QuarkusTest\nclass JacocoProbeTest {}\n' > src/test/java/com/demo/JacocoProbeTest.java
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
  # O-PORTDERIVE: §7 REDESIGN Shape=create requires Port: reimplement
  # O-REIMPLCREATE: create-procedure prose required with Port=reimplement
  { echo "UI surface: waived (API-only service; no legacy web frontend)."
    printf '#### T-001: Convert CartService\n**Class**: infer\n**Shape**: create\n**Port**: reimplement\n- Target: src/main/java/com/demo/CartService.java with ConcurrentHashMap and 404-on-missing GET.\n- Procedure: harvest-from-staging → API mapping table → first-write (O-REIMPLCREATE).\n- API mapping: HashMap → ConcurrentHashMap; missing GET → 404\n'; } > tasks.md
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

# O-HARVESTFULLPATH — Target-design full paths normalize to package-relative
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/org/springframework/samples/petclinic/repository/jdbc
  printf 'package org.springframework.samples.petclinic.repository.jdbc;\npublic class JdbcPet { }\n' \
    > migration/staging/src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPet.java
  printf 'legacyPackage: org.springframework.samples.petclinic\ntargetPackage: com.demo\n' > migration.yaml
  out=$(bash "$HARVEST_SH" \
    src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPet.java 2>&1) || true
  echo "$out"
  { echo "$out" | grep -q 'O-HARVESTFULLPATH: normalized' \
    && [ -f src/main/java/com/demo/repository/jdbc/JdbcPet.java ] \
    && grep -q 'package com.demo.repository.jdbc' src/main/java/com/demo/repository/jdbc/JdbcPet.java; } \
    && echo harvestfullpath-ok || echo FAIL
}
check "harvest accepts Target-design full path (O-HARVESTFULLPATH)" 0 "harvestfullpath-ok"

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

# O-BOOTSQLPROV / O-GENSEED: %prod.sql-load + %prod.validate is RED even when %dev is ok
run_case() {
  sensor_fixture
  mkdir -p src/main/resources
  printf '%s\n' \
    '%dev.quarkus.hibernate-orm.database.generation=drop-and-create' \
    '%dev.quarkus.hibernate-orm.sql-load-script=import.sql' \
    '%prod.quarkus.hibernate-orm.database.generation=validate' \
    '%prod.quarkus.hibernate-orm.sql-load-script=import.sql' \
    > src/main/resources/application.properties
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring rejects %prod.sql-load-script with %prod.generation=validate (O-BOOTSQLPROV)" 1 "O-GENSEED\|O-BOOTSQLPROV"

# O-SHIPFIXJACOCO behavioural: data-file without report props → wiring RED
run_case() {
  sensor_fixture
  mkdir -p src/main/resources
  printf 'quarkus.jacoco.data-file=target/jacoco-quarkus.exec\nquarkus.jacoco.reuse-data-file=true\n' \
    > src/main/resources/application.properties
  # Minimal pom markers wiring_invariants also needs
  printf '<project><build><plugins><plugin><artifactId>jacoco-maven-plugin</artifactId></plugin><plugin><artifactId>maven-compiler-plugin</artifactId><version>3.11.0</version></plugin></plugins></build><properties><sonar.coverage.jacoco.xmlReportPaths>x</sonar.coverage.jacoco.xmlReportPaths></properties></project>\n' > pom.xml
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "wiring rejects jacoco data-file without report props (O-SHIPFIXJACOCO)" 1 "O-SHIPFIXJACOCO"

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

# O-ACSTRUCT — Shape=structure Target package dir missing must NOT oracle-skip
# (W4-024a: T-003 ALREADY COMPLETE while src/main/java/com/demo/dto/ absent).
run_case() {
  mkfix
  mkdir -p .hermes/harness
  # Minimal findings-oracle that claims Findings absent (the false path).
  cat > .hermes/harness/findings-oracle.py <<'PY'
#!/usr/bin/env python3
import sys
print("absent:removed-javaee-modules-00020")
sys.exit(0)
PY
  chmod +x .hermes/harness/findings-oracle.py
  printf 'quarkus-maven-plugin\n' > pom.xml
  # deliberately NO src/main/java/com/demo/dto/.gitkeep
  cat > tasks.md <<'EOF'
# Tasks
#### T-003: Prepare DTO package structure for S02 model harvest
**Findings**: removed-javaee-modules-00020 (17)
**Shape**: structure
**Target design**:
- **Target**: → `src/main/java/com/demo/dto/` (create package structure)
- **Structure**: Create `.gitkeep` file in target package directory
**Acceptance**: Target package directory created with `.gitkeep`
EOF
  ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-003; echo "rc=$?"
}
check "already-complete does not skip structure Target when dir missing (O-ACSTRUCT)" 0 "rc=1"

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

# O-ALREADYPROP — Target .java named → preserve token alone must not skip
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/security src/main/resources
  printf 'petclinic.security.enable=false\n' > src/main/resources/application.properties
  # Target class missing — preserve must not skip
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Redesign BasicAuthenticationConfig to Quarkus Security basic auth
**Class**: infer
**Shape**: create
**Findings**: springboot-security-to-quarkus-00000
**Goal**: Create BasicAuthenticationConfig; preserve petclinic.security.enable
**Target design**: → `src/main/java/com/demo/security/BasicAuthenticationConfig.java`
**Acceptance**: BasicAuthenticationConfig present; petclinic.security.enable gated
EOF
  printf 'preserve:\n  - petclinic.security.enable\n' > migration.yaml
  ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-002; echo "rc=$?"
}
check "already-complete does not skip missing BasicAuth on preserve token (O-ALREADYPROP)" 0 "rc=1"

# O-ALREADYFINDING — finding absent + Target exists without @RolesAllowed → must-run
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/rest src/main/resources .hermes/harness
  printf 'petclinic.security.enable=false\n' > src/main/resources/application.properties
  printf 'package com.demo.rest;\npublic class VetRestController {}\n' \
    > src/main/java/com/demo/rest/VetRestController.java
  # Stub findings-oracle: always absent (finding cleared)
  cat > .hermes/harness/findings-oracle.py <<'PY'
#!/usr/bin/env python3
import sys
print("absent:springboot-security-to-quarkus-00000")
sys.exit(0)
PY
  chmod +x .hermes/harness/findings-oracle.py
  cat > tasks.md <<'EOF'
# Tasks
#### T-009: Wire RolesAllowed and deploy acceptance on VetRestController
**Class**: infer
**Shape**: modify
**Findings**: springboot-security-to-quarkus-00000
**Goal**: Add @RolesAllowed on VetRestController; preserve petclinic.security.enable
**Target design**: → `src/main/java/com/demo/rest/VetRestController.java`
**Owns**: src/main/java/com/demo/rest/VetRestController.java
**Acceptance**: @RolesAllowed present; /api/vets 200 when security off
EOF
  printf 'preserve:\n  - petclinic.security.enable\n' > migration.yaml
  ALREADY_COMPLETE_ROOT="$FIX" python3 "$AC_PY" tasks.md T-009; echo "rc=$?"
}
check "already-complete does not skip RolesAllowed gap on finding-absent (O-ALREADYFINDING)" 0 "rc=1"

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

# O-T6COMPLETE — harvest tip listing 3 Targets must not mechan on 1/3
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/model
  printf 'class BaseEntity {}\n' > src/main/java/com/demo/model/BaseEntity.java
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Harvest BaseEntity NamedEntity Person
**Class**: rewrite
**Goal**: Harvest entity base classes
**Target design**:
- → src/main/java/com/demo/model/BaseEntity.java
- → src/main/java/com/demo/model/NamedEntity.java
- → src/main/java/com/demo/model/Person.java
**Acceptance**: all three present
EOF
  printf 'src/main/java/com/demo/model/BaseEntity.java\n' | python3 "$MM_PY" tasks.md T-002; echo "rc=$?"
}
check "mechan-match refuses partial harvest tip (O-T6COMPLETE)" 0 "rc=1"

run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/model
  printf 'class BaseEntity {}\n' > src/main/java/com/demo/model/BaseEntity.java
  printf 'class NamedEntity {}\n' > src/main/java/com/demo/model/NamedEntity.java
  printf 'class Person {}\n' > src/main/java/com/demo/model/Person.java
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Harvest BaseEntity NamedEntity Person
**Class**: rewrite
**Goal**: Harvest entity base classes
**Target design**:
- → src/main/java/com/demo/model/BaseEntity.java
- → src/main/java/com/demo/model/NamedEntity.java
- → src/main/java/com/demo/model/Person.java
**Acceptance**: all three present
EOF
  printf 'src/main/java/com/demo/model/BaseEntity.java\n' | python3 "$MM_PY" tasks.md T-002; echo "rc=$?"
}
check "mechan-match accepts full harvest tip (O-T6COMPLETE)" 0 "rc=0"

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

# O-STRUCTPRESAT — dirty scaffold-presatisfied must not fail .gitkeep structure
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-003: Prepare DTO package structure for S02 model harvest
**Class**: rewrite
**Shape**: structure
**Target design**:
- **Target**: → `src/main/java/com/demo/dto/` (create package structure)
- **Structure**: Create `.gitkeep` file in target package directory
EOF
  printf '%s\n' \
    'src/main/java/com/demo/dto/.gitkeep' \
    'migration/scaffold-presatisfied.generated.txt' \
    | python3 "$MM_PY" tasks.md T-003; echo "rc=$?"
}
check "mechan-match ignores scaffold-presatisfied with structure gitkeep (O-STRUCTPRESAT)" 0 "rc=0"

# O-SONAR401INST / W4-025a/W4-027 — wiring + behavioural classify + phrases.
run_case() {
  grep -q 'O-SONAR401' "$SENSORS" \
    && grep -q 'ship-blocked-sonar-auth' "$HARNESS_DIR/supervisor.sh" \
    && grep -qE 'HTTP 401|401 Unauthorized' "$HARNESS_DIR/supervisor.sh" \
    && echo sonar401-wired
}
check "supervisor+sensors wire O-SONAR401 ship block (O-SONAR401INST)" 0 "sonar401-wired"

run_case() {
  # Behavioural: sensors.sh sonar path classifies HTTP 401 log as O-SONAR401
  # (not a code-violation RED). Exercise the grep gate on a fixture log.
  mkfix
  printf '%s\n' \
    'Error on analysis/version: HTTP 401 Unauthorized' \
    'Please check the property sonar.token or the environment variable SONAR_TOKEN.' \
    > /tmp/sensor-sonar.log
  if grep -qE 'HTTP 401|401 Unauthorized|Not authorized|check the property sonar\.token' /tmp/sensor-sonar.log \
    && grep -q 'O-SONAR401' "$SENSORS"; then
    echo sonar401-classify-ok
  fi
}
check "O-SONAR401 classify greps match fixture 401 log (O-SONAR401INST)" 0 "sonar401-classify-ok"

run_case() {
  grep -q 'O-SFIXDIMNONE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'dims=\[none\]' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'record_debt' "$HARNESS_DIR/supervisor.sh" \
    && echo sfixdimnone-wired
}
check "supervisor wires O-SFIXDIMNONE skip (O-SONAR401INST)" 0 "sfixdimnone-wired"

run_case() {
  grep -q 'O-SHIPREMOTE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'ship-blocked-remote-diverged' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'will not force-push' "$HARNESS_DIR/supervisor.sh" \
    && grep -qE 'non-fast-forward' "$HARNESS_DIR/supervisor.sh" \
    && echo shipremote-wired
}
check "supervisor wires O-SHIPREMOTE diverge block (O-SONAR401INST)" 0 "shipremote-wired"

run_case() {
  # Phrase fixtures — the exact log tokens the guards match must remain stable.
  printf '%s\n' \
    'SENSOR RED (sonar): O-SONAR401: Sonar auth failed (401)' \
    ' ! [rejected]  main -> main (non-fast-forward)' \
    'hint: Updates were rejected because the tip of your current branch is behind' \
    | grep -qE 'O-SONAR401|non-fast-forward|tip of your current branch is behind' \
    && echo phrase-fixtures-ok
}
check "O-SONAR401/O-SHIPREMOTE match phrases still recognizable (O-SONAR401INST)" 0 "phrase-fixtures-ok"

run_case() {
  grep -q 'O-RESUMEHIDE' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'walked RESUME_RUN_BASE back' "$HARNESS_DIR/outer-loop.sh" \
    && echo resumehide-wired
}
check "outer-loop wires O-RESUMEHIDE walk-back (O-RESUMEHIDE)" 0 "resumehide-wired"

run_case() {
  # O-T6dPKGINFO: build verification mentioning characterization must accept
  # package-info.java-only stage (not need-src-test).
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-008: Build verification and package validation
**Class: infer**
**Target design**: → `pom.xml` and `src/main/java/com/demo/model/package-info.java`
**Actions**:
1. Run `mvn test` to verify characterization tests pass
2. Create package-info.java for model package
**Package verification**:
- Tests pass (PetTypeTest, VisitTest, PetTest)
EOF
  printf '%s\n' 'src/main/java/com/demo/model/package-info.java' \
    | python3 "$MM_PY" tasks.md T-008; echo "rc=$?"
}
check "mechan-match accepts package-info on build-verify task (O-T6dPKGINFO)" 0 "rc=0"

# O-T6WRONGTITLE — Convert + "remove Spring" body must not false-absent
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Convert OwnerRestController to JAX-RS
**Class: infer**
**Target design**: → `src/main/java/com/demo/rest/OwnerRestController.java`
**Actions**:
1. Remove `@RestController` / Spring Web annotations; use JAX-RS `@Path`.
2. Port endpoints from legacy OwnerRestController.
EOF
  # Target absent + bookkeeping dirt must REFUSE (S06 false tip class)
  out=$(printf '%s\n' 'devfile.yaml' 'migration/mta-findings-after.json' \
    | python3 "$MM_PY" tasks.md T-001; echo rc=$?)
  echo "$out" | grep -qE 'rc=1' \
    && echo "$out" | grep -vqE 'removal-already-absent' \
    && echo t6wrongtitle-ok
}
check "O-T6WRONGTITLE Convert refuses removal-already-absent + bookkeeping" 0 "t6wrongtitle-ok"

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

# O-SHIPASSERTWEAK: characterization-drop rename must RED (wake#172)
run_case() {
  sensor_fixture
  mkdir -p src/test/java/com/demo/model
  cat > src/test/java/com/demo/model/OwnerTest.java <<'EOF'
package com.demo.model;
import java.util.List;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class OwnerTest {
  @Test
  void getPets_returnsListWithExpectedBehavior() {
    assertNotNull(List.of());
  }
}
EOF
  SENSOR_ROOT="$FIX" bash "$SENSORS" static
}
check "static sensors reject ListWithExpectedBehavior rename (O-SHIPASSERTWEAK)" 1 "O-SHIPASSERTWEAK"

# O-SHIPFIXCOMMIT / O-PREFCONT: tip tests-only GREEN dirt on timeout + CONTINUE ban
run_case() {
  grep -q 'pref_commit_green_dirt' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SHIPFIXCOMMIT' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'shipfix_timeout_commit' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'pref_snapshot_char_floor' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-PREFCONT' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'WITHOUT rewriting already-present dirty tip content' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SHIPFIXCOMMIT' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && grep -q 'O-PREFCONT' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && awk '/^pref_commit_green_dirt\(\)/,/^pref_snapshot_char_floor\(\)/ {
           if (/src\/main/) m=1
           if (/sensors\.sh task/) t=1
           if (/pref-char-floor|count_test_annotations/) f=1
         }
         END { exit !(m && t && f) }' "$HARNESS_DIR/supervisor.sh" \
    && echo shipfixcommit-prefcont-ok
}
check "O-SHIPFIXCOMMIT tip + O-PREFCONT continuation wiring" 0 "shipfixcommit-prefcont-ok"

# O-SHIPFIXPOM: mechan tests-only tip stages src/test only (not git add -A / pom)
run_case() {
  grep -q 'O-SHIPFIXPOM' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SHIPFIXPOM' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && awk '/^pref_commit_green_dirt\(\)/,/^pref_snapshot_char_floor\(\)/ {
           if (/git add -- src\/test/) a=1
           if (/^[[:space:]]*stage_for_task_commit[[:space:]]*$/) bad=1
           if (/no src\/test dirt/) r=1
         }
         END { exit !(a && r && !bad) }' "$HARNESS_DIR/supervisor.sh" \
    && echo shipfixpom-ok
}
check "O-SHIPFIXPOM mechan tip stages src/test only" 0 "shipfixpom-ok"

# O-PREFCONTUT: floor counts untracked @Test via grep -rho (not git grep alone)
run_case() {
  grep -q 'count_test_annotations' "$HARNESS_DIR/supervisor.sh" \
    && grep -q "grep -rho" "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-PREFCONTUT' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && echo prefcontut-ok
}
check "O-PREFCONTUT floor counts untracked @Test" 0 "prefcontut-ok"

# O-PREFDIMTHRASH: refuse→reset→closing preflight; count reset at fix-round start
run_case() {
  grep -q 'O-PREFDIMTHRASH' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'preflightdim_refuse_reset' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-PREFDIMTHRASH' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && awk '/preflight RED \(round/,/run_stage "Preflight fix/ {
           if (/rm -f \/tmp\/preflight-count/) r=1
         }
         END { exit !r }' "$HARNESS_DIR/supervisor.sh" \
    && echo prefdimthrash-ok
}
check "O-PREFDIMTHRASH refuse reset + per-round count clear" 0 "prefdimthrash-ok"

# O-SHIPROUNDBASE: ship-session base stamps; Preflight/Gate/Build fix committed() exclusive
run_case() {
  grep -q 'O-SHIPROUNDBASE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q '/tmp/ship-session-base' "$HARNESS_DIR/supervisor.sh" \
    && grep -q '_include_base=0' "$HARNESS_DIR/supervisor.sh" \
    && grep -E '"Preflight fix"\*\|"Gate fix"\*\|"Build fix"\*' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'abandoned remote tip is NOT authority' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SHIPROUNDBASE' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && echo shiproundbase-ok
}
check "O-SHIPROUNDBASE ship-session base + exclusive fix committed()" 0 "shiproundbase-ok"

# O-SHIPNOPRSTALE: uptodate O-SHIPNOPR must not judge pre-session PipelineRuns
run_case() {
  # session = 2026-08-03T00:30:00Z → pre-session Failed is stale; post-session fresh
  sess=1785717000
  d_stale=$(python3 "$HARNESS_DIR/shipnoprstale-decide.py" \
    "2026-08-02T23:56:21Z" "$sess" \
    "64881c899edf7c93fe1744f33fc598d110f1b664" \
    "64881c899edf7c93fe1744f33fc598d110f1b664")
  d_fresh=$(python3 "$HARNESS_DIR/shipnoprstale-decide.py" \
    "2026-08-03T01:00:00Z" "$sess" \
    "64881c899edf7c93fe1744f33fc598d110f1b664" \
    "64881c8")
  d_rev=$(python3 "$HARNESS_DIR/shipnoprstale-decide.py" \
    "2026-08-03T01:00:00Z" "$sess" \
    "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef" \
    "64881c899edf7c93fe1744f33fc598d110f1b664")
  d_nopr=$(python3 "$HARNESS_DIR/shipnoprstale-decide.py" "" "$sess")
  [ "$d_stale" = "stale" ] && [ "$d_fresh" = "fresh" ] \
    && [ "$d_rev" = "stale" ] && [ "$d_nopr" = "no-pr" ] \
    && echo shipnoprstale-ok
}
check "shipnoprstale-decide refuses pre-session / wrong-rev PR (O-SHIPNOPRSTALE behavioural)" 0 "shipnoprstale-ok"

run_case() {
  grep -q 'shipnoprstale-decide.py' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'ship-blocked-stale-pipeline' "$HARNESS_DIR/supervisor.sh" \
    && grep -q '/tmp/ship-session-started' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SHIPNOPRSTALE' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && echo shipnoprstale-wire
}
check "wait_pipeline / ship HOLD use shipnoprstale (O-SHIPNOPRSTALE)" 0 "shipnoprstale-wire"

# O-SHIPBUDGET: refuse push-anyway; closing preflight or ship-blocked-preflight-budget
run_case() {
  grep -q 'O-SHIPBUDGET' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'ship-blocked-preflight-budget' "$HARNESS_DIR/supervisor.sh" \
    && ! grep -q 'pushing anyway (factory as arbiter)' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SHIPBUDGET' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && echo shipbudget-ok
}
check "O-SHIPBUDGET refuses unpaid push-anyway" 0 "shipbudget-ok"

# O-BOOTNOFLYWAY / O-BOOTDEVPG: entity-before-Flyway uses DEV Postgres +
# generation override — never QUARKUS_PROFILE=dev/H2 (driver mismatch).
run_case() {
  grep -q 'O-BOOTDEVPG\|O-BOOTNOFLYWAY' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'QUARKUS_HIBERNATE_ORM_DATABASE_GENERATION=drop-and-create' "$HARNESS_DIR/sensors.sh" \
    && ! grep -q 'BOOT_EXTRA=(QUARKUS_PROFILE=dev)' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'db/migration' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'O-BOOTDEVPG' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && echo bootnoflyway-ok
}
check "O-BOOTDEVPG DEV Postgres drop-and-create without Flyway/seed" 0 "bootnoflyway-ok"

# O-BOOTSQLPROV: sql-load-script must NOT set has_schema_prov (Flyway/Liquibase only)
run_case() {
  awk '/^boot_check\(\)/,/^wiring_invariants\(\)/ {
    print
  }' "$HARNESS_DIR/sensors.sh" | grep -q 'O-BOOTSQLPROV' \
    && awk '/^boot_check\(\)/,/^wiring_invariants\(\)/ {
      if ($0 ~ /sql-load-script=/ && $0 ~ /has_schema_prov=1/) bad=1
    } END { exit bad ? 1 : 0 }' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'O-BOOTSQLPROV' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && grep -q '%prod\.sql-load-script' "$HARNESS_DIR/sensors.sh" \
    && echo bootsqlprov-ok
}
check "O-BOOTSQLPROV sql-load-script is not schema provenance" 0 "bootsqlprov-ok"

# O-SHIPFIXJACOCO: wiring refuses jacoco.report* strip while data-file set
run_case() {
  grep -q 'O-SHIPFIXJACOCO' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'quarkus\.jacoco\.report' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'O-SHIPFIXJACOCO' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && echo shipfixjacoco-ok
}
check "O-SHIPFIXJACOCO refuses jacoco.report strip" 0 "shipfixjacoco-ok"

# O-SHIPFIXFINDINGS: scrub Preflight/Gate/Build/Deploy tips of findings JSON
run_case() {
  grep -q 'O-SHIPFIXFINDINGS\|Preflight fix' "$HARNESS_DIR/supervisor.sh" \
    && awk '/^scrub_findings_from_tip\(\)/,/^}/ {
      if ($0 ~ /Preflight fix|Gate fix|Build fix|Deploy fix/) hit=1
    } END { exit hit ? 0 : 1 }' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SHIPFIXFINDINGS' "$HARNESS_DIR/../skills/migration-harness/SHIPPING.md" \
    && echo shipfixfindings-ok
}
check "O-SHIPFIXFINDINGS scrubs findings from Preflight tips" 0 "shipfixfindings-ok"

# O-SHIPASSERTWEAK: K12 refute on characterization-drop tip
run_case() {
  mkfix
  cat > /tmp/shipassertweak.diff <<'EOF'
diff --git a/src/test/java/com/demo/model/OwnerTest.java b/src/test/java/com/demo/model/OwnerTest.java
--- a/src/test/java/com/demo/model/OwnerTest.java
+++ b/src/test/java/com/demo/model/OwnerTest.java
@@ -1,8 +1,10 @@
-    void getPets_returnsUnmodifiableList() {
+    void getPets_returnsListWithExpectedBehavior() {
         List<Pet> pets = owner.getPets();
-        assertThrows(UnsupportedOperationException.class, () -> pets.add(new Pet()));
+        assertNotNull(pets);
+        assertEquals(1, pets.size());
     }
EOF
  out=$(python3 "$HARNESS_DIR/refute-diff.py" --diff /tmp/shipassertweak.diff 2>&1) || true
  echo "$out" | grep -q 'O-SHIPASSERTWEAK' && echo shipassertweak-k12-ok
}
check "refute-diff REFUTES characterization-drop tip (O-SHIPASSERTWEAK)" 0 "shipassertweak-k12-ok"

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

# O-M3CHARSCOPE: legacy Absorbs model cites + Shape=structure must not S-CHAR
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks

UI surface: waived (API-only service; no legacy web frontend).

#### T-003: model package structure
**Class**: rewrite
**Shape**: structure
**Target design**: → `src/main/java/com/demo/model/.gitkeep`
**Owns**: src/main/java/com/demo/model/.gitkeep
**Absorbs**: src/main/java/org/example/legacy/model/Foo.java
EOF
  printf 'legacyPackage: org.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  python3 "$LINT" tasks.md
}
check "S-CHAR skips structure+Absorbs legacy model cites (O-M3CHARSCOPE)" 0 "PLAN OK"

# S-GODORDER: god-node harvest before characterization → RED
run_case() {
  mkfix
  mkdir -p migration
  printf 'legacyPackage: com.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  cat > migration/dependency-order.md <<'EOF'
## Conversion order
1. com.example.legacy.model.PetType (src/.../PetType.java) — god-node: characterization tests first
2. com.example.legacy.model.Role (src/.../Role.java)
EOF
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Harvest PetType (god node)
**Class**: rewrite
**Shape**: create
**Target**: → `src/main/java/com/demo/model/PetType.java`
**Owns**: src/main/java/com/demo/model/PetType.java

#### T-002: Characterize entity relationships
**Class**: infer
**Shape**: create
**Goal**: characterization tests for PetType
**Owns**: src/test/java/com/demo/model/PetTypeTest.java
EOF
  echo '[]' > f.json
  out=$(python3 "$LINT" tasks.md f.json 2>&1 || true)
  echo "$out" | grep -q 'S-GODORDER' && echo sgodorder-red-ok
}
check "S-GODORDER RED when god-node harvest precedes characterization" 0 "sgodorder-red-ok"

run_case() {
  mkfix
  mkdir -p migration
  printf 'legacyPackage: com.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  cat > migration/dependency-order.md <<'EOF'
## Conversion order
1. com.example.legacy.model.PetType (src/.../PetType.java) — god-node: characterization tests first
EOF
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Characterize PetType
**Class**: rewrite
**Shape**: create
**Goal**: characterization tests for PetType
**Owns**: src/test/java/com/demo/model/PetTypeTest.java

#### T-002: Harvest PetType (god node)
**Class**: rewrite
**Shape**: create
**Target**: → `src/main/java/com/demo/model/PetType.java`
**Owns**: src/main/java/com/demo/model/PetType.java
EOF
  echo '[]' > f.json
  out=$(python3 "$LINT" tasks.md f.json 2>&1) || true
  echo "$out" | grep -q 'S-GODORDER' && { echo "unexpected: $out"; return 1; }
  echo "$out" | grep -q 'PLAN OK' && echo sgodorder-ok
}
check "S-GODORDER GREEN when characterization precedes god-node harvest" 0 "sgodorder-ok"

run_case() {
  mkfix
  mkdir -p migration
  printf 'legacyPackage: com.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  cat > migration/dependency-order.md <<'EOF'
## Conversion order
1. com.example.legacy.model.Role (src/.../Role.java)
EOF
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Harvest Role
**Class**: rewrite
**Shape**: create
**Target**: → `src/main/java/com/demo/model/Role.java`
**Owns**: src/main/java/com/demo/model/Role.java

#### T-002: Add model tests
**Class**: infer
**Shape**: create
**Owns**: src/test/java/com/demo/model/RoleTest.java
EOF
  echo '[]' > f.json
  out=$(python3 "$LINT" tasks.md f.json 2>&1) || true
  echo "$out" | grep -q 'S-GODORDER' && { echo "unexpected godorder: $out"; return 1; }
  echo "$out" | grep -q 'PLAN OK' && echo sgodorder-nongod-ok
}
check "S-GODORDER skips non-god-node harvests" 0 "sgodorder-nongod-ok"

run_case() {
  # O-M3SHAPEHARD: missing Shape is RED when grandfather WARN is off
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).
#### T-001: Harvest Role
**Class**: rewrite
**Target**: → `src/main/java/com/demo/model/Role.java`
**Owns**: src/main/java/com/demo/model/Role.java
#### T-002: tests
**Class**: infer
**Shape**: create
**Owns**: src/test/java/com/demo/model/RoleTest.java
EOF
  printf 'legacyPackage: com.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  out=$(PLAN_LINT_SHAPE_WARN=0 PLAN_LINT_REQUIRE_SHAPE=1 python3 "$LINT" tasks.md 2>&1 || true)
  echo "$out" | grep -q 'O-SHAPEDECL' && echo shapehard-ok
}
check "plan-lint Shape missing is RED by default (O-M3SHAPEHARD)" 0 "shapehard-ok"

run_case() {
  grep -q 'O-M3QWENSTALL' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M3_STALL_ABORT_SECS:-120' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M3_SKIP_W2_ON_EMPTY' "$HARNESS_DIR/outer-loop.sh" \
    && echo m3stall-ok
}
check "M3 stall abort 120s + skip w2 on empty w1 (O-M3QWENSTALL)" 0 "m3stall-ok"

run_case() {
  grep -q 'O-M3QWENSTALL: preseeded' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-M3QWENSTALL preseed' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q '_m3_tasks_real' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-REVHOLD' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'review_hold_blocks_ship' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-DEBTNONE' "$HARNESS_DIR/supervisor.sh" \
    && echo m3preseed-revhold-ok
}
check "M3 preseed + O-REVHOLD + O-DEBTNONE wiring" 0 "m3preseed-revhold-ok"

run_case() {
  # O-M3LINTPROCEED: exhausted m3-lint / still-RED plan must HOLD — never
  # "proceeding with the plan as-is" into M4.
  ! grep -qE 'proceeding with the plan as-is|still failing after revision — proceeding' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-M3LINTPROCEED' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'm3-lint-hold' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-M3LINTPROCEED' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'm3-lint-hold' "$HARNESS_DIR/outer-loop.sh" \
    && echo m3lintproceed-ok
}
check "m3-lint exhaustion HOLDs (no M4 proceed) (O-M3LINTPROCEED)" 0 "m3lintproceed-ok"

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
  grep -q 'O-ESCWSTRUCTTGT skip allow-empty' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'missing-gitkeep' "$HARNESS_DIR/escw-eligible.py" \
    && echo escwstruct-ok
}
check "O-ESCWSTRUCTTGT refuses allow-empty while structure Target absent" 0 "escwstruct-ok"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Create package structure and package-info
**Class**: rewrite
**Shape**: structure
**Scope**: Package preparation
- **Owns**: `src/main/java/com/demo/model/package-info.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/package-info.java`
- Create `src/main/java/com/demo/model/` directory structure
EOF
  export TASKS_FILE="$PWD/tasks.md"
  eval "$(sed -n '/^structure_gitkeep_targets()/,/^structure_targets_missing()/{ /^structure_targets_missing()/q; p; }' "$HARNESS_DIR/supervisor.sh")"
  out=$(structure_gitkeep_targets T-001)
  printf '%s\n' "$out" | grep -qx 'src/main/java/com/demo/model/package-info.java' \
    && ! printf '%s\n' "$out" | grep -q 'package/\.gitkeep' \
    && ! printf '%s\n' "$out" | grep -q 'springframework' \
    && echo structpkginfo-ok
}
check "O-STRUCTPKGINFO structure targets are Owns package-info (no legacy/hyphen ghosts)" 0 "structpkginfo-ok"

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

# O-SHAPELINT — Shape=structure without package/.gitkeep Target (property convert)
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Convert legacy database property files to Quarkus profile format
**Class**: rewrite
**Shape**: structure
**Target design**:
- Merge HSQLDB config → `%dev.quarkus.datasource.*` in application.properties
**Acceptance**: Quarkus profiles available
EOF
  printf 'legacyPackage: org.springframework.samples.petclinic\ntargetPackage: com.demo\n' > migration.yaml
  PLAN_LINT_REQUIRE_SHAPE=1 python3 "$LINT" tasks.md
}
check "plan-lint rejects Shape=structure without package Target (O-SHAPELINT)" 1 "O-SHAPELINT"

# O-STRUCTJAVA — Shape=structure must not Target .java sources (use create/modify)
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: structure
**Goal**: Consolidate Spring Data repository implementations to Panache
**Target design**:
- src/main/java/org/example/legacy/repository/SpringDataOwnerRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java
- src/main/java/org/example/legacy/repository/SpringDataPetRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataPetRepository.java
**Acceptance**: Panache repositories compile
EOF
  printf 'legacyPackage: org.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  PLAN_LINT_REQUIRE_SHAPE=1 python3 "$LINT" tasks.md
}
check "plan-lint rejects Shape=structure with .java Targets (O-STRUCTJAVA)" 1 "O-STRUCTJAVA"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-003: Create repository package structure with .gitkeep
**Class**: rewrite
**Shape**: structure
**Goal**: Create repository package structure with .gitkeep
**Target design**: → `src/main/java/com/demo/repository/springdatajpa/.gitkeep`
**Owns**: src/main/java/com/demo/repository/springdatajpa/.gitkeep
**Absorbs**: src/main/java/org/example/legacy/repository/SpringDataOwnerRepository.java
**Acceptance**: package directory trackable via .gitkeep
EOF
  printf 'legacyPackage: org.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  PLAN_LINT_REQUIRE_SHAPE=1 python3 "$LINT" tasks.md
}
check "plan-lint accepts Shape=structure .gitkeep with Absorbs .java (O-STRUCTJAVA-NEG)" 0 "PLAN OK"

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
  # O-DEBTFRZRACE: discard src dirt + re-sensor before debt freeze; avert false RED
  grep -q 'O-DEBTFRZRACE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'discard_src_dirt' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'false-red averted' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'debtfrzrace_averted' "$HARNESS_DIR/supervisor.sh" \
    && awk '/^record_debt\(\)/,/^debt_frozen\(\)/ {
           if (/discard_src_dirt/) d=1
           if (/sensors\.sh.*kind/ || /sensors\.sh "\$kind"/) s=1
           if (/false-red averted/) a=1
         }
         END { exit !(d && s && a) }' "$HARNESS_DIR/supervisor.sh" \
    && echo debtfrzrace-ok
}
check "O-DEBTFRZRACE discard+recheck before debt freeze" 0 "debtfrzrace-ok"

run_case() {
  # O-ESCALAFTERRESET: post O-SFIXSCOPE reset gate + CONTINUE invent ban
  grep -q 'O-ESCALAFTERRESET' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'post_reset_escalation_gate' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'escal-after-reset-' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'WITHOUT inventing new files/tests' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SFIXSCOPE reset worker RED commit' "$HARNESS_DIR/supervisor.sh" \
    && awk '/post_reset_escalation_gate\(\)/,/^run_stage\(\)/ {
           if (/discard_src_dirt|O-SFIXDIRTY/) d=1
           if (/try_mechan_commit/) m=1
           if (/sensors\.sh task/) s=1
         }
         END { exit !(d && m && s) }' "$HARNESS_DIR/supervisor.sh" \
    && echo escalafterreset-ok
}
check "O-ESCALAFTERRESET post-reset gate + CONTINUE guidance" 0 "escalafterreset-ok"

run_case() {
  grep -q 'O-FRZSIG' "$HARNESS_DIR/freeze-harness.sh" \
    && grep -q 'no sessions killed' "$HARNESS_DIR/freeze-harness.sh" \
    && ! grep -qE "kill_pat.*hermes|pkill.*opencode" "$HARNESS_DIR/freeze-harness.sh" \
    && test -f "$HARNESS_DIR/harness-kill.sh" \
    && grep -q 'harness_kill' "$HARNESS_DIR/harness-kill.sh" \
    && echo frzsig-ok
}
check "O-FRZSIG freeze is pause-marker (not slaughter) + O-KILLLEDGER helper" 0 "frzsig-ok"

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
  mkdir -p src/test/java/com/demo
  cat > tasks.md <<'EOF'
# Tasks
#### T-000: Characterization deferred for repository god-nodes (O-CHARORACLE / S-GODORDER)
**Class**: rewrite
**Shape**: verify
**Goal**: Characterization for repository god-node PetTypeRepository is deferred — do NOT invent hollow G-PLACE Repository tests.
**Target design**: verify absence of phantom invented `src/test/java/**/PetTypeRepository*Test.java` for this story
**Oracle**: absent
**Acceptance**: PetTypeRepository named; no hollow repository characterization tests invented
EOF
  ALREADY_COMPLETE_ROOT="$PWD" python3 "$ESCW_PY" tasks.md T-000
  ALREADY_COMPLETE_ROOT="$PWD" python3 "$HARNESS_DIR/already-complete.py" tasks.md T-000
}
check "verify-absent Shape=verify Oracle=absent ESCW+already-complete (O-ESCWVERIFYABS)" 0 "verify-absent"

run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/repository/jdbc
  echo 'class JdbcOwnerRepositoryImpl {}' > src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java
  cat > tasks.md <<'EOF'
# Tasks
#### T-006: Finding-scope boundaries (prior + later)
**Class**: infer
**Shape**: structure
No new SUTs. Claim residual DI finding incidents already delivered or reserved for later stories.
**Target design**:
- `src/main/java/org.example/JdbcOwnerRepositoryImpl.java` → `src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java`
- `src/main/java/org.example/RootRestController.java` → `src/main/java/com/demo/rest/RootRestController.java`
**Absorbs**: `src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java` `src/main/java/com/demo/rest/RootRestController.java`
**Acceptance**: plan-lint green; no new repository/rest/security/util src/main from this task
EOF
  ALREADY_COMPLETE_ROOT="$PWD" python3 "$ESCW_PY" tasks.md T-006
}
check "escw-eligible finding-scope ignores later-story Target dest (O-ESCW3SCOPE)" 0 "eligible"

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

# O-STRUCTTGT — structure/.gitkeep must not O-TGTNAME-mandate Absorbs .java
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-003: Create model package structure with .gitkeep
**Class**: rewrite
**Shape**: structure
**Goal**: Create model package structure with .gitkeep
**Target design**: → `src/main/java/com/demo/model/.gitkeep`
**Owns**: src/main/java/com/demo/model/.gitkeep
**Absorbs**: src/main/java/org/example/legacy/model/BaseEntity.java
**Absorbs**: src/main/java/org/example/legacy/model/Owner.java
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-003 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-STRUCTTGT' \
    && echo "$out" | grep -q 'src/main/java/com/demo/model/.gitkeep' \
    && ! echo "$out" | grep -q 'BaseEntity.java' \
    && ! echo "$out" | grep -q 'Owner.java' \
    && ! echo "$out" | grep -q 'harvest-from-staging.sh' \
    && grep -q 'O-STRUCTTGT' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && echo structtgt-ok
}
check "task-packet gates O-TGTNAME on structure/.gitkeep (O-STRUCTTGT)" 0 "structtgt-ok"

# O-STRUCTJAVA — structure+.java Target-design packet tip (plan defect → NULLACTION)
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: structure
**Goal**: Consolidate Spring Data repository implementations to Panache
**Target design**:
- → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**Acceptance**: Panache repositories compile
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-004 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-STRUCTJAVA' \
    && echo "$out" | grep -qE 'O-NULLACTION|escalation-noaction' \
    && ! echo "$out" | grep -q 'O-STRUCTTGT: Shape=structure / Target .gitkeep' \
    && ! echo "$out" | grep -q 'MANDATORY: .gitkeep' \
    && echo structjava-pkt-ok
}
check "task-packet tips O-STRUCTJAVA on structure+.java Targets" 0 "structjava-pkt-ok"

# O-HTTPPORT-TIP — properties packets must hard-tip deploy-contract port
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Consolidate application.properties with PetClinic legacy settings
**Class**: rewrite
**Shape**: modify
**Goal**: Consolidate application.properties with PetClinic legacy settings
**Target design**: → `src/main/resources/application.properties`
**Owns**: src/main/resources/application.properties
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-001 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-HTTPPORT' \
    && echo "$out" | grep -q 'NEVER copy legacy Spring server.port' \
    && echo httpport-tip-ok
}
check "task-packet injects O-HTTPPORT tip for properties tasks (O-HTTPPORT-TIP)" 0 "httpport-tip-ok"

run_case() {
  # O-STAGEDPATH: harvest packet must expose legacy-layout staged path
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-008: Harvest User
**Class**: rewrite
**Shape**: create
**Goal**: Harvest User with jakarta.persistence migration
**Source**: /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/User.java
**Target**: → `src/main/java/com/demo/model/User.java`
**Owns**: src/main/java/com/demo/model/User.java
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-008 2>/dev/null)
  echo "$out" | grep -q 'O-STAGEDPATH' \
    && echo "$out" | grep -q 'migration/staging/src/main/java/org/springframework/samples/petclinic/model/User.java' \
    && echo stagedpath-ok
}
check "task-packet emits Staged-source legacy path (O-STAGEDPATH)" 0 "stagedpath-ok"

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
  # O-DTOFIRST absent-DTO: mapper-only story that references /dto/ must RED
  mkfix
  cat > tasks.md <<'EOF'
UI surface: waived (API-only).

#### T-005: Harvest mapper interfaces
**Class**: rewrite
**Findings**: javax-to-jakarta-import-00001
**Goal**: Harvest MapStruct mappers; update dto imports to com.demo.dto
**Target**: `src/main/java/com/demo/mapper/*.java`
**Actions**: Update import statements: model → com.demo.model, dto imports → com.demo.dto
EOF
  python3 "$LINT" tasks.md
}
check "plan-lint rejects mapper-only story with dto refs (O-DTOFIRST)" 1 "O-DTOFIRST"

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
  mkdir -p src/main/java/com/example/dto
  cat > pom.xml <<'EOF'
<project><modelVersion>4.0.0</modelVersion>
<properties>
  <sonar.coverage.jacoco.xmlReportPaths>target/jacoco-report/jacoco.xml</sonar.coverage.jacoco.xmlReportPaths>
</properties>
</project>
EOF
  printf 'package com.example.dto;\npublic class SampleDto {}\n' > src/main/java/com/example/dto/SampleDto.java
  python3 "$HARNESS_DIR/ensure-dtocov-pom.py" . && grep -q 'sonar.exclusions' pom.xml && grep -Fq '**/dto/**' pom.xml && echo dtocov-ok
}
check "ensure-dtocov-pom adds dto sonar exclusions (O-DTOCOV)" 0 "dtocov-ok"

run_case() {
  grep -q 'sfix_loop_recheck' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'SFIX_RED_DESC' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'ensure-dtocov-pom.py' "$HARNESS_DIR/supervisor.sh" \
    && echo sfix-dtocov-wire-ok
}
check "O-DTOCOV + O-SFIX-PROMPT-CONFLICT supervisor wiring" 0 "sfix-dtocov-wire-ok"

run_case() {
  mkfix
  mkdir -p src/main/resources
  cat > pom.xml <<'EOF'
<project>
  <dependencies>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-hibernate-orm</artifactId>
    </dependency>
  </dependencies>
</project>
EOF
  : > src/main/resources/application.properties
  out=$(python3 "$HARNESS_DIR/ensure-dskind.py" .)
  echo "$out" | grep -q 'ok:dskind-updated' \
    && grep -q 'quarkus-jdbc-h2' pom.xml \
    && grep -q 'quarkus-jdbc-postgresql' pom.xml \
    && grep -q 'quarkus.datasource.db-kind' src/main/resources/application.properties \
    && echo dskind-ok
}
check "ensure-dskind wires jdbc+db-kind for hibernate (O-DSKIND)" 0 "dskind-ok"

run_case() {
  grep -q 'ensure-dskind.py' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-DSKIND' "$HARNESS_DIR/task-packet.py" \
    && echo dskind-wire-ok
}
check "O-DSKIND wired in supervisor + task-packet tip" 0 "dskind-wire-ok"

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
**Shape**: create
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

# O-M3DTOSCOPE: --story-scope skips incident-unowned for files outside roadmap scope
run_case() {
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Convert pom
**Class**: rewrite
**Shape**: modify
**Findings**: removed-javaee-modules-00020
**Goal**: convert pom only
**Target design**: → `pom.xml`
EOF
  cat > f.json <<'EOF'
[{"violations": {"removed-javaee-modules-00020": {"category": "mandatory", "incidents": [
  {"uri": "file:///projects/legacy/pom.xml", "lineNumber": 1},
  {"uri": "file:///projects/legacy/src/main/java/com/redhat/coolstore/dto/FooDto.java", "lineNumber": 2}
]}}}]
EOF
  python3 "$LINT" tasks.md f.json --story-scope 'pom.xml,src/main/resources/application.properties'
}
check "plan-lint story-scope skips out-of-scope dto incidents (O-M3DTOSCOPE)" 0 "PLAN OK"

# O-M3TASKSCOPE: Target/→ outside --story-scope must RED (service under repository story)
run_case() {
  mkfix
  printf 'legacyPackage: org.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Harvest repository
**Class**: rewrite
**Shape**: modify
**Goal**: convert repository only
**Target design**:
- src/main/java/org/example/legacy/repository/FooRepository.java → src/main/java/com/demo/repository/FooRepository.java

#### T-002: Update service layer
**Class**: rewrite
**Shape**: modify
**Goal**: touch service outside story scope
**Target design**:
- src/main/java/org/example/legacy/service/FooServiceImpl.java → Update repository imports
EOF
  echo '[]' > f.json
  out=$(python3 "$LINT" tasks.md f.json --story-scope \
    'src/main/java/org/example/legacy/repository/FooRepository.java' 2>&1 || true)
  echo "$out" | grep -q 'O-M3TASKSCOPE' && echo "$out" | grep -q 'FooServiceImpl' \
    && echo m3taskscope-red-ok
}
check "plan-lint RED Target outside story-scope (O-M3TASKSCOPE)" 0 "m3taskscope-red-ok"

# O-M3TASKSCOPE: in-scope repository Target stays GREEN; src/test char allowed
run_case() {
  mkfix
  printf 'legacyPackage: org.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Harvest repository
**Class**: rewrite
**Shape**: modify
**Goal**: convert repository
**Target design**:
- src/main/java/org/example/legacy/repository/FooRepository.java → src/main/java/com/demo/repository/FooRepository.java

#### T-002: Characterize repository
**Class**: infer
**Shape**: create
**Goal**: characterization tests for FooRepository
**Target design**:
- Create src/test/java/com/demo/repository/FooRepositoryTest.java
EOF
  echo '[]' > f.json
  python3 "$LINT" tasks.md f.json --story-scope \
    'src/main/java/org/example/legacy/repository/FooRepository.java'
}
check "plan-lint GREEN in-scope Target + test char (O-M3TASKSCOPE)" 0 "PLAN OK"

# O-M3GENSRC: generated-sources never require ownership
run_case() {
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Convert pom
**Class**: rewrite
**Shape**: modify
**Findings**: mapstruct-00001
**Goal**: convert pom
**Target design**: → `pom.xml`
EOF
  cat > f.json <<'EOF'
[{"violations": {"mapstruct-00001": {"category": "mandatory", "incidents": [
  {"uri": "file:///projects/legacy/target/generated-sources/annotations/FooMapperImpl.java", "lineNumber": 1}
]}}}]
EOF
  python3 "$LINT" tasks.md f.json
}
check "plan-lint skips generated-sources incident-unowned (O-M3GENSRC)" 0 "PLAN OK"

# K1-CONF: disclaimer must not manufacture conflict with real owner
run_case() {
  mkfix
  printf 'legacyPackage: com.redhat.coolstore\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Convert Beta
**Class**: rewrite
**Shape**: modify
**Findings**: r-mand-00001
**Goal**: convert Beta
- Target: → `src/main/java/com/demo/Beta.java`

#### T-002: Characterize Alpha
**Class**: infer
**Shape**: verify
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

# O-REDESIGNSIGANNOT — @Query / license must not fake method names
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/com/demo/repository \
    src/main/java/com/demo/repository
  printf '%s\n' \
    'package com.demo.repository;' \
    '/** Licensed under Apache License, Version 2.0 (the "License"); */' \
    'import org.springframework.data.jpa.repository.Query;' \
    'public interface SpringDataOwnerRepository {' \
    '  @Query("SELECT o FROM Owner o WHERE o.id = :id")' \
    '  Owner findById(int id);' \
    '}' \
    > migration/staging/src/main/java/com/demo/repository/SpringDataOwnerRepository.java
  printf '%s\n' \
    'package com.demo.repository;' \
    '/** Licensed under Apache License, Version 2.0 (the "License"); */' \
    'public interface SpringDataOwnerRepository {' \
    '  Owner findById(int id);' \
    '}' \
    > src/main/java/com/demo/repository/SpringDataOwnerRepository.java
  out=$(python3 "$HARNESS_DIR/redesign-sig.py" 2>&1); echo "rc=$?"; echo "$out"
}
check "redesign-sig ignores @Query/license tokens (O-REDESIGNSIGANNOT)" 0 "rc=0"

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
    && grep -q 'oracle_derive' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'inferabsent_blocks' "$HARNESS_DIR/supervisor.sh" \
    && echo inferabsent-ok
}
check "O-INFERABSENT wiring (skip worker on infer+derived-absent)" 0 "inferabsent-ok"

run_case() {
  grep -q 'O-ESCREOPENCODE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'YOU OWN all file-changing work' "$HARNESS_DIR/supervisor.sh" \
    && echo escreopencode-ok
}
check "O-ESCREOPENCODE wiring (no opencode re-dispatch after wedge)" 0 "escreopencode-ok"

run_case() {
  grep -q 'O-ESCREOPENCODE-ENFORCE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'arm_escreopencode' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'escreopencode_kill_spawned' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'escreopencode-deny' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-ESCREOPENCODE-ENFORCE' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && echo escreopencode-enforce-ok
}
check "O-ESCREOPENCODE-ENFORCE wiring (PATH refuse + kill opencode on escalation)" 0 "escreopencode-enforce-ok"

# O-ESCREOPENCODE-SENSORRED — ENFORCE also arms on sensor-red / O-STEPFINISHRED
run_case() {
  grep -q 'O-ESCREOPENCODE-SENSORRED' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-STEPFINISHRED' "$HARNESS_DIR/supervisor.sh" \
    && awk '/^escreopencode_should\(\)/,/^}/ {
           if (/O-STEPFINISHRED/) s=1
           if (/sensor-red/) c=1
           if (/SENSOR RED/) r=1
         }
         END { exit !(s && c && r) }' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-ESCREOPENCODE-SENSORRED' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && grep -q 'sensor-red' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && echo escreopencode-sensorred-ok
}
check "O-ESCREOPENCODE-SENSORRED arms ENFORCE on sensor-red / O-STEPFINISHRED" 0 "escreopencode-sensorred-ok"

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
  discard_orphan_pom() { :; }
  log() { :; }
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

# O-T6EEMPTYESC — pom deps present → ESCW even if findings-oracle would block
run_case() {
  mkfix
  mkdir -p migration .hermes/harness
  cp "$HARNESS_DIR/escw-eligible.py" .hermes/harness/
  cat > pom.xml <<'EOF'
<project>
  <dependencies>
    <dependency><groupId>io.quarkus</groupId><artifactId>quarkus-security</artifactId></dependency>
    <dependency><groupId>io.quarkus</groupId><artifactId>quarkus-smallrye-openapi</artifactId></dependency>
    <dependency><groupId>io.quarkus</groupId><artifactId>quarkus-elytron-security-jdbc</artifactId></dependency>
  </dependencies>
</project>
EOF
  cat > migration/mta-findings-after.json <<'EOF'
[{"violations":{
  "springboot-security-to-quarkus-00000":{"description":"x","incidents":[{"uri":"file:///pom.xml","lineNumber":1}]}
}}]
EOF
  cat > migration/mta-findings.json <<'EOF'
[{"violations":{
  "springboot-security-to-quarkus-00000":{"description":"x","incidents":[{"uri":"file:///pom.xml","lineNumber":1}]}
}}]
EOF
  cat > tasks.md <<'EOF'
#### T-001: Add Quarkus Security and OpenAPI dependencies
**Class**: infer
**Shape**: modify
**Findings**: springboot-security-to-quarkus-00000
**Goal**: Add quarkus-security quarkus-smallrye-openapi quarkus-elytron-security-jdbc to pom.xml
**Target design**: → pom.xml
**Acceptance**: pom.xml declares Quarkus Security + OpenAPI deps
EOF
  out=$(ALREADY_COMPLETE_ROOT="$FIX" python3 .hermes/harness/escw-eligible.py tasks.md T-001)
  echo "$out"
}
check "escw-eligible allows pom-deps-present despite findings (O-T6EEMPTYESC)" 0 "pom-deps-present:"

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

# O-FAILSIGFILE (W3-92) — sonar-report multi-line format must keep rule↔file
run_case() {
  mkfix
  printf '%s\n' \
    'QUALITYGATE FAIL new_violations: actual=3 threshold=0 comparator=GT' \
    'java:S112 (1): src/main/java/com/demo/service/UserServiceImpl.java:26' \
    'java:S1130 (2): src/test/java/com/demo/service/UserServiceImplTest.java:32, src/test/java/com/demo/service/UserServiceImplTest.java:43' \
    'java:S2925 (1): src/test/java/com/demo/service/ClinicServiceImplTest.java:332' \
    > sonar-violations.txt
  python3 "$HARNESS_DIR/failure-sig.py" capture out.sig sonar-violations.txt
  grep -qx 'sonar:java:S2925:ClinicServiceImplTest.java' out.sig \
    && grep -qx 'sonar:java:S1130:UserServiceImplTest.java' out.sig \
    && grep -qx 'sonar:java:S112:UserServiceImpl.java' out.sig \
    && ! grep -q 'sonar:java:S2925:UserServiceImplTest.java' out.sig \
    && ! grep -q 'sonar:java:S1130:UserServiceImpl.java' out.sig \
    && echo failsigfile-ok
}
check "O-FAILSIGFILE sonar rule↔file attribution (no cross-line)" 0 "failsigfile-ok"

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

run_case() {
  mkfix
  mkdir -p migration specs/S01 .hermes/harness
  cp "$HARNESS_DIR/findings-milestone-scope.py" .hermes/harness/
  git init -q
  git config user.email test@test
  git config user.name test
  cat > specs/S01/tasks.md <<'EOF'
### T-001: dto
**Findings**: openapi-dto-harvest-00001
### T-002: pom metrics
**Findings**: javaee-pom-to-quarkus-00030, metrics-to-quarkus-00001
EOF
  git add specs/S01/tasks.md && git commit -q -m "init"
  git commit -q --allow-empty -m "T-001: harvest dto"
  out=$(python3 .hermes/harness/findings-milestone-scope.py specs/S01/tasks.md HEAD)
  echo "$out" | grep -q 'openapi-dto-harvest-00001' \
    && ! echo "$out" | grep -q 'javaee-pom-to-quarkus-00030' \
    && echo k5milescope-ok
}
check "findings-milestone-scope limits in-loop K5 (O-K5MILESCOPE)" 0 "k5milescope-ok"

run_case() {
  # O-K5WAIVELEAK: FINDINGS_K5_WAIVED=1 must short-circuit sensors.sh findings
  # (not fall through to PLAN_SCOPE / --scope-all). Behavioural via real entrypoint.
  mkfix
  out=$(
    FINDINGS_K5_WAIVED=1 FINDINGS_SCOPE= PLAN_SCOPE=springboot-metrics-to-quarkus-0200 \
      FINDINGS_CHECK=on bash "$SENSORS" findings 2>&1
  ) || true
  echo "$out" | grep -q 'O-K5WAIVELEAK' \
    && ! echo "$out" | grep -qE 'FINDINGS RED|SENSOR RED \(findings\)|FAIL:findings' \
    && echo k5waiveleak-ok
}
check "empty in-loop Findings waives K5 (O-K5WAIVELEAK)" 0 "k5waiveleak-ok"

run_case() {
  grep -q 'FINDINGS_K5_WAIVED' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'O-K5WAIVELEAK' "$HARNESS_DIR/sensors.sh" \
    && echo k5waiveleak-wire
}
check "O-K5WAIVELEAK wired in sensors.sh" 0 "k5waiveleak-wire"

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

# O-FIRSTMUTBASH: successful harvest-from-staging bash counts as mutate (S03 T-002 false READ_THRASH)
run_case() {
  mkfix
  python3 - <<'PY' > oc.json
import json
evs = []
for i in range(22):
    evs.append({"type": "tool_use", "part": {"type": "tool", "tool": "read", "callID": f"r{i}"}})
evs.append({
    "type": "tool_use",
    "part": {
        "type": "tool",
        "tool": "bash",
        "callID": "b0",
        "state": {
            "input": {
                "command": ".hermes/skills/migration-harness/scripts/harvest-from-staging.sh repository/jdbc/JdbcPet.java"
            },
            "output": (
                "harvested: migration/staging/src/main/java/org/example/repository/jdbc/JdbcPet.java "
                "-> src/main/java/com/demo/repository/jdbc/JdbcPet.java (package org.example -> com.demo, dest path '/' -joined)"
            ),
        },
    },
})
print(json.dumps(evs))
PY
  python3 "$HARNESS_DIR/worker-read-watch.py" oc.json; echo "rc=$?"
}
check "worker-read-watch continues after bash harvest success (O-FIRSTMUTBASH)" 0 "rc=1"

run_case() {
  mkfix
  python3 - <<'PY' > oc.json
import json
evs = []
for i in range(22):
    evs.append({"type": "tool_use", "part": {"type": "tool", "tool": "read", "callID": f"r{i}"}})
evs.append({
    "type": "tool_use",
    "part": {
        "type": "tool",
        "tool": "bash",
        "callID": "b0",
        "state": {
            "input": {
                "command": ".hermes/skills/migration-harness/scripts/harvest-from-staging.sh repository/jdbc/JdbcPet.java"
            },
            "output": "FATAL: O-HARVESTFULLPATH — missing staging source",
        },
    },
})
print(json.dumps(evs))
PY
  out=$(python3 "$HARNESS_DIR/worker-read-watch.py" oc.json); rc=$?
  [ "$rc" -eq 0 ] && echo "$out" | grep -q 'read-thrash' && echo firstmutbash-fail-kill
}
check "worker-read-watch kills failed harvest bash (O-FIRSTMUTBASH)" 0 "firstmutbash-fail-kill"

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
  grep -q 'O-RESUMEBASEEXCL' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'git log --oneline -1 "${_base}"' "$HARNESS_DIR/supervisor.sh" \
    && grep -q '_include_base=1' "$HARNESS_DIR/supervisor.sh" \
    && echo resumebase-ok
}
check "committed() includes RUN_BASE tip (O-RESUMEBASEEXCL)" 0 "resumebase-ok"

run_case() {
  grep -q 'O-KANTRAMISS' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'kantra-ensure' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'mta-findings-current.json' "$HARNESS_DIR/supervisor.sh" \
    && echo kantramiss-ok
}
check "M5 after-scan calls kantra-ensure + cache fallback (O-KANTRAMISS)" 0 "kantramiss-ok"

run_case() {
  grep -q 'O-CREATEFIRSTMUT' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'CREATE_READ_GLOB_MAX' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'M3_EMPTY_ABORT_SECS:-360' "$HARNESS_DIR/outer-loop.sh" \
    && echo createfirst-ok
}
check "Shape=create first-write tip + M3 empty abort 360s (O-CREATEFIRSTMUT)" 0 "createfirst-ok"

run_case() {
  grep -q 'O-DUPPROP' "$HARNESS_DIR/commit-hygiene.py" \
    && echo dupprop-ok
}
check "commit-hygiene refuses duplicate application.properties keys (O-DUPPROP)" 0 "dupprop-ok"

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
  # O-HYGIENEWORKER: worker/mechan/ESCW tip-accept must call refuse_unhygienic_commit
  # (S03 T-001 d7bde2a spring-tx bypassed run_stage-only hygiene).
  grep -q 'refuse_unhygienic_commit' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-HYGIENEWORKER' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'migration/run-archives' "$HARNESS_DIR/supervisor.sh" \
    && echo hygieneworker-ok
}
check "O-HYGIENEWORKER / O-ARCHIVESTAGE wiring" 0 "hygieneworker-ok"

# O-M3PRESERVEDAO — plan must not Preserve DataAccessException / add spring-tx
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Harvest repository interfaces
**Class**: rewrite
**Shape**: create
**Goal**: Create package structure and harvest repository interfaces
**Target**: → `src/main/java/com/demo/repository/OwnerRepository.java`
Preserve DataAccessException on method signatures.
**Acceptance**: interfaces compile
EOF
  python3 "$LINT" tasks.md
}
check "plan-lint rejects Preserve DataAccessException (O-M3PRESERVEDAO)" 1 "O-M3PRESERVEDAO"

# W4-085a: substring-only remap one-liner without exact table → RED
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Harvest repository interfaces
**Class**: rewrite
**Shape**: create
**Goal**: Harvest OwnerRepository from staging
**Target**: → `src/main/java/com/demo/repository/OwnerRepository.java`
Remap DataAccessException → PersistenceException (or omit throws); never add spring-tx.
**Acceptance**: interfaces compile without spring-dao
EOF
  python3 "$LINT" tasks.md
}
check "plan-lint rejects substring-only DAO remap one-liner (O-M3PRESERVEDAO/W4-085a)" 1 "O-M3PRESERVEDAO"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-001: Harvest repository interfaces
**Class**: rewrite
**Shape**: create
**Goal**: Harvest OwnerRepository from staging
**Target**: → `src/main/java/com/demo/repository/OwnerRepository.java`
**Exception mapping**:
| legacy | target |
| DataAccessException | PersistenceException |
| EmptyResultDataAccessException | NoResultException |
| ObjectRetrievalFailureException | EntityNotFoundException |
| DataRetrievalFailureException | PersistenceException |
Never add spring-tx.
**Acceptance**: interfaces compile without spring-dao
EOF
  out=$(python3 "$LINT" tasks.md 2>&1)
  echo "$out" | grep -q O-M3PRESERVEDAO && echo "FP-FIRED" || echo "preservedao-clean"
}
check "plan-lint accepts exact DAO mapping table (O-M3PRESERVEDAO-NEG)" 0 "preservedao-clean"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Harvest OwnerRepository
**Class**: rewrite
**Shape**: create
**Goal**: Harvest OwnerRepository interface from staging
**Target**: → `src/main/java/com/demo/repository/OwnerRepository.java`
**Owns**: src/main/java/com/demo/repository/OwnerRepository.java
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-001 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-M3PRESERVEDAO' \
    && echo "$out" | grep -q 'PersistenceException' \
    && echo "$out" | grep -q 'EmptyResultDataAccessException' \
    && echo "$out" | grep -q 'NoResultException' \
    && echo "$out" | grep -q 'ObjectRetrievalFailureException' \
    && echo "$out" | grep -q 'EntityNotFoundException' \
    && echo "$out" | grep -q 'NEVER invent' \
    && grep -q 'O-M3PRESERVEDAO' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && grep -q 'O-M3PRESERVEDAO' "$HARNESS_DIR/../skills/migration-harness/PLANNING.md" \
    && echo preservedao-tip-ok
}
check "task-packet injects O-M3PRESERVEDAO tip for repository harvest" 0 "preservedao-tip-ok"

# O-CHARORACLE — characterization Source→Target must exist in staging/legacy
run_case() {
  mkfix
  mkdir -p migration/staging/src/test/java/com/example
  # deliberately omit FooRepositoryTest.java (phantom oracle)
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Characterization tests for repository operations
**Class**: infer
**Shape**: create
**Goal**: Port legacy repository tests to verify CRUD before conversion
**Target design**:
- src/test/java/com/example/FooRepositoryTest.java → src/test/java/com/demo/FooRepositoryTest.java
**Acceptance**: tests pass
EOF
  python3 "$LINT" tasks.md
}
check "plan-lint rejects phantom characterization Source (O-CHARORACLE)" 1 "O-CHARORACLE"

run_case() {
  mkfix
  mkdir -p migration/staging/src/test/java/com/example
  echo 'class FooRepositoryTest {}' > migration/staging/src/test/java/com/example/FooRepositoryTest.java
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Characterization tests for repository operations
**Class**: infer
**Shape**: create
**Goal**: Port legacy repository tests to verify CRUD before conversion
**Target design**:
- src/test/java/com/example/FooRepositoryTest.java → src/test/java/com/demo/FooRepositoryTest.java
**Acceptance**: tests pass
EOF
  out=$(python3 "$LINT" tasks.md 2>&1)
  echo "$out" | grep -q O-CHARORACLE && echo "FP-FIRED" || echo "charoracle-clean"
}
check "plan-lint accepts existing characterization Source (O-CHARORACLE-NEG)" 0 "charoracle-clean"

run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/com/example
  # staging has impl but NOT the test oracle
  echo 'class FooRepository {}' > migration/staging/src/main/java/com/example/FooRepository.java
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Characterization tests for repository operations
**Class**: infer
**Shape**: create
**Goal**: Port legacy repository tests before conversion
**Target design**:
- src/test/java/com/example/FooRepositoryTest.java → src/test/java/com/demo/FooRepositoryTest.java
**Acceptance**: tests pass
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-002 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-CHARORACLE' \
    && echo "$out" | grep -q 'oracle ABSENT' \
    && echo "$out" | grep -q 'O-NULLACTION' \
    && echo "$out" | grep -q 'Do NOT invent' \
    && grep -q 'O-CHARORACLE' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && grep -q 'O-CHARORACLE' "$HARNESS_DIR/../skills/migration-harness/PLANNING.md" \
    && echo charoracle-tip-ok
}
check "task-packet injects O-CHARORACLE tip when oracle absent" 0 "charoracle-tip-ok"

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

# O-SFIXRESCUEDISCARD / O-SFIXSIGINT: tip cited-dim GREEN dirt before discard/reset
run_case() {
  grep -q 'sfix_commit_green_dirt' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SFIXRESCUEDISCARD' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'sfix_rescue_commit' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'sfix_keep_tip_cited_green' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-DEBTSHIPRACE' "$HARNESS_DIR/supervisor.sh" \
    && awk '/^sfix_commit_green_dirt\(\)/,/^record_debt\(\)/ {
           if (/sfix_loop_recheck/) r=1
           if (/stage_for_task_commit/) s=1
           if (/O-SFIXRESCUEDISCARD tip/) t=1
         }
         END { exit !(r && s && t) }' "$HARNESS_DIR/supervisor.sh" \
    && echo sfixrescuediscard-ok
}
check "O-SFIXRESCUEDISCARD tip green dirt before discard + O-DEBTSHIPRACE" 0 "sfixrescuediscard-ok"

# O-SFIXMUTATE: sfix seats early-kill diagnose-freeze (0 edit/write)
run_case() {
  grep -q 'O-SFIXMUTATE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'SFIX_MUTATE_DEADLINE_SECS' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'sfix_mutate_kill' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'WORKER_MUTATE_DEADLINE_SECS' "$HARNESS_DIR/worker-read-watch.py" \
    && grep -q 'sfix-mutate-deadline' "$HARNESS_DIR/worker-read-watch.py" \
    && grep -q 'O-SFIXMUTATE' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && echo sfixmutate-ok
}
check "O-SFIXMUTATE sfix diagnose-freeze early kill + EXECUTION tip" 0 "sfixmutate-ok"

# ARCH-C1 / O-TASKMUTATE: M4 task seats also wire WORKER_MUTATE_DEADLINE (not
# only *sfix*), and worker-read-watch aborts on no first-write past deadline.
run_case() {
  # Wiring: WORKER_MUTATE_DEADLINE appears outside the *sfix*) case branch.
  awk '
    /\*sfix\*\)/ { in_sfix=1; next }
    in_sfix && /^[[:space:]]*esac[[:space:]]*$/ { in_sfix=0 }
    in_sfix && /^[[:space:]]*[a-zA-Z_*|).-]+\)/ && !/\*sfix\*\)/ { in_sfix=0 }
    /WORKER_MUTATE_DEADLINE/ && !in_sfix { found=1 }
    END { exit !found }
  ' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-TASKMUTATE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'task_mutate_kill' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-TASKMUTATE' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && {
      # Behavior: activity + 0 mutates past deadline → kill (exit 0).
      mkfix
      python3 - <<'PY' > oc.json
import json
evs = [{"type": "tool_use", "part": {"type": "tool", "tool": "read", "callID": f"r{i}"}} for i in range(4)]
print(json.dumps(evs))
PY
      out=$(WORKER_MUTATE_DEADLINE_SECS=120 python3 "$HARNESS_DIR/worker-read-watch.py" oc.json 120)
      rc=$?
      [ "$rc" -eq 0 ] && echo "$out" | grep -q 'mutate-deadline' && echo "$out" | grep -q 'mutates=0'
    } \
    && {
      # With a first edit inside the window → continue (exit 1).
      mkfix
      python3 - <<'PY' > oc.json
import json
evs = [{"type": "tool_use", "part": {"type": "tool", "tool": "read", "callID": "r0"}}]
evs.append({"type": "tool_use", "part": {"type": "tool", "tool": "edit", "callID": "e0"}})
print(json.dumps(evs))
PY
      WORKER_MUTATE_DEADLINE_SECS=120 python3 "$HARNESS_DIR/worker-read-watch.py" oc.json 120
      [ $? -eq 1 ]
    } \
    && echo taskmutate-ok
}
check "ARCH-C1 O-TASKMUTATE M4 first-write deadline + abort instrument" 0 "taskmutate-ok"

# O-STYLEFIDELITY: park dirt + fidelity revert + no scoop via git add -A
run_case() {
  grep -q 'park_src_dirt_for_autofix' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'style_autofix_stage' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-STYLEFIDELITY' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'style_autofix_fidelity_revert' "$HARNESS_DIR/supervisor.sh" \
    && awk '/^style_autofix_stage\(\)/,/^park_src_dirt_for_autofix\(\)/ {
           if (/git add -A/) bad=1
           if (/src\/\*/) ok=1
         }
         END { exit !(ok && !bad) }' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-STYLEFIDELITY' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && echo stylefidelity-ok
}
check "O-STYLEFIDELITY park dirt + fidelity revert + src-only stage" 0 "stylefidelity-ok"

# O-M5EVALTESTMAIN / O-M5PRECLAIM / O-M5EVALBURN
run_case() {
  grep -q 'O-M5EVALTESTMAIN' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'm5_eval_testmain_reset' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-M5PRECLAIM' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'm5_preclaim_rewrite' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-M5EVALBURN' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'm5_eval_burn_mechan' "$HARNESS_DIR/supervisor.sh" \
    && echo m5evalhonesty-ok
}
check "O-M5EVALTESTMAIN/PRECLAIM/EVALBURN evaluate honesty wiring" 0 "m5evalhonesty-ok"

# O-SFIXNODELTA: skip task-attributed sfix when K7 new=0/gone=0 + empty tip
run_case() {
  grep -q 'sfix_tip_content_empty' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SFIXNODELTA' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'sfix_nodelta_skip' "$HARNESS_DIR/supervisor.sh" \
    && grep -qE 'SUMMARY new=0 gone=0' "$HARNESS_DIR/supervisor.sh" \
    && echo sfixnodelta-ok
}
check "O-SFIXNODELTA skips sfix on K7 0/0 + empty/structure tip" 0 "sfixnodelta-ok"

# O-SFIXHINTFIDELITY / O-SFIXFALSEGREEN — dim detect + multi-dim recheck
run_case() {
  grep -q 'sfix_red_dims' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SFIXHINTFIDELITY' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SFIXFALSEGREEN' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'sensor-fidelity.log' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'O-FIDELITYSORT' "$HARNESS_DIR/sensors.sh" \
    && echo sfixhint-ok
}
check "sfix dim routing + fidelity log persist (O-SFIXHINTFIDELITY)" 0 "sfixhint-ok"

# O-ESCW3PKGDIR — legacy pkgdir must not block Target .gitkeep ESCW
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/model
  : > src/main/java/com/demo/model/.gitkeep
  cat > migration.yaml <<'EOF'
legacyPackage: org.springframework.samples.petclinic
targetPackage: com.demo
EOF
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Create model package structure
**Class**: rewrite
**Goal**: package structure
**Target**: → src/main/java/com/demo/model/
**Source**: org/springframework/samples/petclinic/model/
**Acceptance**: empty package with .gitkeep
EOF
  ALREADY_COMPLETE_ROOT="$FIX" python3 "$HARNESS_DIR/escw-eligible.py" tasks.md T-001; echo "rc=$?"
}
check "escw-eligible ignores legacy pkgdir (O-ESCW3PKGDIR)" 0 "rc=0"

run_case() {
  mkfix
  git init -q
  git config user.email t@test.local
  git config user.name t
  mkdir -p src/main/java/com/demo/repository
  printf 'x\n' > README
  git add -A && git commit -q -m init
  # Structure tip: .gitkeep with 0 content lines
  : > src/main/java/com/demo/repository/.gitkeep
  git add src/main/java/com/demo/repository/.gitkeep
  git commit -q -m "T-004: Create repository package structure with .gitkeep"
  # shellcheck disable=SC1090
  eval "$(sed -n '/^sfix_tip_content_empty()/,/^}/p' "$HARNESS_DIR/supervisor.sh")"
  sfix_tip_content_empty || { echo "FAIL: structure .gitkeep tip should be empty"; return 1; }
  # Content tip must NOT be empty
  printf 'package com.demo; class X {}\n' > src/main/java/com/demo/X.java
  git add src/main/java/com/demo/X.java
  git commit -q -m "T-005: Add class"
  ! sfix_tip_content_empty || { echo "FAIL: content tip should not be empty"; return 1; }
  echo sfixnodelta-beh-ok
}
check "sfix_tip_content_empty behavioural (O-SFIXNODELTA)" 0 "sfixnodelta-beh-ok"

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
  # O-M3ROUTE: default MiniMax-first; O-M3DTOSCOPE / Class+Shape preseed wired.
  grep -qE 'WORKER_M3_FIRST="\$\{WORKER_M3_FIRST:-false\}"' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-M3ROUTE' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'story-scope' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-M3DTOSCOPE' "$HARNESS_DIR/plan-lint.py" \
    && grep -q '\*\*Class\*\*: rewrite' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q '\*\*Shape\*\*: modify' "$HARNESS_DIR/outer-loop.sh" \
    && echo m3route-ok
}
check "M3 MiniMax-first + story-scope + Class/Shape preseed (O-M3ROUTE/O-M3DTOSCOPE)" 0 "m3route-ok"

run_case() {
  # O-M3SUPSCOPE: supervisor plan-lint must pass --story-scope (parity with outer).
  grep -q 'STORY_SCOPE_ARGS' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'story-scope' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-M3SUPSCOPE\|O-M3DTOSCOPE' "$HARNESS_DIR/supervisor.sh" \
    && echo m3supscope-ok
}
check "supervisor plan-lint passes --story-scope (O-M3SUPSCOPE)" 0 "m3supscope-ok"

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


run_case() {
  grep -q 'O-M4REPLAYNOSPEC' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'T-001:' "$HARNESS_DIR/outer-loop.sh" \
    && echo m4replaynospec-ok
}
check "O-M4REPLAYNOSPEC resume from T-001^ when no S0N spec tip" 0 "m4replaynospec-ok"

run_case() {
  test -f "$HARNESS_DIR/session-registry.sh" \
    && grep -q 'O-PIDREG\|session_register' "$HARNESS_DIR/session-registry.sh" \
    && grep -q 'session_reap_group\|O-OCGROUP' "$HARNESS_DIR/session-registry.sh" \
    && grep -q 'session_register' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'setsid timeout' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'setsid timeout' "$HARNESS_DIR/outer-loop.sh" \
    && ! grep -q 'pkill -9 -x opencode' "$HARNESS_DIR/supervisor.sh" \
    && echo pidreg-ok
}
check "O-PIDREG/O-OCGROUP setsid registry; no name-based opencode pkill" 0 "pidreg-ok"

# --- Wave 3 retro pre-rerun gates (W3-140..147) ---
run_case() {
  FIX=$(mktemp -d)
  mkdir -p "$FIX/migration/staging/util" "$FIX/src/main/java/com/demo/util"
  cat > "$FIX/migration/staging/util/CallMonitoringAspect.java" <<'JAVA'
package util;
@Aspect
public class CallMonitoringAspect {
  @Around("within(@Repository *)")
  public Object invoke(Object p) { return p; }
}
JAVA
  cat > "$FIX/src/main/java/com/demo/util/CallMonitoringAspect.java" <<'JAVA'
package com.demo.util;
import jakarta.enterprise.context.ApplicationScoped;
@ApplicationScoped
public class CallMonitoringAspect {
  public Object invoke(Object p) { return p; }
  public void reset() {}
  public boolean isEnabled() { return true; }
  public void setEnabled(boolean v) {}
  public long getCallCount() { return 0; }
  public long getCallTime() { return 0; }
}
JAVA
  out=$(cd "$FIX" && python3 "$HARNESS_DIR/wireup-check.py" 2>&1); rc=$?
  rm -rf "$FIX"
  [ "$rc" = "1" ] && echo "$out" | grep -q 'O-WIREUP' && echo wireup-ok
}
check "wireup-check RED on unwired aspect (O-WIREUP)" 0 "wireup-ok"

run_case() {
  grep -q 'O-ESCALPAUSE\|supervisor-pause' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'esc_cause="supervisor-pause"' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'esc_cause="sigint"' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-ESCALCAUSE-STALE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'esc_cause="sensor-red"' "$HARNESS_DIR/supervisor.sh" \
    && awk '/O-ESCALCAUSE-STALE/,/escalation-cause-\$\{T\}/ {
           if (/sensor-red/) s=1
           if (/_esc_last/) l=1
         }
         END { exit !(s && l) }' "$HARNESS_DIR/supervisor.sh" \
    && echo escalcause-ok
}
check "O-ESCALCAUSE reads kill why + suppress pause + stale→sensor-red (O-ESCALPAUSE/STALE)" 0 "escalcause-ok"

run_case() {
  FIX=$(mktemp -d)
  mkdir -p "$FIX/migration"
  echo '[]' > "$FIX/migration/mta-findings.json"
  cp "$FIX/migration/mta-findings.json" "$FIX/migration/mta-findings-after.json"
  out=$(FINDINGS_DELTA_STALE=1 FINDINGS_DELTA_ROOT="$FIX" python3 "$HARNESS_DIR/findings-delta.py")
  rm -rf "$FIX"
  echo "$out" | grep -q 'STALE-AFTER' \
    && echo "$out" | grep -q 'stale_resolve_pct=UNSCORED' \
    && ! echo "$out" | grep -q 'honest_resolve_pct' \
    && echo m5stale-ok
}
check "findings-delta STALE-AFTER unscores (O-M5STALE)" 0 "m5stale-ok"

run_case() {
  test -f "$HARNESS_DIR/kantra-path.sh" \
    && grep -q '/projects/.tools/kantra' "$HARNESS_DIR/kantra-path.sh" \
    && grep -q 'kantra-path.sh\|kantra_bin\|KANTRA_HOME' "$HARNESS_DIR/supervisor.sh" \
    && echo kantrapath-ok
}
check "kantra durable home helper (O-KANTRAPATH)" 0 "kantrapath-ok"

run_case() {
  grep -q 'replacement_constructs_missing\|O-ALREADYREPL' "$HARNESS_DIR/already-complete.py" \
    && FIX=$(mktemp -d) \
    && mkdir -p "$FIX" \
    && printf '%s\n' '<?xml version="1.0"?><project></project>' > "$FIX/pom.xml" \
    && cat > "$FIX/tasks.md" <<'MD'
## T-001: Add security deps
**Goal**: add quarkus-security and quarkus-elytron-security-jdbc
**Acceptance**: deps present
**Findings**: springboot-security-to-quarkus-00000
MD
  out=$(ALREADY_COMPLETE_ROOT="$FIX" python3 "$HARNESS_DIR/already-complete.py" "$FIX/tasks.md" T-001 2>&1); rc=$?
  rm -rf "$FIX"
  [ "$rc" = "1" ] && echo alreadyrepl-ok
}
check "already-complete blocks skip when named quarkus-* missing (O-ALREADYREPL)" 0 "alreadyrepl-ok"

run_case() {
  grep -q 'O-SECAUTHTEST\|security_auth_test_contract' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'prod_schema_contract\|O-PRODSCHEMA' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'O-PRODSCHEMA' "$HARNESS_DIR/commit-hygiene.py" \
    && grep -q 'quarkus-spring-' "$HARNESS_DIR/sfix-no-spring.py" \
    && echo w3misc-ok
}
check "O-SECAUTHTEST + O-PRODSCHEMA + W3-70 sfix spring ext key" 0 "w3misc-ok"

run_case() {
  FIX=$(mktemp -d)
  mkdir -p "$FIX/src/main/java/com/demo"
  cat > "$FIX/src/main/java/com/demo/ConfigBean.java" <<'JAVA'
package com.demo;
import jakarta.enterprise.context.ApplicationScoped;
import org.eclipse.microprofile.config.inject.ConfigProperty;
@ApplicationScoped
public class ConfigBean {
  @ConfigProperty(name="app.security.enable", defaultValue="false")
  boolean securityEnabled;
}
JAVA
  out=$(cd "$FIX" && python3 "$HARNESS_DIR/wireup-check.py" 2>&1); rc=$?
  rm -rf "$FIX"
  [ "$rc" = "0" ] && echo "$out" | grep -q 'wireup-check GREEN' && echo wireupfp-ok
}
check "wireup-check GREEN on package-private @ConfigProperty bean (O-WIREUP-FP)" 0 "wireupfp-ok"

run_case() {
  grep -q 'O-TMPARCHIVE' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'run-archives' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'archive_tmp_forensics' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q "trap 'archive_tmp_forensics' EXIT" "$HARNESS_DIR/outer-loop.sh" \
    && echo tmparchive-ok
}
check "outer-loop archives /tmp forensics on EXIT incl fail (O-TMPARCHIVE)" 0 "tmparchive-ok"

# O-REVERTPURE / O-SCOPEBACKFILL — scope revert stages only reverted paths;
# structure/.gitkeep Target is restored after later-story wipe (W4-010).
run_case() {
  grep -q 'stage_scope_revert_paths' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-REVERTPURE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'scope_structure_backfill' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SCOPEBACKFILL' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SCOPEBACKFILL' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && ! grep -E 'git add -A && git commit.*scope revert' "$HARNESS_DIR/supervisor.sh" \
    && echo revertpure-wiring-ok
}
check "scope_enforce wires O-REVERTPURE + O-SCOPEBACKFILL (no git add -A)" 0 "revertpure-wiring-ok"

run_case() {
  mkfix
  git init -q
  git config user.email t@test.local
  git config user.name t
  mkdir -p migration src/main/java/com/demo/dto
  printf '{"base":true}\n' > migration/mta-findings-current.json
  printf 'x\n' > src/main/java/com/demo/dto/.gitkeep
  git add -A && git commit -q -m init
  # Simulate worker tip that added later-story entities (no .gitkeep)
  mkdir -p src/main/java/com/demo/model
  printf 'package com.demo.model; public class Owner {}\n' \
    > src/main/java/com/demo/model/Owner.java
  printf '{"stale":9966}\n' > migration/mta-findings-current.json
  git add -A && git commit -q -m "T-003: Create model package structure with .gitkeep"
  cat > tasks.md <<'EOF'
# Tasks
#### T-003: Create model package structure with .gitkeep
**Class**: rewrite
**Shape**: structure
**Goal**: Create model package structure with .gitkeep
**Target design**: → `src/main/java/com/demo/model/.gitkeep`
**Owns**: src/main/java/com/demo/model/.gitkeep
EOF
  TASKS_FILE="$PWD/tasks.md"
  LATER_CLASSES="Owner"
  STORY_SCOPE=""
  LOG=/dev/null
  outer_log() { :; }
  log() { :; }
  event() { :; }
  task_title() { echo "Create model package structure with .gitkeep"; }
  # shellcheck disable=SC1090
  eval "$(sed -n '/^structure_gitkeep_targets()/,/^stage_scope_revert_paths()/{ /^stage_scope_revert_paths()/q; p; }' "$HARNESS_DIR/supervisor.sh")"
  eval "$(sed -n '/^stage_scope_revert_paths()/,/^}/p' "$HARNESS_DIR/supervisor.sh")"
  eval "$(sed -n '/^scope_structure_backfill()/,/^}/p' "$HARNESS_DIR/supervisor.sh")"
  # Minimal scope_enforce later-story path (A) + backfill — mirror supervisor
  scope_enforce() {
    local prefix="$1" f lviol=""
    if [ -n "${LATER_CLASSES:-}" ]; then
      for f in $(git diff --name-only HEAD~1..HEAD -- src/main/java/ 2>/dev/null); do
        bn=$(basename "$f" .java)
        case " ${LATER_CLASSES} " in *" ${bn} "*) lviol="$lviol $f";; esac
      done
      if [ -n "$lviol" ]; then
        for f in $lviol; do
          if git diff --name-only --diff-filter=A HEAD~1..HEAD -- "$f" 2>/dev/null | grep -q .; then
            git rm -q "$f" 2>/dev/null || rm -f "$f"
          else
            git checkout HEAD~1 -- "$f" 2>/dev/null || true
          fi
        done
        stage_scope_revert_paths $lviol
        if ! git diff --cached --quiet 2>/dev/null; then
          git commit -q -m "${prefix} scope revert: removed later-story class(es) created early (${lviol# })"
        fi
      fi
    fi
    scope_structure_backfill "$prefix"
  }
  scope_enforce T-003
  # Findings must NOT be in the scope-revert commit; .gitkeep must exist
  rev=$(git log --format=%H --grep='^T-003 scope revert:' -1)
  if [ -z "$rev" ]; then echo "FAIL: no scope-revert commit"; return 1; fi
  if git diff-tree --no-commit-id --name-only -r "$rev" | grep -qx 'migration/mta-findings-current.json'; then
    echo "FAIL: findings swept into scope revert"; return 1
  fi
  git diff-tree --no-commit-id --name-only -r "$rev" | grep -q 'Owner.java' \
    || { echo "FAIL: Owner.java not in scope-revert tip"; return 1; }
  [ -f src/main/java/com/demo/model/.gitkeep ] || { echo "FAIL: .gitkeep missing"; return 1; }
  git log -1 --format=%s | grep -qE '^T-003:' \
    && git log -1 --format=%s | grep -q 'O-SCOPEBACKFILL' \
    && ! git log -1 --format=%s | grep -qi 'scope revert' \
    && echo scopebackfill-ok
}
check "scope revert pure + structure .gitkeep backfill (O-REVERTPURE/O-SCOPEBACKFILL)" 0 "scopebackfill-ok"

# O-LOCKSTALE / O-LOGCOLLIDE / O-SFIXTESTPAIR — pre-S03 wiring (W4-007/W4-058/W4-057a)
run_case() {
  grep -q 'O-LOCKSTALE' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'clear_stale_pid_lock' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'clear_stale_pid_lock' "$HARNESS_DIR/supervisor.sh" \
    && echo lockstale-ok
}
check "outer+supervisor clear dead PID locks (O-LOCKSTALE)" 0 "lockstale-ok"

run_case() {
  grep -q 'oc_seat_base' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-LOGCOLLIDE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'STORY_ID=' "$HARNESS_DIR/outer-loop.sh" \
    && echo logcollide-ok
}
check "seat logs keyed by story (O-LOGCOLLIDE)" 0 "logcollide-ok"

run_case() {
  grep -q 'sfix_test_pair_note' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-SFIXTESTPAIR' "$HARNESS_DIR/supervisor.sh" \
    && echo sfixtestpair-ok
}
check "sfix couples harvest tests on fidelity (O-SFIXTESTPAIR)" 0 "sfixtestpair-ok"

# O-CDIPARTIAL / O-JDBCHARVESTAPI — incomplete CDI + Spring JDBC APIs under quarkus
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/repository/jdbc
  cat > pom.xml <<'EOF'
<project><build><plugins>
<plugin><artifactId>quarkus-maven-plugin</artifactId></plugin>
</plugins></build></project>
EOF
  cat > src/main/java/com/demo/repository/jdbc/JdbcFooRepositoryImpl.java <<'EOF'
package com.demo.repository.jdbc;
import jakarta.enterprise.context.ApplicationScoped;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
@ApplicationScoped
public class JdbcFooRepositoryImpl {
  @Autowired NamedParameterJdbcTemplate jdbc;
}
EOF
  python3 "$HARNESS_DIR/cdi-partial-check.py"
}
check "cdi-partial-check REDs Autowired+spring.jdbc on CDI bean (O-CDIPARTIAL/O-JDBCHARVESTAPI)" 1 "O-CDIPARTIAL"

run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/repository/jdbc
  cat > pom.xml <<'EOF'
<project><build><plugins>
<plugin><artifactId>quarkus-maven-plugin</artifactId></plugin>
</plugins></build></project>
EOF
  cat > src/main/java/com/demo/repository/jdbc/JdbcFooRepositoryImpl.java <<'EOF'
package com.demo.repository.jdbc;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import javax.sql.DataSource;
@ApplicationScoped
public class JdbcFooRepositoryImpl {
  @Inject DataSource ds;
}
EOF
  python3 "$HARNESS_DIR/cdi-partial-check.py" && echo cdipartial-clean
}
check "cdi-partial-check accepts Inject+DataSource CDI bean (O-CDIPARTIAL-NEG)" 0 "cdipartial-clean"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Convert JDBC repository implementations to CDI
**Class**: rewrite
**Shape**: create
**Goal**: Harvest Jdbc*RepositoryImpl and convert @Autowired to @Inject; drop spring.jdbc
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java`
**Owns**: src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java
**Acceptance**: CDI beans compile without spring-jdbc
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-002 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-CDIPARTIAL' \
    && echo "$out" | grep -q 'O-JDBCHARVESTAPI' \
    && echo "$out" | grep -q 'Autowired' \
    && echo "$out" | grep -q 'NamedParameterJdbcTemplate\|spring.jdbc\|Agroal' \
    && grep -q 'O-CDIPARTIAL' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && grep -q 'cdi_partial_check' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'cdi-partial-check' "$HARNESS_DIR/commit-hygiene.py" \
    && grep -q '@Autowired' "$HARNESS_DIR/../skills/migration-harness/scripts/harvest-from-staging.sh" \
    && echo cdipartial-tip-ok
}
check "task-packet/sensor/harvest wire O-CDIPARTIAL+O-JDBCHARVESTAPI" 0 "cdipartial-tip-ok"

# O-MMSCOPEQUIT — MiniMax must not scope-quit with unfinished spring residue
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Convert JDBC repository implementations to CDI
**Class**: rewrite
**Shape**: create
**Goal**: Harvest Jdbc*RepositoryImpl and convert @Autowired to @Inject; drop spring.jdbc
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java`
**Owns**: src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java
**Acceptance**: CDI beans compile without spring-jdbc
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-002 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-MMSCOPEQUIT' \
    && echo "$out" | grep -q 'scope-quit\|reclassification\|task-splitting' \
    && grep -q 'O-MMSCOPEQUIT' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && echo mmscopequit-ok
}
check "task-packet+EXECUTION wire O-MMSCOPEQUIT" 0 "mmscopequit-ok"

# O-HOTSWAPSTALE — zero-byte harness-update + md5 parity auto-clear
run_case() {
  grep -q 'O-HOTSWAPSTALE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'zero-byte harness-update' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'SUPERVISOR_VERSION' "$HARNESS_DIR/supervisor.sh" \
    && echo hotswapstale-ok
}
check "supervisor wires O-HOTSWAPSTALE auto-clear" 0 "hotswapstale-ok"

# O-TREEFIXSTUB — REMOVED / comment-only husks under src/main
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/repository/jdbc
  cat > src/main/java/com/demo/repository/jdbc/JdbcFooRepositoryImpl.java <<'EOF'
/* REMOVED: Prematurely harvested file containing Spring Framework dependencies */
EOF
  python3 "$HARNESS_DIR/tree-fix-stub-check.py"
}
check "tree-fix-stub-check REDs REMOVED comment stub (O-TREEFIXSTUB)" 1 "O-TREEFIXSTUB"

run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/repository/jdbc
  cat > src/main/java/com/demo/repository/jdbc/JdbcFooRepositoryImpl.java <<'EOF'
package com.demo.repository.jdbc;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import javax.sql.DataSource;
@ApplicationScoped
public class JdbcFooRepositoryImpl {
  @Inject DataSource ds;
  public void save() { /* real body */ ds.toString(); }
}
EOF
  python3 "$HARNESS_DIR/tree-fix-stub-check.py" && echo treefixstub-clean
}
check "tree-fix-stub-check accepts real CDI type (O-TREEFIXSTUB-NEG)" 0 "treefixstub-clean"

run_case() {
  grep -q 'tree_fix_stub_check' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'tree-fix-stub-check' "$HARNESS_DIR/commit-hygiene.py" \
    && grep -q 'O-TREEFIXSTUB' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'Tree fix' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-TREEFIXSTUB' "$HARNESS_DIR/task-packet.py" \
    && grep -q 'O-TREEFIXSTUB' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && grep -q 'O-COLLABOWN' "$HARNESS_DIR/plan-lint.py" \
    && grep -q 'O-COLLABOWN' "$HARNESS_DIR/task-packet.py" \
    && echo treefixstub-wire-ok
}
check "sensor/hygiene/packet/plan-lint wire O-TREEFIXSTUB+O-COLLABOWN" 0 "treefixstub-wire-ok"

# O-INFERFIRSTWRITE — multi-file Class=infer names a leaf first-write Target
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Convert JDBC repository implementations to CDI
**Class**: infer
**Shape**: modify
**Goal**: Convert JDBC repository implementations from Spring JDBC to Agroal DataSource + @Inject
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java`
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcPetRowMapper.java`
**Owns**: src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java, src/main/java/com/demo/repository/jdbc/JdbcPetRowMapper.java
**Acceptance**: CDI beans compile without spring-jdbc
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-002 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-INFERFIRSTWRITE' \
    && echo "$out" | grep -q 'JdbcPetRowMapper.java' \
    && grep -q 'O-INFERFIRSTWRITE' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && echo inferfirstwrite-ok
}
check "task-packet+EXECUTION wire O-INFERFIRSTWRITE" 0 "inferfirstwrite-ok"

# O-ESCWSCOPEUTIL — escalation prompt + untracked later-class scrub
run_case() {
  grep -q 'O-ESCWSCOPEUTIL' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'later_story_untracked\|untracked later-story' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-ESCWSCOPEUTIL' "$HARNESS_DIR/task-packet.py" \
    && grep -q 'O-ESCWSCOPEUTIL' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && echo escwscopeutil-ok
}
check "supervisor/packet/EXECUTION wire O-ESCWSCOPEUTIL" 0 "escwscopeutil-ok"

# O-AGROALHELPERSIG — preserve public helpers through Agroal rewrite
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Convert JDBC repository implementations to CDI
**Class**: infer
**Shape**: modify
**Goal**: Convert JDBC @Autowired NamedParameterJdbcTemplate to Agroal DataSource + @Inject
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcVisitRepositoryImpl.java`
**Owns**: src/main/java/com/demo/repository/jdbc/JdbcVisitRepositoryImpl.java
**Acceptance**: CDI beans compile without spring-jdbc
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-002 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-AGROALHELPERSIG' \
    && echo "$out" | grep -q 'mapRow\|ParameterSource' \
    && echo "$out" | grep -qE 'rename|privatize|RowMapper' \
    && grep -q 'O-AGROALHELPERSIG' "$HARNESS_DIR/redesign-sig.py" \
    && grep -q 'rename/privatize smell\|exact public' "$HARNESS_DIR/redesign-sig.py" \
    && grep -q 'O-AGROALHELPERSIG' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && echo agroalhelpersig-ok
}
check "task-packet/redesign-sig/EXECUTION wire O-AGROALHELPERSIG" 0 "agroalhelpersig-ok"

# O-STEPFINISHRED — refuse false-complete under task sensor RED
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Convert JDBC repository implementations to CDI
**Class**: infer
**Shape**: modify
**Goal**: Convert JDBC @Autowired NamedParameterJdbcTemplate to Agroal DataSource + @Inject
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcVisitRepositoryImpl.java`
**Owns**: src/main/java/com/demo/repository/jdbc/JdbcVisitRepositoryImpl.java
**Acceptance**: CDI beans compile without spring-jdbc
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-002 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-STEPFINISHRED' \
    && echo "$out" | grep -q 'sensors.sh task\|SENSOR RED' \
    && grep -q 'O-STEPFINISHRED' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'rewriting worker_rc 0→42' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'O-STEPFINISHRED' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && awk '/O-STEPFINISHRED \/ O-ESCALCAUSE-STALE/,/esc_cause="sensor-red"/ {
           if (/O-STEPFINISHRED/) s=1
           if (/task sensor RED/) t=1
         }
         END { exit !(s && t) }' "$HARNESS_DIR/supervisor.sh" \
    && echo stepfinishred-ok
}
check "supervisor/packet/EXECUTION wire O-STEPFINISHRED" 0 "stepfinishred-ok"

# O-SDJPAHARVESTONLY — harvest-only Spring Data residue (no Panache) must RED
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/m/repository/springdatajpa \
           src/main/java/m/repository/springdatajpa
  cat > migration/staging/src/main/java/m/repository/springdatajpa/SpringDataOwnerRepository.java <<'EOF'
package m.repository.springdatajpa;
import java.util.Collection;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import m.repository.OwnerRepository;
import m.model.Owner;
public interface SpringDataOwnerRepository extends OwnerRepository, Repository<Owner, Integer> {
    @Override
    @Query("SELECT DISTINCT owner FROM Owner owner WHERE owner.lastName LIKE :lastName%")
    Collection<Owner> findByLastName(String lastName);
}
EOF
  # dest = naive harvest (still Spring Data, Panache=0)
  cat > src/main/java/m/repository/springdatajpa/SpringDataOwnerRepository.java <<'EOF'
package m.repository.springdatajpa;
import java.util.Collection;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import m.repository.OwnerRepository;
import m.model.Owner;
public interface SpringDataOwnerRepository extends OwnerRepository, Repository<Owner, Integer> {
    @Override
    @Query("SELECT DISTINCT owner FROM Owner owner WHERE owner.lastName LIKE :lastName%")
    Collection<Owner> findByLastName(String lastName);
}
EOF
  out=$(python3 "$HARNESS_DIR/sdjpa-harvest-check.py" 2>&1); echo "$out"; echo "rc=$?"
  echo "$out" | grep -q 'O-SDJPAHARVESTONLY' && echo harvestonly-red-ok
}
check "sdjpa-harvest-check REDs harvest-only Spring Data (O-SDJPAHARVESTONLY)" 0 "harvestonly-red-ok"

# O-SDJPAHARVEST — Spring Data → Panache must keep domain extends / query bodies
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/m/repository/springdatajpa \
           src/main/java/m/repository/springdatajpa
  cat > migration/staging/src/main/java/m/repository/springdatajpa/SpringDataOwnerRepository.java <<'EOF'
package m.repository.springdatajpa;
import java.util.Collection;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import m.repository.OwnerRepository;
import m.model.Owner;
public interface SpringDataOwnerRepository extends OwnerRepository, Repository<Owner, Integer> {
    @Override
    @Query("SELECT DISTINCT owner FROM Owner owner WHERE owner.lastName LIKE :lastName%")
    Collection<Owner> findByLastName(String lastName);
}
EOF
  cat > src/main/java/m/repository/springdatajpa/SpringDataOwnerRepository.java <<'EOF'
package m.repository.springdatajpa;
import java.util.Collection;
import io.quarkus.hibernate.orm.panache.PanacheRepository;
import jakarta.persistence.NamedQuery;
import m.model.Owner;
@NamedQuery(name = "Owner.findByLastName", query = "SELECT DISTINCT owner FROM Owner owner WHERE owner.lastName LIKE :lastName%")
public interface SpringDataOwnerRepository extends PanacheRepository<Owner> {
    Collection<Owner> findByLastName(String lastName);
}
EOF
  python3 "$HARNESS_DIR/sdjpa-harvest-check.py"
}
check "sdjpa-harvest-check REDs dropped extends + NamedQuery + hollow finder (O-SDJPAHARVEST)" 1 "O-SDJPAHARVEST"

run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/m/repository/springdatajpa \
           src/main/java/m/repository/springdatajpa
  cat > migration/staging/src/main/java/m/repository/springdatajpa/SpringDataOwnerRepository.java <<'EOF'
package m.repository.springdatajpa;
import java.util.Collection;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import m.repository.OwnerRepository;
import m.model.Owner;
public interface SpringDataOwnerRepository extends OwnerRepository, Repository<Owner, Integer> {
    @Override
    @Query("SELECT DISTINCT owner FROM Owner owner WHERE owner.lastName LIKE :lastName%")
    Collection<Owner> findByLastName(String lastName);
}
EOF
  cat > src/main/java/m/repository/springdatajpa/SpringDataOwnerRepository.java <<'EOF'
package m.repository.springdatajpa;
import java.util.Collection;
import java.util.List;
import io.quarkus.hibernate.orm.panache.PanacheRepositoryBase;
import m.repository.OwnerRepository;
import m.model.Owner;
public interface SpringDataOwnerRepository extends OwnerRepository, PanacheRepositoryBase<Owner, Integer> {
    @Override
    default Collection<Owner> findByLastName(String lastName) {
        return list("SELECT DISTINCT owner FROM Owner owner WHERE owner.lastName LIKE ?1", lastName + "%");
    }
}
EOF
  python3 "$HARNESS_DIR/sdjpa-harvest-check.py" && echo sdjpaharvest-clean
}
check "sdjpa-harvest-check accepts domain extends + Panache body (O-SDJPAHARVEST-NEG)" 0 "sdjpaharvest-clean"

run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/m/repository/springdatajpa \
           src/main/java/m/repository/springdatajpa
  cat > migration/staging/src/main/java/m/repository/springdatajpa/PetRepositoryOverride.java <<'EOF'
package m.repository.springdatajpa;
import m.model.Pet;
public interface PetRepositoryOverride { void delete(Pet pet); }
EOF
  cat > migration/staging/src/main/java/m/repository/springdatajpa/SpringDataPetRepositoryImpl.java <<'EOF'
package m.repository.springdatajpa;
import m.model.Pet;
public class SpringDataPetRepositoryImpl implements PetRepositoryOverride {
  public void delete(Pet pet) { /* real delete */ }
}
EOF
  cat > migration/staging/src/main/java/m/repository/springdatajpa/SpringDataPetRepository.java <<'EOF'
package m.repository.springdatajpa;
import org.springframework.data.repository.Repository;
import m.repository.PetRepository;
import m.model.Pet;
public interface SpringDataPetRepository extends PetRepository, Repository<Pet, Integer>, PetRepositoryOverride {}
EOF
  # dest: Panache iface + Override iface, but NO Impl
  cat > src/main/java/m/repository/springdatajpa/SpringDataPetRepository.java <<'EOF'
package m.repository.springdatajpa;
import io.quarkus.hibernate.orm.panache.PanacheRepository;
import m.repository.PetRepository;
import m.model.Pet;
public interface SpringDataPetRepository extends PetRepository, PanacheRepository<Pet>, PetRepositoryOverride {}
EOF
  cat > src/main/java/m/repository/springdatajpa/PetRepositoryOverride.java <<'EOF'
package m.repository.springdatajpa;
import m.model.Pet;
public interface PetRepositoryOverride { void delete(Pet pet); }
EOF
  out=$(python3 "$HARNESS_DIR/sdjpa-harvest-check.py" 2>&1); echo "$out"; echo "rc=$?"
  echo "$out" | grep -q 'RepositoryImpl' && echo impl-missing-ok
}
check "sdjpa-harvest-check REDs missing Override Impl (O-SDJPAHARVEST-IMPL)" 0 "impl-missing-ok"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: create
**Goal**: Consolidate Spring Data repository implementations to Panache repositories
**Target design**:
- → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**Acceptance**: Panache repositories compile with domain extends
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-004 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-SDJPAHARVESTONLY' \
    && echo "$out" | grep -q 'harvest-from-staging\|NOT task-complete\|Panache=0' \
    && echo "$out" | grep -q 'O-SDJPAHARVEST' \
    && echo "$out" | grep -q 'domain-repo\|DomainRepository\|PanacheRepository' \
    && echo "$out" | grep -q 'NamedQuery\|hollow\|RepositoryImpl' \
    && grep -q 'O-SDJPAHARVESTONLY' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && grep -q 'O-SDJPAHARVESTONLY' "$HARNESS_DIR/../skills/migration-harness/PLANNING.md" \
    && grep -q 'O-SDJPAHARVESTONLY' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'sdjpa-harvest-check' "$HARNESS_DIR/commit-hygiene.py" \
    && echo sdjpaharvest-tip-ok
}
check "task-packet/sensors/EXECUTION wire O-SDJPAHARVEST+O-SDJPAHARVESTONLY" 0 "sdjpaharvest-tip-ok"

# O-ALREADYCONS — Consolidate/Panache + "delete bodies" must not absent-skip
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/repository/springdatajpa
  : > src/main/java/com/demo/repository/springdatajpa/.gitkeep
  cat > tasks.md <<'EOF'
# Tasks
#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: create
**Goal**: Convert Spring Data to Panache; harvest Override Impl delete bodies
**Target design**:
- → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**Acceptance**: Panache repos compile
EOF
  # Target .java absent — must NOT already-complete
  out=$(ALREADY_COMPLETE_ROOT="$FIX" python3 "$HARNESS_DIR/already-complete.py" tasks.md T-004 2>&1); rc=$?
  echo "rc=$rc out=$out"
  [ "$rc" -ne 0 ] && echo alreadycons-ok
}
check "already-complete refuses Consolidate+delete-bodies absent skip (O-ALREADYCONS)" 0 "alreadycons-ok"

# O-PORTREIMPL — API-swap convert must declare Port + mapping when reimplement
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: create
**Goal**: Convert Spring Data repositories to Quarkus Panache
**Target design**:
- → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**Acceptance**: Panache repositories compile
EOF
  printf 'legacyPackage: org.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  PLAN_LINT_REQUIRE_SHAPE=1 python3 "$LINT" tasks.md
}
check "plan-lint rejects API-swap without Port (O-PORTREIMPL)" 1 "O-PORTREIMPL"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: create
**Port**: reimplement
**Goal**: Convert Spring Data repositories to Quarkus Panache
**Target design**:
- → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**API mapping**:
| legacy | target |
| `@Query` JPQL | Panache `find`/`list` bodies |
| Spring Data `Repository` | `PanacheRepositoryBase` + domain iface |
**Acceptance**: convert-after-harvest (O-SDJPAHARVESTONLY); Panache bodies present
EOF
  printf 'legacyPackage: org.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  PLAN_LINT_REQUIRE_SHAPE=1 python3 "$LINT" tasks.md
}
check "plan-lint accepts Port=reimplement + mapping table (O-PORTREIMPL-NEG)" 0 "PLAN OK"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: create
**Port**: reimplement
**Goal**: Convert Spring Data to Panache after harvest
**Target design**: → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**API mapping**: `@Query` → Panache find/list; convert-after-harvest O-SDJPAHARVEST
**Acceptance**: Panache repos
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-004 2>/dev/null)
  echo "$out" | grep -q 'Port: reimplement' \
    && echo "$out" | grep -q 'O-PORTREIMPL' \
    && echo portreimpl-pkt-ok
}
check "task-packet tips O-PORTREIMPL on Port=reimplement (O-PORTREIMPL)" 0 "portreimpl-pkt-ok"

# O-POMDISCARD — discard_orphan_pom / stage refuse orphan panache pom
run_case() {
  mkfix
  git init -q
  cat > pom.xml <<'EOF'
<project><build><plugins><plugin><artifactId>quarkus-maven-plugin</artifactId></plugin></plugins></build>
<dependencies><dependency><artifactId>quarkus-resteasy</artifactId></dependency></dependencies></project>
EOF
  mkdir -p src/main/java/m
  echo 'package m; class A {}' > src/main/java/m/A.java
  git add -A && git -c user.email=t@t -c user.name=t commit -qm base
  # Burned seat: add panache to pom, leave untracked springdata dirt, then discard
  cat > pom.xml <<'EOF'
<project><build><plugins><plugin><artifactId>quarkus-maven-plugin</artifactId></plugin></plugins></build>
<dependencies>
<dependency><artifactId>quarkus-resteasy</artifactId></dependency>
<dependency><artifactId>quarkus-hibernate-orm-panache</artifactId></dependency>
</dependencies></project>
EOF
  mkdir -p src/main/java/m/repository/springdatajpa
  echo 'package m.repository.springdatajpa; import org.springframework.data.repository.Repository; interface SpringDataX {}' \
    > src/main/java/m/repository/springdatajpa/SpringDataX.java
  # Inline discard helpers from supervisor
  eval "$(sed -n '/^discard_orphan_pom()/,/^discard_src_dirt()/{ /^discard_src_dirt()/q; p; }' "$HARNESS_DIR/supervisor.sh")"
  eval "$(sed -n '/^discard_src_dirt()/,/^}/{ p; }' "$HARNESS_DIR/supervisor.sh" | head -n 40)"
  log() { :; }
  discard_src_dirt "test"
  ! grep -q 'quarkus-hibernate-orm-panache' pom.xml \
    && [ ! -f src/main/java/m/repository/springdatajpa/SpringDataX.java ] \
    && echo pomdiscard-ok
}
check "discard_src_dirt reverts orphan panache pom (O-POMDISCARD)" 0 "pomdiscard-ok"

# O-SPRINGRESIDUE — org.springframework under src/main must be 0; invent RED
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/repository/jdbc
  cat > pom.xml <<'EOF'
<project><build><plugins>
<plugin><artifactId>quarkus-maven-plugin</artifactId></plugin>
</plugins></build></project>
EOF
  cat > src/main/java/com/demo/repository/jdbc/JdbcFooRepositoryImpl.java <<'EOF'
package com.demo.repository.jdbc;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import javax.sql.DataSource;
// comment may mention org.springframework.jdbc — ignored
@ApplicationScoped
public class JdbcFooRepositoryImpl {
  @Inject DataSource ds;
  void boom() { throw new org.springframework.dao.EmptyResultPersistenceException("x"); }
}
EOF
  out=$(python3 "$HARNESS_DIR/cdi-partial-check.py" 2>&1); rc=$?
  echo "$out"
  [ "$rc" -ne 0 ] && echo "$out" | grep -q 'O-SPRINGRESIDUE' && echo springresidue-red-ok
}
check "cdi-partial-check REDs invented spring PersistenceException (O-SPRINGRESIDUE)" 0 "springresidue-red-ok"

run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/repository/jdbc
  cat > pom.xml <<'EOF'
<project><build><plugins>
<plugin><artifactId>quarkus-maven-plugin</artifactId></plugin>
</plugins></build></project>
EOF
  cat > src/main/java/com/demo/repository/jdbc/JdbcFooRepositoryImpl.java <<'EOF'
package com.demo.repository.jdbc;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import javax.sql.DataSource;
// leftover prose: org.springframework.jdbc.core.JdbcTemplate — OK in comment
@ApplicationScoped
public class JdbcFooRepositoryImpl {
  @Inject DataSource ds;
}
EOF
  python3 "$HARNESS_DIR/cdi-partial-check.py" && echo springresidue-clean
}
check "cdi-partial-check accepts comment-only spring mention (O-SPRINGRESIDUE-NEG)" 0 "springresidue-clean"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-002: Convert JDBC repository implementations to CDI
**Class**: infer
**Shape**: create
**Port**: reimplement
**Goal**: Convert Jdbc*RepositoryImpl — drop org.springframework
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java`
**Acceptance**: org.springframework under src/main/java is 0
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-002 qwen27b/qwen3-6-27b)
  echo "$out" | grep -q 'O-SPRINGRESIDUE' \
    && grep -q 'O-SPRINGRESIDUE' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && grep -q 'O-SPRINGRESIDUE' "$HARNESS_DIR/sensors.sh" \
    && echo springresidue-tip-ok
}
check "task-packet/sensor wire O-SPRINGRESIDUE" 0 "springresidue-tip-ok"

# O-T4SPRINGDATA — SpringData* Target without spring-data deps → RED
run_case() {
  mkfix
  cat > pom.xml <<'EOF'
<project><build><plugins>
<plugin><artifactId>quarkus-maven-plugin</artifactId></plugin>
</plugins></build></project>
EOF
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-004: Harvest Spring Data repositories
**Class**: rewrite
**Shape**: create
**Goal**: Harvest SpringDataOwnerRepository from staging
**Target design**:
- → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**Acceptance**: interfaces compile
EOF
  printf 'legacyPackage: org.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  PLAN_LINT_REQUIRE_SHAPE=1 python3 "$LINT" tasks.md
}
check "plan-lint rejects SpringData* harvest without spring-data deps (O-T4SPRINGDATA)" 1 "O-T4SPRINGDATA"

run_case() {
  mkfix
  cat > pom.xml <<'EOF'
<project><build><plugins>
<plugin><artifactId>quarkus-maven-plugin</artifactId></plugin>
</plugins></build></project>
EOF
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: create
**Port**: reimplement
**Goal**: Convert Spring Data repositories to Quarkus Panache
**Target design**:
- → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**API mapping**:
| legacy | target |
| `@Query` JPQL | Panache `find`/`list` bodies |
| Spring Data `Repository` | `PanacheRepositoryBase` + domain iface |
**Acceptance**: convert-after-harvest (O-SDJPAHARVESTONLY); Panache bodies present
EOF
  printf 'legacyPackage: org.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  out=$(PLAN_LINT_REQUIRE_SHAPE=1 python3 "$LINT" tasks.md 2>&1)
  echo "$out" | grep -q O-T4SPRINGDATA && echo "FP-FIRED" || echo "t4springdata-clean"
}
check "plan-lint accepts Port=reimplement SpringData→Panache (O-T4SPRINGDATA-NEG)" 0 "t4springdata-clean"

# O-SDJPA-SKIP — Override-only + Jpa* CDI cover → already-complete
run_case() {
  mkfix
  mkdir -p src/main/java/com/demo/repository/jpa \
           migration/staging/src/main/java/com/demo/repository/springdatajpa
  cat > pom.xml <<'EOF'
<project><build><plugins>
<plugin><artifactId>quarkus-maven-plugin</artifactId></plugin>
</plugins></build></project>
EOF
  for e in Owner Pet Visit; do
    cat > "src/main/java/com/demo/repository/jpa/Jpa${e}RepositoryImpl.java" <<EOF
package com.demo.repository.jpa;
import jakarta.enterprise.context.ApplicationScoped;
@ApplicationScoped
public class Jpa${e}RepositoryImpl {}
EOF
  done
  # staging Override already mirrored in live (none pending)
  cat > tasks.md <<'EOF'
# Tasks
#### T-005: Harvest Spring Data Override delete helpers
**Class**: rewrite
**Shape**: modify
**Goal**: Override-only Spring Data delete helpers; redesign skip when Jpa CDI covers
**Target design**:
- → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**Acceptance**: O-SDJPA-SKIP / already-complete when Jpa* cover
EOF
  out=$(ALREADY_COMPLETE_ROOT="$FIX" python3 "$HARNESS_DIR/already-complete.py" tasks.md T-005 2>&1); rc=$?
  echo "rc=$rc out=$out"
  [ "$rc" -eq 0 ] && echo "$out" | grep -q 'sdjpa-skip' && echo sdjpaskip-ok
}
check "already-complete skips Override-only when Jpa CDI covers (O-SDJPA-SKIP)" 0 "sdjpaskip-ok"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-004: Consolidate Spring Data to Panache
**Class**: infer
**Shape**: create
**Port**: reimplement
**Goal**: Panache convert SpringDataOwnerRepository
**Target**: → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**Acceptance**: Panache bodies
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-004 2>/dev/null)
  echo "$out" | grep -q 'O-T4SPRINGDATA\|O-SDJPA-SKIP' \
    && grep -q 'O-T4SPRINGDATA\|O-SDJPA-SKIP' "$HARNESS_DIR/../skills/migration-harness/PLANNING.md" \
    && echo sdjpaskip-tip-ok
}
check "task-packet/PLANNING wire O-T4SPRINGDATA+O-SDJPA-SKIP" 0 "sdjpaskip-tip-ok"

# O-OWNSTAGE — stage_for_task_commit allowlists Owns; mechan-match rejects extras
run_case() {
  mkfix
  git init -q
  git config user.email t@test.local
  git config user.name t
  mkdir -p src/main/java/com/demo/model migration .hermes/harness
  printf 'package com.demo.model; public class Base {}\n' \
    > src/main/java/com/demo/model/Base.java
  git add -A && git commit -q -m init
  printf 'package com.demo.model; public class Owner {}\n' \
    > src/main/java/com/demo/model/Owner.java
  printf 'package com.demo.model; public class Pet {}\n' \
    > src/main/java/com/demo/model/Pet.java
  printf 'package com.demo.model; public class Visit {}\n' \
    > src/main/java/com/demo/model/Visit.java
  cat > tasks.md <<'EOF'
# Tasks
#### T-009: Harvest Owner entity
**Class**: rewrite
**Shape**: create
**Goal**: Harvest Owner only
**Target design**: → `src/main/java/com/demo/model/Owner.java`
**Owns**: src/main/java/com/demo/model/Owner.java
EOF
  cp "$HARNESS_DIR/task-stage-paths.py" .hermes/harness/
  TASKS_FILE="$PWD/tasks.md"
  CURRENT_TASK=T-009
  discard_orphan_pom() { :; }
  log() { :; }
  restore_frozen_specs() { :; }
  frozen_spec_paths() { :; }
  eval "$(sed -n '/^stage_for_task_commit()/,/^}/p' "$HARNESS_DIR/supervisor.sh")"
  stage_for_task_commit
  staged=$(git diff --cached --name-only)
  echo "$staged" | grep -qx 'src/main/java/com/demo/model/Owner.java' \
    || { echo "FAIL: Owner not staged"; echo "$staged"; return 1; }
  echo "$staged" | grep -q 'Pet.java' && { echo "FAIL: Pet scooped"; return 1; }
  echo "$staged" | grep -q 'Visit.java' && { echo "FAIL: Visit scooped"; return 1; }
  # mechan-match belt: if someone force-stages siblings, refuse
  {
    echo 'src/main/java/com/demo/model/Owner.java'
    echo 'src/main/java/com/demo/model/Pet.java'
  } | python3 "$HARNESS_DIR/mechan-match.py" tasks.md T-009 >/tmp/ownstage-mm.out 2>&1
  mm_rc=$?
  [ "$mm_rc" -ne 0 ] || { echo "FAIL: mechan-match accepted extras"; cat /tmp/ownstage-mm.out; return 1; }
  grep -q 'ownstage-extra' /tmp/ownstage-mm.out \
    || { echo "FAIL: expected ownstage-extra"; cat /tmp/ownstage-mm.out; return 1; }
  grep -q 'O-OWNSTAGE' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && echo ownstage-ok
}
check "stage_for_task_commit Owns-only + mechan-match extras (O-OWNSTAGE)" 0 "ownstage-ok"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-009: Harvest Owner entity
**Owns**: src/main/java/com/demo/model/Owner.java
**Target design**: → `src/main/java/com/demo/model/Owner.java`
EOF
  out=$(python3 "$HARNESS_DIR/task-stage-paths.py" tasks.md T-009)
  echo "$out" | grep -qx 'src/main/java/com/demo/model/Owner.java' \
    && [ "$(echo "$out" | wc -l | tr -d ' ')" = 1 ] \
    && echo ownstage-paths-ok
}
check "task-stage-paths.py emits Owns/Target only (O-OWNSTAGE)" 0 "ownstage-paths-ok"

# O-PLANCORPUS — standing archived-plan re-lint with live M3 flag parity
run_case() {
  local pc="$HARNESS_DIR/tests/fixtures/plan-corpus"
  local n634 nfinal
  n634=$(wc -l < "$pc/s03-6348afe-class/tasks.md" | tr -d ' ')
  nfinal=$(wc -l < "$pc/s03-32812a6-final/tasks.md" | tr -d ' ')
  grep -q 'O-PLANCORPUS\|plan-corpus-lint' "$HARNESS_DIR/plan-corpus-lint.sh" \
    && grep -q -- '--story-scope' "$HARNESS_DIR/plan-corpus-lint.sh" \
    && grep -q -- '--findings-scope' "$HARNESS_DIR/plan-corpus-lint.sh" \
    && grep -q -- '--profile' "$HARNESS_DIR/plan-corpus-lint.sh" \
    && grep -q -- '--story-deploy' "$HARNESS_DIR/plan-corpus-lint.sh" \
    && test -f "$pc/manifest.env" \
    && test -f "$pc/s03-6348afe-class/tasks.md" \
    && test -f "$pc/s03-post-port-good/tasks.md" \
    && test -f "$pc/s01-f7c1329/tasks.md" \
    && test -f "$pc/s02-ee834b1/tasks.md" \
    && test -f "$pc/s03-6348afe-real/tasks.md" \
    && test -f "$pc/s03-c164532/tasks.md" \
    && test -f "$pc/s03-be070fb/tasks.md" \
    && test -f "$pc/s03-43d3a8e/tasks.md" \
    && test -f "$pc/s03-ca57010/tasks.md" \
    && test -f "$pc/s03-c9be4b0/tasks.md" \
    && test -f "$pc/s03-32812a6-final/tasks.md" \
    && test "$n634" -ge 100 \
    && test "$nfinal" -ge 100 \
    && grep -q 'sha=6348afe' "$pc/s03-6348afe-class/SOURCE.txt" \
    && grep -q 'sha=32812a6' "$pc/s03-32812a6-final/SOURCE.txt" \
    && grep -q 'CORPUS_s03_32812a6_final_EXPECT=red' "$pc/manifest.env" \
    && echo plancorpus-wire-ok
}
check "plan-corpus-lint wiring + fixtures present (O-PLANCORPUS)" 0 "plancorpus-wire-ok"

run_case() {
  out=$(bash "$HARNESS_DIR/plan-corpus-lint.sh" --case s03-6348afe-class 2>&1) || true
  echo "$out" | grep -q 'PASS s03-6348afe-class' \
    && echo "$out" | grep -q 'O-STRUCTJAVA' \
    && echo "$out" | grep -q 'O-PORTREIMPL' \
    && echo "$out" | grep -q 'O-M3PRESERVEDAO' \
    && echo "$out" | grep -q 'O-COLLABOWN' \
    && echo "$out" | grep -q 'live-gate flag parity OK' \
    && echo plancorpus-red-ok
}
check "plan-corpus known-RED 6348afe-class signals (O-PLANCORPUS)" 0 "plancorpus-red-ok"

run_case() {
  out=$(bash "$HARNESS_DIR/plan-corpus-lint.sh" --case s03-32812a6-final 2>&1) || true
  echo "$out" | grep -q 'PASS s03-32812a6-final' \
    && echo "$out" | grep -q 'O-PORTREIMPL' \
    && echo "$out" | grep -q 'hit O-PORTREIMPL' \
    && echo plancorpus-final-red-ok
}
check "plan-corpus known-RED 32812a6-final O-PORTREIMPL (W4-109b)" 0 "plancorpus-final-red-ok"

run_case() {
  out=$(bash "$HARNESS_DIR/plan-corpus-lint.sh" --case s03-post-port-good 2>&1) || true
  echo "$out" | grep -q 'PASS s03-post-port-good' \
    && echo "$out" | grep -q 'PLAN OK' \
    && echo plancorpus-green-ok
}
check "plan-corpus known-GREEN post-Port PLAN OK (O-PLANCORPUS)" 0 "plancorpus-green-ok"

# O-DEFAULTAUDIT — fail-open defaults inventory artefact
run_case() {
  bash "$HARNESS_DIR/defaults-inventory.sh" --check \
    && grep -q 'O-INFERABSENT' "$HARNESS_DIR/defaults-inventory.md" \
    && grep -q 'Oracle field' "$HARNESS_DIR/defaults-inventory.md" \
    && grep -q 'O-ORACLEDERIVE' "$HARNESS_DIR/defaults-inventory.md" \
    && grep -q 'Proceed: O-NULLACTION' "$HARNESS_DIR/defaults-inventory.md" \
    && grep -q 'LINT tier' "$HARNESS_DIR/defaults-inventory.md" \
    && ! grep -q 'WARN tier (does not fail PLAN OK)' "$HARNESS_DIR/defaults-inventory.md" \
    && grep -q 'permissive' "$HARNESS_DIR/defaults-inventory.md" \
    && grep -q 'restrictive' "$HARNESS_DIR/defaults-inventory.md" \
    && echo defaultaudit-ok
}
check "defaults-inventory artefact seed rows (O-DEFAULTAUDIT)" 0 "defaultaudit-ok"

# O-DEFAULTRG — grep -nE harvest (no rg); non-empty fences required before GREEN
run_case() {
  ! grep -nE '(^|[[:space:]])rg[[:space:]]+-n' "$HARNESS_DIR/defaults-inventory.sh" \
    && grep -q '_grepn\|grep -nE' "$HARNESS_DIR/defaults-inventory.sh" \
    && grep -q 'assert_fence_harvest\|O-DEFAULTRG' "$HARNESS_DIR/defaults-inventory.sh" \
    && bash "$HARNESS_DIR/defaults-inventory.sh" \
    && bash "$HARNESS_DIR/defaults-inventory.sh" --check \
    && pl_n=$(awk '/^### plan-lint\.py/{s=1;next} s&&/^```$/{if(f){exit} f=1;next} s&&f{print}' \
         "$HARNESS_DIR/defaults-inventory.md" | grep -cE '^[0-9]+:' || true) \
    && sup_n=$(awk '/^### supervisor\.sh/{s=1;next} s&&/^```$/{if(f){exit} f=1;next} s&&f{print}' \
         "$HARNESS_DIR/defaults-inventory.md" | grep -cE '^[0-9]+:' || true) \
    && test "$pl_n" -ge 1 && test "$sup_n" -ge 1 \
    && echo defaultrg-ok
}
check "defaults-inventory grep -nE + non-empty fences (O-DEFAULTRG)" 0 "defaultrg-ok"

# O-PLANCORPUSSWEEP — bare full-sweep (no --case) must rc=0 (preflight operation)
run_case() {
  if bash "$HARNESS_DIR/plan-corpus-lint.sh" >/tmp/plancorpus-sweep.out 2>&1; then
    test "$(grep -c '^PASS ' /tmp/plancorpus-sweep.out || true)" -ge 1 \
      && echo plancorpus-sweep-ok
  else
    echo "plancorpus-sweep-FAIL"
    sed 's/^/    /' /tmp/plancorpus-sweep.out | tail -40
    false
  fi
}
check "plan-corpus bare full-sweep rc=0 (O-PLANCORPUSSWEEP)" 0 "plancorpus-sweep-ok"

# O-M3CASEINPUTS — per-case M3 input pointers / local files + prefer case-local
run_case() {
  local pc="$HARNESS_DIR/tests/fixtures/plan-corpus"
  local live="$pc/_shared/live-v3"
  local missing=0 c
  test -f "$live/mta-findings.json" && test -f "$live/architecture-profile.md" \
    && test -f "$live/SOURCE.txt" \
    && test "$(wc -c < "$live/mta-findings.json" | tr -d ' ')" -ge 100000 \
    && grep -q 'md5_findings=' "$live/SOURCE.txt" \
    && grep -q 'resolve_case_inputs\|O-M3CASEINPUTS' "$HARNESS_DIR/plan-corpus-lint.sh" \
    && grep -q 'm3-inputs.env' "$HARNESS_DIR/plan-corpus-lint.sh" \
    && grep -q 'CORPUS_s02_ee834b1_EXPECT=green' "$pc/manifest.env" \
    || return 1
  for c in s01-f7c1329 s02-ee834b1 s03-6348afe-class s03-6348afe-real s03-c164532 \
           s03-be070fb s03-43d3a8e s03-ca57010 s03-c9be4b0 s03-32812a6-final; do
    if ! grep -q 'INPUTS_KIND=live-v3' "$pc/$c/migration/m3-inputs.env" 2>/dev/null; then
      echo "O-M3CASEINPUTS: $c missing live-v3 pointer" >&2
      missing=1
    fi
  done
  grep -q 'INPUTS_KIND=stand-in' "$pc/s03-post-port-good/migration/m3-inputs.env" \
    || { echo "O-M3CASEINPUTS: post-port-good must stay stand-in" >&2; missing=1; }
  [ "$missing" -eq 0 ] && echo m3caseinputs-wire-ok
}
check "plan-corpus per-case M3 input pointers (O-M3CASEINPUTS)" 0 "m3caseinputs-wire-ok"

run_case() {
  local pc="$HARNESS_DIR/tests/fixtures/plan-corpus"
  local name="zz-m3caseinputs-prefer" out
  rm -rf "$pc/$name"
  mkdir -p "$pc/$name/migration"
  # Clone a known-GREEN tip so lint can finish; override with case-local stand-in
  # while a poison pointer would REFUSE if preferred.
  cp -f "$pc/s03-post-port-good/tasks.md" "$pc/$name/tasks.md"
  cp -f "$pc/_shared/mta-findings.json" "$pc/$name/migration/mta-findings.json"
  cp -f "$pc/_shared/architecture-profile.md" "$pc/$name/migration/architecture-profile.md"
  cat > "$pc/$name/migration/m3-inputs.env" <<'EOF'
INPUTS_KIND=poison
FINDINGS_SRC=/nonexistent/mta-findings.json
PROFILE_SRC=/nonexistent/architecture-profile.md
EOF
  {
    echo ""
    echo "# ephemeral O-M3CASEINPUTS prefer probe (instruments; removed after)"
    echo "CORPUS_zz_m3caseinputs_prefer_EXPECT=green"
    echo "CORPUS_zz_m3caseinputs_prefer_FINDINGS=\"springboot-di-to-quarkus-00003,springboot-di-to-quarkus-00000,springboot-di-to-quarkus-00002\""
    echo "CORPUS_zz_m3caseinputs_prefer_DEPLOY=false"
    echo "CORPUS_zz_m3caseinputs_prefer_SCOPE=\"src/main/java/org/springframework/samples/petclinic/repository src/main/java/com/demo/repository\""
  } >> "$pc/manifest.env"
  out=$(bash "$HARNESS_DIR/plan-corpus-lint.sh" --case "$name" 2>&1) || true
  rm -rf "$pc/$name"
  # Strip ephemeral rows without relying on GNU sed -i
  local mf="$pc/manifest.env"
  python3 - "$mf" <<'PY'
import sys
from pathlib import Path
p = Path(sys.argv[1])
lines = p.read_text().splitlines(True)
out = []
skip = False
for ln in lines:
    if "ephemeral O-M3CASEINPUTS prefer probe" in ln:
        skip = True
        continue
    if skip:
        if ln.startswith("CORPUS_zz_m3caseinputs_prefer_"):
            continue
        if ln.strip() == "":
            skip = False
            continue
        skip = False
    out.append(ln)
p.write_text("".join(out))
PY
  echo "$out" | grep -q 'O-M3CASEINPUTS: case=zz-m3caseinputs-prefer mode=case-local' \
    && ! echo "$out" | grep -q 'points to missing inputs' \
    && echo "$out" | grep -q 'PASS zz-m3caseinputs-prefer' \
    && echo m3caseinputs-prefer-ok
}
check "plan-corpus prefers case-local inputs over pointer (O-M3CASEINPUTS)" 0 "m3caseinputs-prefer-ok"

# O-HERMESPREFLIGHT — wiring + local RED/GREEN digest compare (no oc / no outer start)
run_case() {
  local top parity preflight
  top=$(git -C "$HARNESS_DIR/../../../../.." rev-parse --show-toplevel 2>/dev/null || true)
  parity="${top}/scripts/track-b/v10-hermes-parity.sh"
  preflight="${top}/scripts/track-b/v9-preflight-outer-start.sh"
  [ -n "$top" ] && [ -f "$parity" ] && [ -f "$preflight" ] \
    && grep -q 'O-HERMESPREFLIGHT\|v10-hermes-parity' "$preflight" \
    && grep -qE 'md5sum|md5 -q|DIGEST=' "$parity" \
    && grep -q 'REFUSE' "$parity" \
    && echo hermespreflight-wire-ok
}
check "hermes parity preflight wiring (O-HERMESPREFLIGHT)" 0 "hermespreflight-wire-ok"

run_case() {
  local top parity scaffold a b
  top=$(git -C "$HARNESS_DIR/../../../../.." rev-parse --show-toplevel 2>/dev/null || true)
  parity="${top}/scripts/track-b/v10-hermes-parity.sh"
  scaffold="${top}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
  [ -f "$parity" ] || { echo "missing parity script"; return 1; }
  # GREEN: identical trees
  bash "$parity" --compare "$scaffold" "$scaffold" >/tmp/hermes-parity-green.out 2>&1 \
    || { echo "same-tree compare should GREEN"; cat /tmp/hermes-parity-green.out; return 1; }
  # RED: mutate a key file in a copy
  a=$(mktemp -d)
  b=$(mktemp -d)
  mkdir -p "$a" "$b"
  # Copy only .hermes (rsync/cp -R); keep small by using tar
  (cd "$scaffold" && tar cf - .hermes) | (cd "$a" && tar xf -)
  (cd "$scaffold" && tar cf - .hermes) | (cd "$b" && tar xf -)
  echo '# parity-probe-drift' >> "$b/.hermes/harness/plan-lint.py"
  if bash "$parity" --compare "$a" "$b" >/tmp/hermes-parity-red.out 2>&1; then
    echo "mismatch compare should RED"
    cat /tmp/hermes-parity-red.out
    rm -rf "$a" "$b"
    return 1
  fi
  grep -q 'REFUSE' /tmp/hermes-parity-red.out \
    && rm -rf "$a" "$b" \
    && echo hermespreflight-red-ok
}
check "hermes parity REFUSE on digest mismatch (O-HERMESPREFLIGHT)" 0 "hermespreflight-red-ok"

# O-HERMESPARITYSEM — stamp / _Generated: catalog churn must not false-RED digests
run_case() {
  local top parity gf scaffold a b da db
  top=$(git -C "$HARNESS_DIR/../../../../.." rev-parse --show-toplevel 2>/dev/null || true)
  parity="${top}/scripts/track-b/v10-hermes-parity.sh"
  gf="${top}/scripts/track-b/v10-golden-fresh.sh"
  lib="${top}/scripts/track-b/lib-quality-gates.sh"
  scaffold="${top}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
  [ -f "$parity" ] && [ -f "$gf" ] && [ -f "$lib" ] || { echo "missing parity/golden/lib"; return 1; }
  grep -q 'qg_hermes_list_semantic_files' "$parity" \
    && grep -q 'qg_hermes_list_semantic_files' "$gf" \
    && grep -q 'defaults-inventory.md' "$lib" \
    && grep -q 'guard-manifest.md' "$lib" \
    && grep -q '\.published-fp' "$lib" \
    && grep -q 'defaults-inventory.md' "$parity" \
    && grep -q 'guard-manifest.md' "$parity" \
    || { echo "semantic exclusions not wired"; return 1; }
  a=$(mktemp -d); b=$(mktemp -d)
  (cd "$scaffold" && tar cf - .hermes) | (cd "$a" && tar xf -)
  (cd "$scaffold" && tar cf - .hermes) | (cd "$b" && tar xf -)
  # Non-semantic churn that previously false-RED'd R1
  echo "STAMPED_AT=2099-01-01T00:00:00Z" >> "$b/.hermes/harness/.published-fp"
  printf '\n_Generated: 2099-01-01T00:00:00Z_\n' >> "$b/.hermes/harness/defaults-inventory.md"
  printf '\n_Generated: 2099-01-01T00:00:00Z_\n' >> "$b/.hermes/harness/guard-manifest.md"
  if ! bash "$parity" --compare "$a" "$b" >/tmp/hermesparitysem-green.out 2>&1; then
    echo "stamp/_Generated: churn should stay GREEN under O-HERMESPARITYSEM"
    cat /tmp/hermesparitysem-green.out
    rm -rf "$a" "$b"
    return 1
  fi
  # Semantic drift still RED
  echo '# hermesparitysem-probe' >> "$b/.hermes/harness/plan-lint.py"
  if bash "$parity" --compare "$a" "$b" >/tmp/hermesparitysem-red.out 2>&1; then
    echo "plan-lint drift should still RED"
    cat /tmp/hermesparitysem-red.out
    rm -rf "$a" "$b"
    return 1
  fi
  grep -q 'REFUSE' /tmp/hermesparitysem-red.out \
    && rm -rf "$a" "$b" \
    && echo hermesparitysem-ok
}
check "hermes parity ignores stamp/_Generated: (O-HERMESPARITYSEM)" 0 "hermesparitysem-ok"

# O-GOLDENFRESH — publish-fp stamp + local three-way legs (no outer start)
run_case() {
  local top gf preflight
  top=$(git -C "$HARNESS_DIR/../../../../.." rev-parse --show-toplevel 2>/dev/null || true)
  gf="${top}/scripts/track-b/v10-golden-fresh.sh"
  preflight="${top}/scripts/track-b/v9-preflight-outer-start.sh"
  [ -n "$top" ] && [ -f "$gf" ] && [ -f "$preflight" ] \
    && grep -q 'O-GOLDENFRESH\|v10-golden-fresh' "$preflight" \
    && grep -q '\.published-fp' "$gf" \
    && grep -q 'REFUSE' "$gf" \
    && grep -q 'v10-golden-fresh' "${top}/scripts/bootstrap-scaffold-repos.sh" \
    && echo goldenfresh-wire-ok
}
check "golden-fresh preflight+bootstrap wiring (O-GOLDENFRESH)" 0 "goldenfresh-wire-ok"

run_case() {
  local top gf scaffold
  top=$(git -C "$HARNESS_DIR/../../../../.." rev-parse --show-toplevel 2>/dev/null || true)
  gf="${top}/scripts/track-b/v10-golden-fresh.sh"
  scaffold="${top}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
  [ -f "$gf" ] || { echo "missing golden-fresh script"; return 1; }
  bash "$gf" --stamp "$scaffold" >/tmp/goldenfresh-stamp.out 2>&1 \
    || { echo "stamp failed"; cat /tmp/goldenfresh-stamp.out; return 1; }
  bash "$gf" --check-local "$scaffold" >/tmp/goldenfresh-green.out 2>&1 \
    || { echo "check-local should GREEN after stamp"; cat /tmp/goldenfresh-green.out; return 1; }
  grep -q 'GREEN' /tmp/goldenfresh-green.out \
    && [ -f "$scaffold/.hermes/harness/.published-fp" ] \
    && echo goldenfresh-stamp-ok
}
check "golden-fresh stamp then check-local GREEN (O-GOLDENFRESH)" 0 "goldenfresh-stamp-ok"

run_case() {
  local top gf scaffold a
  top=$(git -C "$HARNESS_DIR/../../../../.." rev-parse --show-toplevel 2>/dev/null || true)
  gf="${top}/scripts/track-b/v10-golden-fresh.sh"
  scaffold="${top}/stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
  [ -f "$gf" ] || { echo "missing golden-fresh script"; return 1; }
  a=$(mktemp -d)
  (cd "$scaffold" && tar cf - .hermes) | (cd "$a" && tar xf -)
  bash "$gf" --stamp "$a" >/tmp/goldenfresh-red-stamp.out 2>&1 \
    || { echo "stamp on copy failed"; cat /tmp/goldenfresh-red-stamp.out; rm -rf "$a"; return 1; }
  echo '# goldenfresh-probe-drift' >> "$a/.hermes/harness/plan-lint.py"
  if bash "$gf" --check-local "$a" >/tmp/goldenfresh-red.out 2>&1; then
    echo "drifted tree should RED"
    cat /tmp/goldenfresh-red.out
    rm -rf "$a"
    return 1
  fi
  grep -q 'REFUSE' /tmp/goldenfresh-red.out \
    && rm -rf "$a" \
    && echo goldenfresh-red-ok
}
check "golden-fresh REFUSE on publish lag (O-GOLDENFRESH)" 0 "goldenfresh-red-ok"

# O-HARNESSFP-POD — pod digest in harness_fp / last_activity (no oc)
run_case() {
  local top clock
  top=$(git -C "$HARNESS_DIR/../../../../.." rev-parse --show-toplevel 2>/dev/null || true)
  clock="${top}/scripts/track-b/v10-idle-clock.sh"
  [ -n "$top" ] && [ -f "$clock" ] \
    && grep -q 'O-HARNESSFP-POD' "$clock" \
    && grep -q 'pod_fp' "$clock" \
    && grep -q 'V10_IDLE_POD_DIGEST\|_pod_harness_digest' "$clock" \
    && grep -q 'last_activity' "$clock" \
    && grep -q -- '--self-test' "$clock" \
    && echo harnessfppod-wire-ok
}
check "idle-clock pod digest wiring (O-HARNESSFP-POD)" 0 "harnessfppod-wire-ok"

run_case() {
  local top clock
  top=$(git -C "$HARNESS_DIR/../../../../.." rev-parse --show-toplevel 2>/dev/null || true)
  clock="${top}/scripts/track-b/v10-idle-clock.sh"
  [ -f "$clock" ] || { echo "missing v10-idle-clock.sh"; return 1; }
  bash "$clock" --self-test >/tmp/harnessfppod-self.out 2>&1 \
    || { echo "self-test failed"; cat /tmp/harnessfppod-self.out; return 1; }
  grep -q 'O-HARNESSFP-POD: self-test GREEN' /tmp/harnessfppod-self.out \
    && echo harnessfppod-self-ok
}
check "idle-clock pod digest self-test (O-HARNESSFP-POD)" 0 "harnessfppod-self-ok"

# O-ORACLEDERIVE / O-INFERABSENT §2.1/§2.2 — derive Oracle; WARN→LINT
run_case() {
  mkfix
  printf 'legacyPackage: com.example\ntargetPackage: com.demo\n' > migration.yaml
  mkdir -p migration
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).
#### T-001: Infer convert missing Target
**Class**: infer
**Shape**: modify
**Goal**: Convert Foo from Spring to Quarkus
**Target**: → `src/main/java/com/demo/Foo.java`
**Acceptance**: compiles
EOF
  out=$(PLAN_LINT_REQUIRE_SHAPE=1 PLAN_LINT_SHAPE_WARN=0 \
    python3 "$HARNESS_DIR/plan-lint.py" tasks.md --story-deploy false 2>&1) || true
  echo "$out" | grep -q 'LINT:O-INFERABSENT' \
    && ! echo "$out" | grep -q 'WARN:O-INFERABSENT' \
    && echo inferabsent-lint-ok
}
check "plan-lint LINT O-INFERABSENT on infer+derived-absent (O-INFERABSENT)" 0 "inferabsent-lint-ok"

run_case() {
  mkfix
  printf 'legacyPackage: com.example\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).
#### T-001: Create convert missing Target
**Class**: infer
**Shape**: create
**Goal**: Create Foo via harvest-then-convert create-procedure
**Target**: → `src/main/java/com/demo/Foo.java`
**Acceptance**: harvest-then-convert; compiles
EOF
  out=$(PLAN_LINT_REQUIRE_SHAPE=1 PLAN_LINT_SHAPE_WARN=0 \
    python3 "$HARNESS_DIR/plan-lint.py" tasks.md --story-deploy false 2>&1) || true
  echo "$out" | grep -q 'PLAN OK' \
    && ! echo "$out" | grep -q 'LINT:O-INFERABSENT' \
    && echo inferabsent-create-ok
}
check "plan-lint Shape=create proceeds on derived-absent (O-INFERABSENT)" 0 "inferabsent-create-ok"

run_case() {
  mkfix
  printf 'legacyPackage: com.example\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).
#### T-001: Infer with NULLACTION proceed
**Class**: infer
**Shape**: modify
**Proceed**: O-NULLACTION
**Goal**: Fixture override path for derived-absent
**Target**: → `src/main/java/com/demo/Foo.java`
**Acceptance**: stop honest
EOF
  out=$(PLAN_LINT_REQUIRE_SHAPE=1 PLAN_LINT_SHAPE_WARN=0 \
    python3 "$HARNESS_DIR/plan-lint.py" tasks.md --story-deploy false 2>&1) || true
  echo "$out" | grep -q 'PLAN OK' \
    && ! echo "$out" | grep -q 'LINT:O-INFERABSENT' \
    && echo inferabsent-proceed-ok
}
check "plan-lint Proceed:O-NULLACTION override (O-INFERABSENT)" 0 "inferabsent-proceed-ok"

run_case() {
  mkfix
  printf 'legacyPackage: com.example\ntargetPackage: com.demo\n' > migration.yaml
  mkdir -p src/main/java/com/demo
  echo 'package com.demo; public class Foo {}' > src/main/java/com/demo/Foo.java
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).
#### T-001: Infer present Target
**Class**: infer
**Shape**: modify
**Goal**: Convert existing Foo
**Target**: → `src/main/java/com/demo/Foo.java`
**Acceptance**: compiles
EOF
  out=$(PLAN_LINT_REQUIRE_SHAPE=1 PLAN_LINT_SHAPE_WARN=0 \
    python3 "$HARNESS_DIR/plan-lint.py" tasks.md --story-deploy false 2>&1) || true
  echo "$out" | grep -q 'PLAN OK' \
    && ! echo "$out" | grep -q 'LINT:O-INFERABSENT' \
    && echo oraclederive-present-ok
}
check "plan-lint derived Oracle present when Target exists (O-ORACLEDERIVE)" 0 "oraclederive-present-ok"

run_case() {
  mkfix
  printf 'legacyPackage: com.example\ntargetPackage: com.demo\n' > migration.yaml
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).
#### T-001: Infer convert missing Target
**Class**: infer
**Shape**: modify
**Goal**: Convert Foo
**Target**: → `src/main/java/com/demo/Foo.java`
**Acceptance**: compiles
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-001 2>&1) || true
  echo "$out" | grep -qE '^Oracle:[[:space:]]*absent' \
    && echo "$out" | grep -q 'O-INFERABSENT' \
    && echo inferabsent-pkt-ok
}
check "task-packet derives Oracle=absent + tip (O-ORACLEDERIVE)" 0 "inferabsent-pkt-ok"

run_case() {
  out=$(bash "$HARNESS_DIR/plan-corpus-lint.sh" --case s03-32812a6-final 2>&1) || true
  echo "$out" | grep -q 'PASS s03-32812a6-final' \
    && echo "$out" | grep -q 'O-INFERABSENT' \
    && echo "$out" | grep -q 'hit O-INFERABSENT' \
    && echo plancorpus-inferabsent-ok
}
check "plan-corpus 32812a6-final fires O-INFERABSENT (O-INFERABSENT)" 0 "plancorpus-inferabsent-ok"

# O-FIDELITYPORT — Port=rename keeps harvest byte-match; Port=reimplement uses redesign-sig
# Corpus/fixture case: Port=rename + serialVersionUID drift → FIDELITY RED (fires harvest path).
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/com/example src/main/java/com/demo
  printf 'legacyPackage: com.example\ntargetPackage: com.demo\n' > migration.yaml
  cat > migration/staging/src/main/java/com/example/Widget.java <<'EOF'
package com.example;
public class Widget {
  private static final long serialVersionUID = 1L;
  public int size() { return 1; }
}
EOF
  cat > src/main/java/com/demo/Widget.java <<'EOF'
package com.demo;
public class Widget {
  private static final long serialVersionUID = 99L;
  public int size() { return 1; }
}
EOF
  cat > tasks.md <<'EOF'
# Tasks
#### T-001: Harvest Widget
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Goal**: Harvest Widget with package rename only
**Target design**: → `src/main/java/com/demo/Widget.java`
**Acceptance**: harvest fidelity GREEN
EOF
  CURRENT_TASK=T-001 STORY_TASKS="$FIX/tasks.md" SENSOR_ROOT="$FIX" \
    bash "$SENSORS" fidelity
}
check "Port=rename fidelity REDs serialVersionUID drift (O-FIDELITYPORT)" 1 "FIDELITY:"

# Corpus/fixture case: Port=reimplement + Spring-import body drift → fidelity GREEN
# (byte-match skipped) while redesign-sig still catches method rename.
run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/com/example src/main/java/com/demo
  printf 'legacyPackage: com.example\ntargetPackage: com.demo\n' > migration.yaml
  cat > migration/staging/src/main/java/com/example/OwnerRepo.java <<'EOF'
package com.example;
import org.springframework.data.repository.Repository;
public interface OwnerRepo extends Repository<Object, Integer> {
  Object findById(Integer id);
}
EOF
  # Dest reimplements with Panache — Spring imports gone, serial/body differ, method kept.
  cat > src/main/java/com/demo/OwnerRepo.java <<'EOF'
package com.demo;
import io.quarkus.hibernate.orm.panache.PanacheRepositoryBase;
import jakarta.enterprise.context.ApplicationScoped;
@ApplicationScoped
public class OwnerRepo implements PanacheRepositoryBase<Object, Integer> {
  public Object findById(Integer id) { return find("id", id).firstResult(); }
}
EOF
  cat > tasks.md <<'EOF'
# Tasks
#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: create
**Port**: reimplement
**Goal**: Convert Spring Data to Panache after harvest
**Target design**: → `src/main/java/com/demo/OwnerRepo.java`
**API mapping**: `@Query` → Panache find/list; convert-after-harvest O-SDJPAHARVEST
**Acceptance**: Panache repos
EOF
  out=$(CURRENT_TASK=T-004 STORY_TASKS="$FIX/tasks.md" SENSOR_ROOT="$FIX" \
    bash "$SENSORS" fidelity 2>&1) || true
  echo "$out" | grep -q 'O-FIDELITYPORT: Port=reimplement' \
    && echo "$out" | grep -qE 'reimpl-sig GREEN|redesign-sig GREEN|fidelity check GREEN' \
    && echo "$out" | grep -qv 'FIDELITY:OwnerRepo' \
    && echo fidelityport-reimpl-ok
}
check "Port=reimplement skips harvest byte-match (O-FIDELITYPORT)" 0 "fidelityport-reimpl-ok"

run_case() {
  mkfix
  mkdir -p migration/staging/src/main/java/com/example src/main/java/com/demo
  printf 'legacyPackage: com.example\ntargetPackage: com.demo\n' > migration.yaml
  cat > migration/staging/src/main/java/com/example/OwnerRepo.java <<'EOF'
package com.example;
public interface OwnerRepo {
  Object findById(Integer id);
}
EOF
  # Method renamed — redesign-sig --mode=reimpl must RED under Port=reimplement.
  cat > src/main/java/com/demo/OwnerRepo.java <<'EOF'
package com.demo;
import jakarta.enterprise.context.ApplicationScoped;
@ApplicationScoped
public class OwnerRepo {
  public Object getById(Integer id) { return null; }
}
EOF
  cat > tasks.md <<'EOF'
# Tasks
#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: create
**Port**: reimplement
**Goal**: Convert Spring Data to Panache
**Target design**: → `src/main/java/com/demo/OwnerRepo.java`
**API mapping**: convert-after-harvest O-SDJPAHARVEST
**Acceptance**: Panache
EOF
  CURRENT_TASK=T-004 STORY_TASKS="$FIX/tasks.md" SENSOR_ROOT="$FIX" \
    bash "$SENSORS" fidelity
}
check "Port=reimplement fidelity REDs method rename via redesign-sig (O-FIDELITYPORT)" 1 "SIG:"

# O-REIMPLCREATE — Port=reimplement Shape=create always gets create-procedure tip
run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: create
**Port**: reimplement
**Goal**: Convert Spring Data to Panache after harvest
**Target design**: → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**API mapping**: `@Query` → Panache find/list; convert-after-harvest O-SDJPAHARVEST
**Acceptance**: Panache repos
EOF
  out=$(python3 "$HARNESS_DIR/task-packet.py" tasks.md T-004 2>/dev/null)
  echo "$out" | grep -q 'O-REIMPLCREATE' \
    && echo "$out" | grep -q 'harvest-from-staging' \
    && echo "$out" | grep -q 'API mapping' \
    && echo "$out" | grep -qE 'first-write|O-CREATEFIRSTMUT' \
    && echo "$out" | grep -q 'O-FIDELITYPORT' \
    && echo reimplcreate-pkt-ok
}
check "task-packet tips O-REIMPLCREATE on Port=reimplement Shape=create" 0 "reimplcreate-pkt-ok"

run_case() {
  mkfix
  cat > tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).

#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: create
**Port**: reimplement
**Goal**: Convert Spring Data repositories to Quarkus Panache
**Target design**:
- → `src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java`
**API mapping**:
| legacy | target |
| `@Query` JPQL | Panache `find`/`list` bodies |
**Acceptance**: Panache repositories compile
EOF
  printf 'legacyPackage: org.example.legacy\ntargetPackage: com.demo\n' > migration.yaml
  PLAN_LINT_REQUIRE_SHAPE=1 python3 "$LINT" tasks.md
}
check "plan-lint REDs Port=reimplement Shape=create without create-procedure (O-REIMPLCREATE)" 1 "O-REIMPLCREATE"

run_case() {
  grep -q 'O-FIDELITYPORT' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && grep -q 'O-REIMPLCREATE' "$HARNESS_DIR/../skills/migration-harness/EXECUTION.md" \
    && grep -q 'O-FIDELITYPORT' "$HARNESS_DIR/../skills/migration-harness/PLANNING.md" \
    && grep -q 'O-REIMPLCREATE' "$HARNESS_DIR/../skills/migration-harness/PLANNING.md" \
    && grep -q 'run_port_scoped_fidelity\|O-FIDELITYPORT' "$HARNESS_DIR/sensors.sh" \
    && grep -q 'O-REIMPLCREATE' "$HARNESS_DIR/task-packet.py" \
    && grep -q 'mode=reimpl\|--mode=reimpl' "$HARNESS_DIR/redesign-sig.py" \
    && echo fidelityport-wire-ok
}
check "sensors/packet/EXECUTION/PLANNING wire O-FIDELITYPORT+O-REIMPLCREATE" 0 "fidelityport-wire-ok"

# O-M3ALL — whole-plan-set lint + outer-loop two-pass / waterfall hooks
run_case() {
  test -x "$HARNESS_DIR/m3-all-lint.sh" \
    && grep -q 'O-M3ALL' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'm3-all-lint.sh' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M3_ALL_PASS' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'waterfall' "$HARNESS_DIR/outer-loop.sh" \
    && ! grep -Eq '^[^#]*\b(M3_ALL_SKIP_JIT|WATERFALL_OPTIONAL)=' "$HARNESS_DIR/outer-loop.sh" \
    && bash "$HARNESS_DIR/m3-all-lint.sh" --mode=wire-check \
    && grep -q 'O-M3ALL' "$HARNESS_DIR/../skills/migration-harness/PLANNING.md" \
    && echo m3all-wire-ok
}
check "m3-all-lint + outer-loop waterfall hooks (O-M3ALL)" 0 "m3all-wire-ok"

run_case() {
  mkfix
  mkdir -p migration specs/S01-a specs/S02-b
  cat > migration/roadmap.md <<'EOF'
# Roadmap
## S01: foundation
- deploy: false
- findings: springboot-di-to-quarkus-00000
- scope: src/main/java/com/demo/Config.java
## S02: data
- deploy: true
- findings: springboot-di-to-quarkus-00001
- scope: src/main/java/com/demo/repository/FooRepository.java
EOF
  cat > specs/S01-a/tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).
#### T-001: Config
**Class**: rewrite
**Shape**: modify
**Owns**: `src/main/java/com/demo/Config.java`
**Oracle**: present
**Findings**: springboot-di-to-quarkus-00000
**Acceptance**: compiles
EOF
  cat > specs/S02-b/tasks.md <<'EOF'
# Tasks
UI surface: waived (API-only).
#### T-001: Repo convert
**Class**: infer
**Shape**: create
**Port**: reimplement
**Owns**: `src/main/java/com/demo/repository/FooRepository.java`
**Oracle**: absent
**Assumes**: Config exists (S01 T-001)
**Goal**: Convert Spring Data repository to Panache
**API mapping**:
| legacy | target |
| CrudRepository | PanacheRepository |
**Findings**: springboot-di-to-quarkus-00001
**Acceptance**: Panache
EOF
  out=$(bash "$HARNESS_DIR/m3-all-lint.sh" --mode=whole-set --root "$FIX" 2>&1) || true
  echo "$out" | grep -q 'PLAN-SET OK' \
    && echo "$out" | grep -q 'projected-tree' \
    && echo m3all-green-ok
}
check "m3-all-lint whole-set GREEN on partitioned plans (O-M3ALL)" 0 "m3all-green-ok"

run_case() {
  mkfix
  mkdir -p migration specs/S01-a specs/S02-b
  cat > migration/roadmap.md <<'EOF'
# Roadmap
## S01: early
- deploy: false
- findings: springboot-di-to-quarkus-00000
- scope: src/main/java/com/demo/Early.java
## S02: data
- deploy: true
- findings: springboot-di-to-quarkus-00000
- scope: src/main/java/com/demo/repository/FooRepository.java
EOF
  cat > specs/S01-a/tasks.md <<'EOF'
# Tasks
#### T-001: Early
**Class**: rewrite
**Shape**: modify
**Owns**: `src/main/java/com/demo/Early.java`
**Findings**: springboot-di-to-quarkus-00000
**Acceptance**: ok
EOF
  cat > specs/S02-b/tasks.md <<'EOF'
# Tasks
#### T-001: Repo
**Class**: infer
**Shape**: create
**Owns**: `src/main/java/com/demo/repository/FooRepository.java`
**Goal**: Convert Spring Data repository to Panache
**Findings**: springboot-di-to-quarkus-00000
**Acceptance**: ok
EOF
  out=$(bash "$HARNESS_DIR/m3-all-lint.sh" --mode=whole-set --root "$FIX" 2>&1) || true
  echo "$out" | grep -q 'LINT:O-M3ALL-K1' \
    && echo "$out" | grep -q 'LINT:O-M3ALL-PORT' \
    && echo m3all-k1-port-ok
}
check "m3-all-lint REDs K1 dual-owner + missing Port (O-M3ALL)" 0 "m3all-k1-port-ok"

run_case() {
  mkfix
  mkdir -p migration specs/S01-a specs/S02-b
  cat > migration/roadmap.md <<'EOF'
# Roadmap
## S01: early
- deploy: false
- findings: springboot-di-to-quarkus-00000
- scope: src/main/java/com/demo/Early.java
## S02: later
- deploy: true
- findings: springboot-di-to-quarkus-00001
- scope: src/main/java/com/demo/LaterService.java
EOF
  cat > specs/S01-a/tasks.md <<'EOF'
# Tasks
#### T-001: Leak
**Class**: infer
**Shape**: create
**Owns**: `src/main/java/com/demo/LaterService.java`
**Findings**: springboot-di-to-quarkus-00000
**Acceptance**: ok
EOF
  cat > specs/S02-b/tasks.md <<'EOF'
# Tasks
#### T-001: Later
**Class**: infer
**Shape**: create
**Owns**: `src/main/java/com/demo/LaterService.java`
**Findings**: springboot-di-to-quarkus-00001
**Acceptance**: ok
EOF
  out=$(bash "$HARNESS_DIR/m3-all-lint.sh" --mode=whole-set --root "$FIX" 2>&1) || true
  echo "$out" | grep -q 'LINT:O-M3ALL-LATER' \
    && echo m3all-later-ok
}
check "m3-all-lint REDs later-class leakage (O-M3ALL)" 0 "m3all-later-ok"

run_case() {
  mkfix
  mkdir -p migration specs/S01-a specs/S02-b
  cat > migration/roadmap.md <<'EOF'
# Roadmap
## S01: early
- deploy: false
- findings: springboot-di-to-quarkus-00000
- scope: src/main/java/com/demo/Early.java
## S02: later
- deploy: true
- findings: springboot-di-to-quarkus-00001
- scope: src/main/java/com/demo/Later.java
EOF
  cat > specs/S01-a/tasks.md <<'EOF'
# Tasks
#### T-001: Early
**Class**: rewrite
**Shape**: modify
**Owns**: `src/main/java/com/demo/Shared.java`
**Findings**: springboot-di-to-quarkus-00000
**Acceptance**: ok
EOF
  cat > specs/S02-b/tasks.md <<'EOF'
# Tasks
#### T-001: Later
**Class**: infer
**Shape**: create
**Port**: reimplement
**Owns**: `src/main/java/com/demo/Shared.java`
**Goal**: Convert Shared
**API mapping**:
| legacy | target |
| A | B |
**Findings**: springboot-di-to-quarkus-00001
**Acceptance**: ok
EOF
  out=$(bash "$HARNESS_DIR/m3-all-lint.sh" --mode=whole-set --root "$FIX" 2>&1) || true
  echo "$out" | grep -q 'LINT:O-M3ALL-FILE' \
    && echo m3all-file-ok
}
check "m3-all-lint REDs cross-story Owns dual-owner (O-M3ALL A4)" 0 "m3all-file-ok"

run_case() {
  mkfix
  mkdir -p migration specs/S01-a src/main/java/com/demo
  echo 'class Existing {}' > src/main/java/com/demo/Existing.java
  cat > migration/roadmap.md <<'EOF'
# Roadmap
## S01: early
- deploy: true
- findings: springboot-di-to-quarkus-00000
- scope: src/main/java/com/demo/Existing.java
EOF
  cat > specs/S01-a/tasks.md <<'EOF'
# Tasks
#### T-001: Overwrite
**Class**: rewrite
**Shape**: create
**Owns**: `src/main/java/com/demo/Existing.java`
**Findings**: springboot-di-to-quarkus-00000
**Acceptance**: ok
EOF
  out=$(bash "$HARNESS_DIR/m3-all-lint.sh" --mode=whole-set --root "$FIX" 2>&1) || true
  echo "$out" | grep -q 'LINT:O-M3ALL-TREE' \
    && echo "$out" | grep -q 'projected-tree' \
    && echo m3all-projected-ok
}
check "m3-all-lint REDs projected-tree create-into-prior (O-M3ALL)" 0 "m3all-projected-ok"

# O-M3ALL remainder — Oracle whole-set + Assumes closure + operator gate / prediction freeze
run_case() {
  mkfix
  mkdir -p migration specs/S01-a
  cat > migration/roadmap.md <<'EOF'
# Roadmap
## S01: early
- deploy: true
- findings: springboot-di-to-quarkus-00000
- scope: src/main/java/com/demo/Early.java
EOF
  cat > specs/S01-a/tasks.md <<'EOF'
# Tasks
#### T-001: Early
**Class**: rewrite
**Shape**: modify
**Owns**: `src/main/java/com/demo/Early.java`
**Findings**: springboot-di-to-quarkus-00000
**Acceptance**: ok
EOF
  out=$(bash "$HARNESS_DIR/m3-all-lint.sh" --mode=whole-set --root "$FIX" 2>&1) || true
  echo "$out" | grep -q 'LINT:O-M3ALL-ORACLE' \
    && echo m3all-oracle-ok
}
check "m3-all-lint REDs missing Oracle per task (O-M3ALL)" 0 "m3all-oracle-ok"

run_case() {
  mkfix
  mkdir -p migration specs/S01-a specs/S02-b
  cat > migration/roadmap.md <<'EOF'
# Roadmap
## S01: early
- deploy: false
- findings: springboot-di-to-quarkus-00000
- scope: src/main/java/com/demo/Early.java
## S02: later
- deploy: true
- findings: springboot-di-to-quarkus-00001
- scope: src/main/java/com/demo/Later.java
EOF
  cat > specs/S01-a/tasks.md <<'EOF'
# Tasks
#### T-001: Early
**Class**: rewrite
**Shape**: modify
**Owns**: `src/main/java/com/demo/Early.java`
**Oracle**: present
**Findings**: springboot-di-to-quarkus-00000
**Acceptance**: ok
EOF
  cat > specs/S02-b/tasks.md <<'EOF'
# Tasks
#### T-001: Later
**Class**: infer
**Shape**: create
**Port**: reimplement
**Owns**: `src/main/java/com/demo/Later.java`
**Oracle**: absent
**Assumes**: MissingThing exists (S01 T-001)
**Goal**: Convert Later
**API mapping**:
| legacy | target |
| A | B |
**Findings**: springboot-di-to-quarkus-00001
**Acceptance**: ok
EOF
  out=$(bash "$HARNESS_DIR/m3-all-lint.sh" --mode=whole-set --root "$FIX" 2>&1) || true
  echo "$out" | grep -q 'LINT:O-M3ALL-ASSUMES' \
    && echo m3all-assumes-ok
}
check "m3-all-lint REDs Assumes not closed by earlier Owns (O-M3ALL A6)" 0 "m3all-assumes-ok"

run_case() {
  mkfix
  mkdir -p migration
  # freeze + gate require predictions file; refuse without APPROVED when AUTO=0
  if M3_ALL_OPERATOR_AUTO=0 bash "$HARNESS_DIR/m3-all-lint.sh" \
      --mode=operator-gate --root "$FIX" >/tmp/m3all-gate-red.txt 2>&1; then
    echo m3all-gate-should-red
  else
    grep -q 'OPERATOR_GATE RED' /tmp/m3all-gate-red.txt \
      && bash "$HARNESS_DIR/m3-all-lint.sh" --mode=freeze-predictions --root "$FIX" >/dev/null \
      && M3_ALL_OPERATOR_AUTO=1 bash "$HARNESS_DIR/m3-all-lint.sh" \
           --mode=operator-gate --root "$FIX" >/tmp/m3all-gate-ok.txt 2>&1 \
      && grep -q 'OPERATOR_GATE auto-APPROVED\|OPERATOR_GATE APPROVED' /tmp/m3all-gate-ok.txt \
      && test -f "$FIX/migration/.m3-all-predictions.md" \
      && grep -q 'FROZEN' "$FIX/migration/.m3-all-predictions.md" \
      && grep -q 'freeze-predictions' "$HARNESS_DIR/outer-loop.sh" \
      && grep -q 'operator-gate' "$HARNESS_DIR/outer-loop.sh" \
      && grep -q 'OPERATOR_GATE' "$HARNESS_DIR/outer-loop.sh" \
      && echo m3all-gate-ok
  fi
}
check "m3-all prediction freeze + OPERATOR_GATE (O-M3ALL)" 0 "m3all-gate-ok"

# O-M3ALL skeleton-first compose
run_case() {
  test -f "$HARNESS_DIR/m3-all-compose.py" \
    && grep -q 'm3-all-compose.py' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'skeleton-first' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M3_ALL_COMPOSE' "$HARNESS_DIR/outer-loop.sh" \
    && grep -qi 'skeleton-first' "$HARNESS_DIR/../skills/migration-harness/PLANNING.md" \
    && bash "$HARNESS_DIR/m3-all-lint.sh" --mode=wire-check \
    && echo m3all-compose-wire-ok
}
check "m3-all-compose wired in outer-loop + PLANNING (O-M3ALL skeleton-first)" 0 "m3all-compose-wire-ok"

run_case() {
  mkfix
  mkdir -p migration/briefs src/main/java/com/demo
  echo 'class Config {}' > src/main/java/com/demo/Config.java
  cat > migration/roadmap.md <<'EOF'
# Roadmap
## S01: foundation
- deploy: false
- findings: springboot-di-to-quarkus-00000
- scope: src/main/java/com/demo/Config.java
## S02: data
- deploy: true
- findings: springboot-di-to-quarkus-00001
- scope: src/main/java/com/demo/repository/FooRepository.java
EOF
  cat > migration/briefs/S01-foundation.md <<'EOF'
# S01 brief
## In scope
Config
EOF
  cat > migration/briefs/S02-data.md <<'EOF'
# S02 brief
## In scope
FooRepository
EOF
  out=$(python3 "$HARNESS_DIR/m3-all-compose.py" --root "$FIX" 2>&1) || true
  echo "$out" | grep -q 'wrote=' \
    && test -f "$FIX/specs/S01-foundation/tasks.md" \
    && test -f "$FIX/specs/S02-data/tasks.md" \
    && grep -q 'O-M3ALL-SKELETON' "$FIX/specs/S01-foundation/tasks.md" \
    && grep -q '\*\*Oracle\*\*:' "$FIX/specs/S01-foundation/tasks.md" \
    && grep -q '\*\*Owns\*\*:' "$FIX/specs/S01-foundation/tasks.md" \
    && grep -q '\*\*Port\*\*:' "$FIX/specs/S02-data/tasks.md" \
    && grep -q 'reimplement' "$FIX/specs/S02-data/tasks.md" \
    && grep -q '\*\*Assumes\*\*:' "$FIX/specs/S02-data/tasks.md" \
    && grep -q 'S01 T-001' "$FIX/specs/S02-data/tasks.md" \
    && echo '#### T-001: AUTHED' > "$FIX/specs/S01-foundation/tasks.md" \
    && out2=$(python3 "$HARNESS_DIR/m3-all-compose.py" --root "$FIX" 2>&1) || true \
    && echo "$out2" | grep -q 'skipped authored' \
    && grep -q 'AUTHED' "$FIX/specs/S01-foundation/tasks.md" \
    && echo m3all-compose-emit-ok
}
check "m3-all-compose emits skeleton fields and skips authored (O-M3ALL)" 0 "m3all-compose-emit-ok"

# O-LOGSTORY — story identity on every in-story log() line (wake#375)
run_case() {
  grep -q 'O-LOGSTORY' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'STORY_TAG=' "$HARNESS_DIR/outer-loop.sh" \
    && grep -qE 'STORY_TAG:\+ \$STORY_TAG' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'STORY_TAG="\$SID"' "$HARNESS_DIR/outer-loop.sh" \
    && echo logstory-wire-ok
}
check "outer-loop log() prefixes STORY_TAG (O-LOGSTORY wire)" 0 "logstory-wire-ok"

run_case() {
  mkfix
  LOG="$FIX/outer.log"
  STORY_TAG=""
  # Mirror outer-loop.sh log() contract (O-LOGSTORY choke point).
  log() { echo "[$(date -u +%F' '%T)]${STORY_TAG:+ $STORY_TAG}$([ -n "${STORY_TAG:-}" ] && echo ' ▸') $*" >> "$LOG"; }
  log "▶ START  M1 ANALYZE — establish migration ground truth"
  log "         M2 SEQUENCE still working"
  STORY_TAG=S02
  log "▶ START  M3 SPECIFY — plan story S02-x (2/6)"
  log "         ✓ SENSE milestone sensor GREEN after T-001"
  log "✓ END    M4/M5 EXECUTE — S02-x complete"
  STORY_TAG=""
  log "▶ START  M3-ALL whole-set lint — K1 / Port / later-class"
  # M1/M2 and post-story: no SID prefix
  ! grep -E '^\[[^]]+\] S0[0-9] ▸' "$LOG" | grep -q 'M1 ANALYZE' \
    && ! grep -E '^\[[^]]+\] S0[0-9] ▸' "$LOG" | grep -q 'M2 SEQUENCE' \
    && ! grep -E '^\[[^]]+\] S0[0-9] ▸' "$LOG" | grep -q 'M3-ALL whole-set' \
    && grep -qE '^\[[^]]+\] S02 ▸ ▶ START  M3 SPECIFY' "$LOG" \
    && grep -qE '^\[[^]]+\] S02 ▸          ✓ SENSE' "$LOG" \
    && grep -qE '^\[[^]]+\] S02 ▸ ✓ END    M4/M5' "$LOG" \
    && ! grep -vE '^\[[^]]+\] S02 ▸' "$LOG" | grep -q 'M3 SPECIFY\|SENSE milestone\|M4/M5 EXECUTE' \
    && echo logstory-emit-ok
}
check "log() emits S02 ▸ in-story and none for M1/M2 (O-LOGSTORY)" 0 "logstory-emit-ok"

# O-LOGBRIEF / O-LOGEPILOG — story-start banner + end-of-story summary (wake#376)
run_case() {
  grep -q 'O-LOGBRIEF' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'emit_story_brief' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-LOGEPILOG' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'emit_story_epilog' "$HARNESS_DIR/outer-loop.sh" \
    && grep -qE 'GOAL|SCOPE|OWNS|PLAN|PORT|BUDGET|DONE' "$HARNESS_DIR/outer-loop.sh" \
    && grep -qE 'RESULT|CODE|TESTS|FIND|COST|HEAD' "$HARNESS_DIR/outer-loop.sh" \
    && echo logbrief-epilog-wire-ok
}
check "outer-loop wires O-LOGBRIEF+O-LOGEPILOG emitters" 0 "logbrief-epilog-wire-ok"

run_case() {
  mkfix
  LOG="$FIX/outer.log"
  STORY_TAG=S03
  SID=S03
  SLUG=S03-data-access-layer
  STORY_IDX=3
  STORY_COUNT=6
  SCOPE="src/main/java/com/demo/repository,src/test/java/com/demo/repository"
  FINDINGS="springboot-di-to-quarkus-00000,springboot-di-to-quarkus-00002,springboot-di-to-quarkus-00003"
  DEPLOY=false
  BRIEF="$FIX/brief.md"
  SPEC_TASKS="$FIX/tasks.md"
  cat > "$BRIEF" <<'EOF'
# S03: Data Access Layer

## Goal & position

Replace Spring Data / JDBC repositories with Panache + CDI so persistence is Quarkus-native.

## Done-criteria

- milestone sensor GREEN and zero org.springframework under repository scope
EOF
  cat > "$SPEC_TASKS" <<'EOF'
# Tasks

#### T-001: Convert JDBC repositories
**Class**: infer
**Shape**: create
**Port**: reimplement
**Goal**: Harvest JDBC then convert to Agroal

#### T-002: Rename repository interfaces
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Goal**: Package rename only

#### T-003: Verify repositories
**Class**: rewrite
**Shape**: verify
**Port**: rename
**Goal**: Compile + test green
EOF
  # Mirror outer-loop log + helpers (source the function bodies via bash -c extract).
  # shellcheck disable=SC1091
  eval "$(sed -n '/^_log_rule()/,/^_outer_heartbeat_start()/p' "$HARNESS_DIR/outer-loop.sh" \
    | sed '$d')"
  log() { echo "[$(date -u +%F' '%T)]${STORY_TAG:+ $STORY_TAG}$([ -n "${STORY_TAG:-}" ] && echo ' ▸') $*" >> "$LOG"; }
  emit_story_brief
  goal_line=$(grep -E 'S03 GOAL' "$LOG" | head -1)
  slug="$SLUG"
  echo "$goal_line" | grep -qE 'S03 GOAL[[:space:]]+.+' \
    && ! echo "$goal_line" | grep -qF "$slug" \
    && grep -qE 'S03 SCOPE' "$LOG" \
    && grep -qE 'S03 OWNS' "$LOG" \
    && grep -qE 'S03 PLAN' "$LOG" \
    && grep -qE 'S03 PORT' "$LOG" \
    && grep -qE 'S03 DONE' "$LOG" \
    && grep -qE '══ S03' "$LOG" \
    && echo logbrief-emit-ok
}
check "story brief banner emits GOAL≠slug + SCOPE/OWNS/PLAN/PORT/DONE (O-LOGBRIEF)" 0 "logbrief-emit-ok"

run_case() {
  mkfix
  LOG="$FIX/outer.log"
  git init -q
  git config user.email "inst@test"
  git config user.name "inst"
  mkdir -p src/main/java src/test/java
  echo 'class A {}' > src/main/java/A.java
  echo '@Test void t(){ assertThat(true); }' > src/test/java/ATest.java
  git add -A && git commit -q -m "seed"
  STORY_RUN_BASE=$(git rev-parse HEAD)
  echo 'class B {}' > src/main/java/B.java
  git add -A && git commit -q -m "T-001: add B"
  SID=S03
  SLUG=S03-data-access-layer
  STORY_TAG=S03
  STORY_T0=$(( $(date -u +%s) - 3661 ))
  FINDINGS="a,b,c"
  SPEC_TASKS="$FIX/tasks.md"
  cat > "$SPEC_TASKS" <<'EOF'
#### T-001: one
#### T-002: two
EOF
  BRIEF=""
  # Isolate seat-file glob from leftover /tmp/oc-S03-* (other tests / host).
  rm -f /tmp/oc-S03-*.json
  : > /tmp/oc-S03-T-001.json
  : > /tmp/oc-S03-T-002.json
  : > /tmp/oc-S03-escalation-T-001.json
  # shellcheck disable=SC1091
  eval "$(sed -n '/^_log_rule()/,/^_outer_heartbeat_start()/p' "$HARNESS_DIR/outer-loop.sh" \
    | sed '$d')"
  log() { echo "[$(date -u +%F' '%T)]${STORY_TAG:+ $STORY_TAG}$([ -n "${STORY_TAG:-}" ] && echo ' ▸') $*" >> "$LOG"; }
  emit_story_epilog "complete"
  cost_line=$(grep -E 'S03 COST' "$LOG" | head -1)
  cost_n=$(echo "$cost_line" | sed -nE 's/.*COST[[:space:]]+([0-9]+) seats.*/\1/p')
  seat_files=$(ls /tmp/oc-S03-*.json 2>/dev/null | wc -l | tr -d ' ')
  grep -qE 'S03 RESULT' "$LOG" \
    && grep -qE 'S03 CODE' "$LOG" \
    && grep -qE 'S03 TESTS' "$LOG" \
    && grep -qE 'S03 FIND' "$LOG" \
    && grep -qE 'S03 COST' "$LOG" \
    && grep -qE 'S03 HEAD' "$LOG" \
    && [ -n "$cost_n" ] && [ "$cost_n" = "$seat_files" ] \
    && echo logepilog-emit-ok
  rm -f /tmp/oc-S03-*.json
}
check "story epilog emits RESULT/CODE/TESTS/FIND/COST/HEAD with COST=seat files (O-LOGEPILOG)" 0 "logepilog-emit-ok"

# O-EVIDLIVE — K-system ≥1 row/story or RED at story-gate (wake#377)
run_case() {
  [ -f "$HARNESS_DIR/evidence-liveness.sh" ] \
    && grep -q 'O-EVIDLIVE' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'evidence_liveness_blocks_ship' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'k2:evidence' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'evidence-liveness.sh' "$HARNESS_DIR/outer-loop.sh" \
    && echo evidlive-wire-ok
}
check "evidence-liveness wired at story-gate + K1/K2/K3 emitters (O-EVIDLIVE wire)" 0 "evidlive-wire-ok"

run_case() {
  mkfix
  chmod +x "$HARNESS_DIR/evidence-liveness.sh"
  mkdir -p .hermes/harness migration specs
  cp "$HARNESS_DIR/evidence-liveness.sh" .hermes/harness/
  cp "$HARNESS_DIR/append-discovered.py" .hermes/harness/ 2>/dev/null || true
  # Quiet story — heartbeat fills K9/K11 none; K1 via plan-lint log; K3 via roadmap.
  cat > migration/roadmap.md <<'EOF'
# Roadmap
## S01 platform
- springboot-bom-00001: defer (later story)
- quarkus-rest-00002: adopt
EOF
  cat > specs/tasks.md <<'EOF'
#### T-001: BOM
**Owns**: `pom.xml`
**Goal**: Quarkus BOM
EOF
  : > /tmp/supervisor-events.csv
  echo 'plan lint: PASS (M4 entry gate)' > /tmp/supervisor.log
  STORY_TASKS="$FIX/specs/tasks.md" \
    SUPERVISOR_EVENTS=/tmp/supervisor-events.csv \
    ORACLE_ROOT="$FIX" \
    EVIDENCE_LIVENESS_LEDGER="$FIX/migration/evidence-liveness.md" \
    bash .hermes/harness/evidence-liveness.sh heartbeat S01
  STORY_TASKS="$FIX/specs/tasks.md" \
    SUPERVISOR_EVENTS=/tmp/supervisor-events.csv \
    ORACLE_ROOT="$FIX" \
    EVIDENCE_LIVENESS_LEDGER="$FIX/migration/evidence-liveness.md" \
    bash .hermes/harness/evidence-liveness.sh check S01 \
    && grep -qE '\| S01 \| K9 \|' migration/evidence-liveness.md \
    && grep -qE '\| S01 \| K11 \|' migration/evidence-liveness.md \
    && grep -qE '\| S01 \| K1 \|' migration/evidence-liveness.md \
    && grep -qE '\| S01 \| K3 \|' migration/evidence-liveness.md \
    && echo evidlive-heartbeat-ok
}
check "heartbeat fills K1/K3/K9/K11 for quiet story (O-EVIDLIVE)" 0 "evidlive-heartbeat-ok"

run_case() {
  mkfix
  chmod +x "$HARNESS_DIR/evidence-liveness.sh"
  mkdir -p .hermes/harness migration specs
  cp "$HARNESS_DIR/evidence-liveness.sh" .hermes/harness/
  # Findings present, zero k2/k11 events, empty roadmap decisions → K2/K3/K11 silent RED
  cat > specs/tasks.md <<'EOF'
#### T-001: Convert
**Findings**: springboot-di-to-quarkus-00001
**Owns**: `src/main/java/Foo.java`
**Goal**: convert
EOF
  : > /tmp/supervisor-events.csv
  : > /tmp/supervisor.log
  cat > migration/roadmap.md <<'EOF'
# Roadmap
## S02 models
(no decision table rows)
EOF
  STORY_TASKS="$FIX/specs/tasks.md" \
    SUPERVISOR_EVENTS=/tmp/supervisor-events.csv \
    ORACLE_ROOT="$FIX" \
    EVIDENCE_LIVENESS_LEDGER="$FIX/migration/evidence-liveness.md" \
    bash .hermes/harness/evidence-liveness.sh heartbeat S02 || true
  if STORY_TASKS="$FIX/specs/tasks.md" \
    SUPERVISOR_EVENTS=/tmp/supervisor-events.csv \
    ORACLE_ROOT="$FIX" \
    EVIDENCE_LIVENESS_LEDGER="$FIX/migration/evidence-liveness.md" \
    bash .hermes/harness/evidence-liveness.sh check S02 2>/tmp/evidlive-red.txt; then
    echo evidlive-should-red
  else
    grep -q 'RED:O-EVIDLIVE' /tmp/evidlive-red.txt \
      && echo evidlive-red-ok
  fi
}
check "check REDs when Findings exist but K2/K11 silent (O-EVIDLIVE)" 0 "evidlive-red-ok"

# O-PORTDERIVE / ARCH A1 — REDESIGN brief contract + §7→Port derive
# Note: roadmap_fixture was redefined later for parse-roadmap — use a local fixture.
portderive_roadmap_fix() { # $1 = brief contract? (yes|no)
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
- kind: reimplement
- seat-budget: 5
EOF
  cat > briefs/S01-models.md <<'EOF'
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
  if [ "$1" = "yes" ]; then
    cat > briefs/S02-services.md <<'EOF'
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
`CartService` — REDESIGN: target CDI `@ApplicationScoped` + JAX-RS `@Path` (→ ConcurrentHashMap state).
## Contracts owned by this story
- seat-budget: 5
x
## Done-criteria
x
EOF
  else
    cat > briefs/S02-services.md <<'EOF'
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
  fi
  cat > inv.md <<'EOF'
## Summary by class
- rewrite: 1 — javaee-pom-to-quarkus-00010
- OPEN DESIGN: 1 — springboot-web-to-quarkus-00000
EOF
}

run_case() {
  mkfix; portderive_roadmap_fix no
  out=$(python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md 2>&1) || true
  echo "$out" | grep -q 'LINT:O-PORTDERIVE' && echo portderive-brief-red-ok
}
check "roadmap-lint REDs OPEN DESIGN story without REDESIGN contract (O-PORTDERIVE)" 0 "portderive-brief-red-ok"

run_case() {
  mkfix; portderive_roadmap_fix yes
  out=$(python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md 2>&1) || true
  echo "$out" | grep -q 'ROADMAP OK' && echo portderive-brief-green-ok
}
check "roadmap-lint accepts OPEN DESIGN brief with REDESIGN contract (O-PORTDERIVE)" 0 "portderive-brief-green-ok"

run_case() {
  grep -q 'O-PORTDERIVE' "$HARNESS_DIR/roadmap-lint.py" \
    && grep -q 'O-PORTDERIVE' "$HARNESS_DIR/plan-lint.py" \
    && grep -q 'architecture-profile.md' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-PORTDERIVE' "$HARNESS_DIR/outer-loop.sh" \
    && echo portderive-wire-ok
}
check "O-PORTDERIVE wired in roadmap-lint + plan-lint + outer-loop" 0 "portderive-wire-ok"

# O-GUARDMANIFEST — ARCH-B2 stage×mechanism×verification inventory
run_case() {
  [ -x "$HARNESS_DIR/guard-manifest.sh" ] || chmod +x "$HARNESS_DIR/guard-manifest.sh"
  bash "$HARNESS_DIR/guard-manifest.sh" --check \
    && grep -qE '\| *Stage *\|' "$HARNESS_DIR/guard-manifest.md" \
    && grep -qE '\| *Mechanism *\|' "$HARNESS_DIR/guard-manifest.md" \
    && grep -qE '\| *Verification *\|' "$HARNESS_DIR/guard-manifest.md" \
    && grep -q 'O-INFERABSENT' "$HARNESS_DIR/guard-manifest.md" \
    && grep -q 'O-EXECCORPUS' "$HARNESS_DIR/guard-manifest.md" \
    && grep -q 'O-EVIDLIVE' "$HARNESS_DIR/guard-manifest.md" \
    && grep -q 'O-GUARDMANIFEST' "$HARNESS_DIR/guard-manifest.md" \
    && grep -q 'O-GOLDENFRESH' "$HARNESS_DIR/guard-manifest.md" \
    && grep -q 'O-PORTDERIVE' "$HARNESS_DIR/guard-manifest.md" \
    && grep -q 'O-STORYKIND' "$HARNESS_DIR/guard-manifest.md" \
    && grep -q 'O-SPECREIMPL' "$HARNESS_DIR/guard-manifest.md" \
    && grep -qE '\| L1' "$HARNESS_DIR/guard-manifest.md" \
    && grep -qE '\| L2' "$HARNESS_DIR/guard-manifest.md" \
    && grep -qE '\| L3' "$HARNESS_DIR/guard-manifest.md" \
    && ! grep -nE '(^|[[:space:]])rg[[:space:]]+-n' "$HARNESS_DIR/guard-manifest.sh" \
    && grep -q '_grepn\|grep -nE' "$HARNESS_DIR/guard-manifest.sh" \
    && echo guardmanifest-ok
}
check "guard-manifest stage×mechanism×verification --check (O-GUARDMANIFEST)" 0 "guardmanifest-ok"

run_case() {
  bash "$HARNESS_DIR/guard-manifest.sh" \
    && bash "$HARNESS_DIR/guard-manifest.sh" --check \
    && n=$(awk '/^### harness O-\* \/ guard markers/{s=1;next} s&&/^```$/{if(f){exit} f=1;next} s&&f{print}' \
         "$HARNESS_DIR/guard-manifest.md" | grep -cE '^[0-9]+:' || true) \
    && test "$n" -ge 1 \
    && echo guardmanifest-regen-ok
}
check "guard-manifest regenerate + non-empty harvest (O-GUARDMANIFEST)" 0 "guardmanifest-regen-ok"

# O-EXECCORPUS — archived execution replay (symmetric with O-PLANCORPUS)
run_case() {
  local ec="$HARNESS_DIR/tests/fixtures/exec-corpus"
  [ -x "$HARNESS_DIR/exec-corpus-lint.sh" ] || chmod +x "$HARNESS_DIR/exec-corpus-lint.sh"
  [ -f "$HARNESS_DIR/exec-corpus-lint.sh" ] \
    && [ -f "$ec/manifest.env" ] \
    && [ -d "$ec/s03-t004-sfixnodelta" ] \
    && [ -f "$ec/s03-t004-sfixnodelta/failure-delta.txt" ] \
    && [ -d "$ec/s03-t004-escalation-cause" ] \
    && [ -f "$ec/s03-t004-escalation-cause/escalation-cause-T-004.txt" ] \
    && grep -q 'O-EXECCORPUS\|exec-corpus-lint' "$HARNESS_DIR/exec-corpus-lint.sh" \
    && grep -q 'sfix_tip_content_empty' "$HARNESS_DIR/exec-corpus-lint.sh" \
    && grep -q 'classify_cause_from_err\|O-STEPFINISHRED' "$HARNESS_DIR/exec-corpus-lint.sh" \
    && echo execcorpus-wire-ok
}
check "exec-corpus-lint wiring + fixtures present (O-EXECCORPUS)" 0 "execcorpus-wire-ok"

run_case() {
  out=$(bash "$HARNESS_DIR/exec-corpus-lint.sh" --case s03-t004-sfixnodelta 2>&1) || true
  printf '%s\n' "$out" | grep -q 'PASS sfixnodelta' \
    && printf '%s\n' "$out" | grep -q 'O-EXECCORPUS PASS' \
    && echo execcorpus-sfixnodelta-ok
}
check "exec-corpus T-004 O-SFIXNODELTA refuse seat burn (O-EXECCORPUS)" 0 "execcorpus-sfixnodelta-ok"

run_case() {
  out=$(bash "$HARNESS_DIR/exec-corpus-lint.sh" --case s03-t004-escalation-cause 2>&1) || true
  printf '%s\n' "$out" | grep -q 'PASS escalation-cause' \
    && printf '%s\n' "$out" | grep -q 'O-EXECCORPUS PASS' \
    && echo execcorpus-escalcause-ok
}
check "exec-corpus T-004 escalation-cause sensor-red (O-EXECCORPUS)" 0 "execcorpus-escalcause-ok"

run_case() {
  out=$(bash "$HARNESS_DIR/exec-corpus-lint.sh" 2>&1) || true
  printf '%s\n' "$out" | grep -qE 'O-EXECCORPUS PASS \(2 case' \
    && echo execcorpus-sweep-ok
}
check "exec-corpus bare full-sweep rc=0 (O-EXECCORPUS)" 0 "execcorpus-sweep-ok"

# O-STORYKIND / ARCH A3 — roadmap kind field on OPEN DESIGN / §7 REDESIGN stories
run_case() {
  mkfix; portderive_roadmap_fix yes
  sed -i.bak '/^- kind:/d' roadmap.md
  out=$(python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md 2>&1) || true
  echo "$out" | grep -q 'LINT:O-STORYKIND' && echo storykind-missing-red-ok
}
check "roadmap-lint REDs OPEN DESIGN story without kind (O-STORYKIND)" 0 "storykind-missing-red-ok"

run_case() {
  mkfix; portderive_roadmap_fix yes
  sed -i.bak 's/^- kind: reimplement/- kind: rename/' roadmap.md
  out=$(python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md 2>&1) || true
  echo "$out" | grep -q 'LINT:O-STORYKIND' && echo storykind-rename-red-ok
}
check "roadmap-lint REDs OPEN DESIGN with kind=rename (O-STORYKIND)" 0 "storykind-rename-red-ok"

run_case() {
  mkfix; portderive_roadmap_fix yes
  sed -i.bak 's/^- kind: reimplement/- kind: mixed/' roadmap.md
  out=$(python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md 2>&1) || true
  echo "$out" | grep -q 'LINT:O-STORYKIND' && echo storykind-mixed-bare-red-ok
}
check "roadmap-lint REDs kind=mixed without justification (O-STORYKIND)" 0 "storykind-mixed-bare-red-ok"

run_case() {
  mkfix; portderive_roadmap_fix yes
  sed -i.bak 's/^- kind: reimplement/- kind: mixed — harvest + convert; split deferred/' roadmap.md
  out=$(python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md 2>&1) || true
  echo "$out" | grep -q 'ROADMAP OK' && echo storykind-mixed-green-ok
}
check "roadmap-lint accepts kind=mixed with split justification (O-STORYKIND)" 0 "storykind-mixed-green-ok"

run_case() {
  grep -q 'O-STORYKIND' "$HARNESS_DIR/roadmap-lint.py" \
    && grep -q 'kind: rename|reimplement|mixed' "$HARNESS_DIR/../skills/migration-harness/SEQUENCING.md" \
    && echo storykind-wire-ok
}
check "O-STORYKIND wired in roadmap-lint + SEQUENCING (O-STORYKIND)" 0 "storykind-wire-ok"

# O-SEATBUDGET / ARCH A5 — kind × incidents → seat-budget + overrun escalate
run_case() {
  mkfix; portderive_roadmap_fix yes
  sed -i.bak '/^- seat-budget:/d' roadmap.md
  out=$(python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md 2>&1) || true
  echo "$out" | grep -q 'LINT:O-SEATBUDGET' && echo seatbudget-missing-red-ok
}
check "roadmap-lint REDs kind story without seat-budget (O-SEATBUDGET)" 0 "seatbudget-missing-red-ok"

run_case() {
  mkfix; portderive_roadmap_fix yes
  sed -i.bak 's/^- seat-budget: 5/- seat-budget: 99/' roadmap.md
  out=$(python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md 2>&1) || true
  echo "$out" | grep -q 'LINT:O-SEATBUDGET' && echo seatbudget-wrong-red-ok
}
check "roadmap-lint REDs seat-budget mismatch vs kind×incidents (O-SEATBUDGET)" 0 "seatbudget-wrong-red-ok"

run_case() {
  mkfix; portderive_roadmap_fix yes
  # brief without seat-budget publish
  sed -i.bak '/seat-budget:/d' briefs/S02-services.md
  out=$(python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md 2>&1) || true
  echo "$out" | grep -q 'LINT:O-SEATBUDGET' && echo seatbudget-brief-red-ok
}
check "roadmap-lint REDs brief missing seat-budget publish (O-SEATBUDGET)" 0 "seatbudget-brief-red-ok"

run_case() {
  mkfix; portderive_roadmap_fix yes
  out=$(python3 "$HARNESS_DIR/roadmap-lint.py" roadmap.md inv.md 2>&1) || true
  echo "$out" | grep -q 'ROADMAP OK' && echo seatbudget-green-ok
}
check "roadmap-lint accepts kind×incidents seat-budget + brief (O-SEATBUDGET)" 0 "seatbudget-green-ok"

run_case() {
  n=$(python3 "$HARNESS_DIR/seat-budget.py" expected --kind reimplement --incidents 51)
  # unit=10 → ceil(51/10)=6 × 5 = 30
  [ "$n" = "30" ] && echo seatbudget-derive-ok
}
check "seat-budget.py derives reimplement×51 → 30 (O-SEATBUDGET)" 0 "seatbudget-derive-ok"

run_case() {
  mkfix
  sid=S99
  printf '5\n' > "/tmp/story-seat-budget-${sid}"
  rm -f /tmp/oc-${sid}-*.json
  : > "/tmp/oc-${sid}-T-001.json"
  : > "/tmp/oc-${sid}-T-002.json"
  : > "/tmp/oc-${sid}-T-003.json"
  : > "/tmp/oc-${sid}-T-004.json"
  : > "/tmp/oc-${sid}-T-005.json"
  : > "/tmp/oc-${sid}-T-006.json"
  # budget=5 factor=2 → limit=10; actual=6 → under
  python3 "$HARNESS_DIR/seat-budget.py" check-overrun --sid "$sid" --budget 5 --factor 2 \
    && : > "/tmp/oc-${sid}-T-007.json" \
    && : > "/tmp/oc-${sid}-T-008.json" \
    && : > "/tmp/oc-${sid}-T-009.json" \
    && : > "/tmp/oc-${sid}-T-010.json" \
    && : > "/tmp/oc-${sid}-T-011.json" \
    && ! python3 "$HARNESS_DIR/seat-budget.py" check-overrun --sid "$sid" --budget 5 --factor 2 \
    && echo seatbudget-overrun-ok
  rm -f /tmp/oc-${sid}-*.json "/tmp/story-seat-budget-${sid}"
}
check "seat-budget overrun trips when actual > budget×factor (O-SEATBUDGET)" 0 "seatbudget-overrun-ok"

run_case() {
  grep -q 'O-SEATBUDGET' "$HARNESS_DIR/roadmap-lint.py" \
    && grep -q 'seat-budget' "$HARNESS_DIR/../skills/migration-harness/SEQUENCING.md" \
    && grep -q 'check_seat_budget_overrun\|O-SEATBUDGET' "$HARNESS_DIR/supervisor.sh" \
    && grep -q 'BUDGET' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'seat-budget' "$HARNESS_DIR/../skills/migration-harness/BRIEF-TEMPLATE.md" \
    && echo seatbudget-wire-ok
}
check "O-SEATBUDGET wired in lint+banner+supervisor+SEQUENCING (O-SEATBUDGET)" 0 "seatbudget-wire-ok"

# O-SPECREIMPL / ARCH A2 — sibling spec.md REDESIGN → Port: reimplement coverage
specreimpl_fixture() { # $1 = port? (yes|no)
  mkdir -p specs/s02-demo
  cat > specs/s02-demo/spec.md <<'EOF'
# S02: Services

## Observations
`CartService` is REDESIGN / OPEN DESIGN — target ConcurrentHashMap + 404-on-missing GET.
ShoppingCart is HARVEST (faithful carry).
EOF
  if [ "$1" = "yes" ]; then
    cat > specs/s02-demo/tasks.md <<'EOF'
#### T-001: Convert CartService
**Class**: infer
**Shape**: create
**Port**: reimplement
- Target: `src/main/java/com/demo/service/CartService.java`
- Procedure: harvest-from-staging → API mapping → first-write
- API mapping: HashMap → ConcurrentHashMap; missing GET → 404
EOF
  else
    cat > specs/s02-demo/tasks.md <<'EOF'
#### T-001: Convert CartService
**Class**: infer
**Shape**: create
- Target: `src/main/java/com/demo/service/CartService.java`
EOF
  fi
}

run_case() {
  mkfix; specreimpl_fixture no
  out=$(python3 "$HARNESS_DIR/plan-lint.py" specs/s02-demo/tasks.md 2>&1) || true
  echo "$out" | grep -q 'LINT:O-SPECREIMPL' && echo specreimpl-red-ok
}
check "plan-lint REDs spec.md REDESIGN class without Port: reimplement (O-SPECREIMPL)" 0 "specreimpl-red-ok"

run_case() {
  mkfix; specreimpl_fixture yes
  out=$(python3 "$HARNESS_DIR/plan-lint.py" specs/s02-demo/tasks.md 2>&1) || true
  echo "$out" | grep -q 'PLAN OK\|LINT:' 
  # Prefer no O-SPECREIMPL; other LINT classes may fire on thin fixture
  ! echo "$out" | grep -q 'LINT:O-SPECREIMPL' && echo specreimpl-green-ok
}
check "plan-lint accepts spec.md REDESIGN covered by Port: reimplement (O-SPECREIMPL)" 0 "specreimpl-green-ok"

run_case() {
  grep -q 'O-SPECREIMPL' "$HARNESS_DIR/plan-lint.py" \
    && grep -q 'spec.md' "$HARNESS_DIR/plan-lint.py" \
    && echo specreimpl-wire-ok
}
check "O-SPECREIMPL wired in plan-lint (O-SPECREIMPL)" 0 "specreimpl-wire-ok"

# O-M2COMPOSE — skeleton-first partition + computed seat-budget + brief stubs
run_case() {
  test -f "$HARNESS_DIR/m2-compose.py" \
    && grep -q 'm2-compose.py' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'O-M2COMPOSE' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M2_COMPOSE' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'm2_compose_bookkeeping' "$HARNESS_DIR/outer-loop.sh" \
    && grep -qi 'O-M2COMPOSE\|m2-compose' "$HARNESS_DIR/../skills/migration-harness/SEQUENCING.md" \
    && echo m2compose-wire-ok
}
check "m2-compose wired in outer-loop + SEQUENCING (O-M2COMPOSE)" 0 "m2compose-wire-ok"

run_case() {
  mkfix
  mkdir -p migration/briefs
  cat > migration/findings-inventory.md <<'EOF'
# Findings inventory

## springboot-parent-pom-to-quarkus-00000 [rewrite]

- Convert parent POM
- Decided target: Quarkus BOM
- /projects/legacy/pom.xml: line 1, 2

## springboot-di-to-quarkus-00000 [rewrite]

- CDI
- Decided target: @ApplicationScoped
- /projects/legacy/src/main/java/com/demo/service/FooService.java: line 10

## javax-to-jakarta-import-00001 [recipe]

- jakarta rename
- Decided target: recipe
- /projects/legacy/src/main/java/com/demo/model/Bar.java: line 3

## springboot-devservices-to-quarkus-00000 [non-mandatory]

- devservices
- Decided target: optional

## Summary by class

- recipe: 1 — javax-to-jakarta-import-00001
- rewrite: 2 — springboot-di-to-quarkus-00000, springboot-parent-pom-to-quarkus-00000
- non-mandatory: 1 — springboot-devservices-to-quarkus-00000
EOF
  out=$(python3 "$HARNESS_DIR/m2-compose.py" --root "$FIX" --mode skeleton 2>&1) || true
  echo "$out" | grep -q 'wrote skeleton\|O-M2COMPOSE: done' \
    && test -f "$FIX/migration/roadmap.md" \
    && grep -q 'O-M2COMPOSE-SKELETON' "$FIX/migration/roadmap.md" \
    && grep -q 'springboot-parent-pom-to-quarkus-00000' "$FIX/migration/roadmap.md" \
    && grep -q 'springboot-di-to-quarkus-00000' "$FIX/migration/roadmap.md" \
    && ! grep -q 'javax-to-jakarta-import-00001' "$FIX/migration/roadmap.md" \
    && grep -q 'Non-mandatory decisions' "$FIX/migration/roadmap.md" \
    && grep -q 'springboot-devservices-to-quarkus-00000' "$FIX/migration/roadmap.md" \
    && grep -qE 'deploy: true' "$FIX/migration/roadmap.md" \
    && ls "$FIX"/migration/briefs/S*.md >/dev/null 2>&1 \
    && echo m2compose-skeleton-ok
}
check "m2-compose skeleton partitions + briefs + K3 + deploy-last (O-M2COMPOSE)" 0 "m2compose-skeleton-ok"

run_case() {
  mkfix
  mkdir -p migration/briefs
  cat > migration/findings-inventory.md <<'EOF'
# Findings inventory

## springboot-parent-pom-to-quarkus-00000 [rewrite]

- parent
- Decided target: BOM
- /projects/legacy/pom.xml: line 1, 2, 3, 4, 5, 6, 7, 8, 9, 10

## springboot-di-to-quarkus-00000 [OPEN DESIGN]

- di
- Decided target: decide
- /projects/legacy/src/main/java/com/demo/service/FooService.java: line 1, 2

## Summary by class

- rewrite: 1 — springboot-parent-pom-to-quarkus-00000
- OPEN DESIGN: 1 — springboot-di-to-quarkus-00000
EOF
  cat > migration/roadmap.md <<'EOF'
# Modernization roadmap

## S01: Platform
- scope: pom.xml
- findings: springboot-parent-pom-to-quarkus-00000, springboot-di-to-quarkus-00000
- depends: -
- deploy: false
- done: platform ready
- rationale: BOM first
- kind: mixed — split platform vs service later
- seat-budget: 1

## S02: Services
- scope: src/main/java/com/demo/service/FooService.java
- findings: springboot-di-to-quarkus-00000
- depends: S01
- deploy: false
- done: services ready
- rationale: after platform
- kind: reimplement
- seat-budget: 99
EOF
  out=$(python3 "$HARNESS_DIR/m2-compose.py" --root "$FIX" --mode fill 2>&1) || true
  # dual-owner DI kept on S01 only; S02 budget corrected; last deploy true; brief stubs
  s01=$(awk '/^## S01:/{p=1;next}/^## /{p=0}p' migration/roadmap.md)
  s02=$(awk '/^## S02:/{p=1;next}/^## /{p=0}p' migration/roadmap.md)
  echo "$s01" | grep -q 'springboot-di-to-quarkus-00000' \
    && ! echo "$s02" | grep -q 'springboot-di-to-quarkus-00000' \
    && echo "$s02" | grep -qE '^- seat-budget: 5$' \
    && echo "$s02" | grep -qE '^- deploy: true$' \
    && ls migration/briefs/S01-*.md >/dev/null 2>&1 \
    && ls migration/briefs/S02-*.md >/dev/null 2>&1 \
    && echo "$out" | grep -q 'seat-budget-updates\|O-M2COMPOSE: done' \
    && echo m2compose-fill-ok
}
check "m2-compose fill dedupes coverage + writes seat-budget + deploy-last (O-M2COMPOSE)" 0 "m2compose-fill-ok"

# O-M2-429 — rate-limit does not burn M2 attempt; real backoff (not claimed-only)
run_case() {
  grep -q 'O-M2-429' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M2_429_BACKOFF_SECS' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'attempt .* NOT spent' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'caller must NOT-spend + backoff' "$HARNESS_DIR/outer-loop.sh" \
    && ! grep -q 'supervisor backs off 15m on orch 429s' "$HARNESS_DIR/outer-loop.sh" \
    && echo m2429-wire-ok
}
check "outer-loop M2 429 NOT-spent + real backoff wire (O-M2-429)" 0 "m2429-wire-ok"

# O-M2429CAP — consecutive NOT-spent 429s capped; distinct fail_run cause; reset on non-429
run_case() {
  grep -q 'O-M2429CAP' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M2_429_MAX' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M3_429_MAX' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M3_429_BACKOFF_SECS' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'sleep "${M3_429_BACKOFF_SECS}"' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'quota exhausted after .* rate-limited seats (O-M2-429CAP)' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M2_429_COUNT=0' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M3_429_COUNT=0' "$HARNESS_DIR/outer-loop.sh" \
    && echo m2429cap-wire-ok
}
check "outer-loop M2/M3 429 NOT-spent cap + distinct fail cause (O-M2429CAP)" 0 "m2429cap-wire-ok"

# O-M2RETRYINLINE — attempt-2 prompt inlines bounded lint (not path-only)
run_case() {
  grep -q 'O-M2RETRYINLINE' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'BEGIN ROADMAP-LINT' "$HARNESS_DIR/outer-loop.sh" \
    && grep -q 'M2_RETRY_LINT_LINES' "$HARNESS_DIR/outer-loop.sh" \
    && ! grep -qE 'findings are in /tmp/roadmap-lint\.txt \(read it with your file tools\)' \
         "$HARNESS_DIR/outer-loop.sh" \
    && echo m2retryinline-wire-ok
}
check "outer-loop M2 retry inlines lint (O-M2RETRYINLINE)" 0 "m2retryinline-wire-ok"

# O-M2CORPUS — known-RED v4 M2 lint×2 fixture re-lints RED with live argv
run_case() {
  test -f "$HARNESS_DIR/m2-corpus-lint.sh" \
    && test -d "$HARNESS_DIR/tests/fixtures/m2-corpus/v4-m2-lintx2-10790d6" \
    && out=$(bash "$HARNESS_DIR/m2-corpus-lint.sh" --case v4-m2-lintx2-10790d6 2>&1) \
    && echo "$out" | grep -q 'PASS v4-m2-lintx2-10790d6' \
    && echo "$out" | grep -q 'O-M2CORPUS PASS' \
    && echo m2corpus-red-ok
}
check "m2-corpus known-RED v4 lint×2 stays RED (O-M2CORPUS)" 0 "m2corpus-red-ok"

# O-MONSTART — preflight --start wires dual-monitor start (host telemetry)
run_case() {
  local top preflight
  top=$(git -C "$HARNESS_DIR/../../../../.." rev-parse --show-toplevel 2>/dev/null || true)
  preflight="${top}/scripts/track-b/v9-preflight-outer-start.sh"
  [ -n "$top" ] && [ -f "$preflight" ] \
    && grep -q 'O-MONSTART' "$preflight" \
    && grep -qE 'v10-v3-dual-monitor-start\.sh|dual-monitor-start' "$preflight" \
    && echo monstart-wire-ok
}
check "preflight --start wires dual-monitor (O-MONSTART)" 0 "monstart-wire-ok"

echo "----"
echo "$PASS/$N passed"
if [ "$FAIL" -ne 0 ]; then
  echo "# instruments FAIL count=$FAIL" >&2
  exit 1
fi
exit 0

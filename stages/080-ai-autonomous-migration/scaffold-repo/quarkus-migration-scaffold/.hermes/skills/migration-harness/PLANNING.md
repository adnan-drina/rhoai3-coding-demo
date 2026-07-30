# M3 SPECIFY — plan (and findings access notes)

Plans map findings to the DECIDED targets in [MAPPINGS.md](MAPPINGS.md) —
cite the catalog, do not re-derive architecture per run. `tasks.md` MUST
follow [TASKS-TEMPLATE.md](TASKS-TEMPLATE.md) — the supervisor's plan
lint bounces non-conforming plans.

M1 ground truth and the architecture profile live in [ANALYSIS.md](ANALYSIS.md)
(and `analyze.sh`). This file owns M3. The normalize snippet below is
kept so whole-app supervisor runs that land here without an outer-loop
M1 still have a fallback path.

## Contents
- M1 fallback — normalize ground truth (prefer ANALYSIS.md / analyze.sh)
- Working with the findings file
- M3 — plan (spec handoff)

## M1 fallback — normalize ground truth

The contract input is `migration/mta-findings.json` (konveyor analyzer
format: list of rulesets → `violations` keyed by rule id → `incidents`
with `uri`/`lineNumber`/`message`).

```bash
latest=$(ls -t /projects/legacy/.vscode/mta-core/analysis_*.json 2>/dev/null | head -1)
if [ -n "$latest" ]; then
  cp "$latest" /projects/modernized/migration/mta-findings.json
else
  # No IDE analysis available — produce ground truth with the kantra sensor
  kantra-ensure
  /tmp/kantra/kantra analyze -i /projects/legacy -o /tmp/kantra-baseline \
    --target quarkus --json-output --overwrite || true
  # kantra has a known bug marshaling the dependencies file: the command may
  # exit 1 even though the violations output.json is complete. Trust the file.
  cp /tmp/kantra-baseline/output.json /projects/modernized/migration/mta-findings.json
fi
```

### Working with the findings file — never read it whole

`mta-findings.json` is large (hundreds of KB). Reading it into context
wastes the budget and stalls the run. Extract what you need with the
BUNDLED script (NOT an inline `python3 - <<EOF` heredoc — the headless
command policy denies those, hanging ~5 min then blocking):

```bash
python3 .hermes/skills/migration-harness/scripts/extract_findings.py
# a single rule's incidents:
python3 .hermes/skills/migration-harness/scripts/extract_findings.py --rule <RULE_ID>
```

Read individual incidents (file/line/message) the same way — filtered by
rule id, never the full file.

## M3 — plan (spec handoff)

Read the legacy code and `migration/mta-findings.json`, then write the
contract into the same layout stage 070 uses:

- `specs/<NNN-migration-slug>/spec.md` — observed legacy behavior + API
  contract (endpoints, data shapes, side effects), with legacy file paths
  as evidence.
- `specs/<NNN-migration-slug>/plan.md` — Quarkus mapping. Tag every item
  `rewrite` (mechanical: annotation/import/dependency swaps covered by
  OpenRewrite recipes) or `infer` (judgment: design, API shape, tests).
- `specs/<NNN-migration-slug>/tasks.md` — ordered checklist. Rewrite tasks
  before infer tasks. Every mandatory finding maps to at least one task;
  every task cites its finding rule ids.

The plan lint (`.hermes/harness/plan-lint.py`) enforces, deterministically:
task headings `#### T-NNN: title` (any heading depth 2–6; zero-padded
numeric ids, each used once); a `Class: rewrite|infer` marker per task;
all rewrite tasks before the first infer task; **S-INFTEST** — after the
first infer task, characterization / package-verify / follow-on work must
also be Class infer (plan-lint forbids rewrite after infer began; V9 S03);
**S-PKGDIR** — package-structure / mkdir tasks must require `.gitkeep` or
`package-info.java` (empty dirs are uncommittable; O-PKGDIR);
decided design content in
every infer body (file mappings/signatures/annotations); the legacy
user-facing surface (web UI / index page) covered by a task or
explicitly waived with a reason; every mandatory finding, every
migration.yaml `preserve:` item, and the migration.yaml
`acceptance.path` mapped to a task; and no legacy-package targets — the
project root is `migration.yaml` `targetPackage` (never the `legacyPackage`).
Package rename is a **full prefix replace**:
`legacyPackage.service` → `targetPackage.service`
(e.g. `com.redhat.coolstore.service` → `com.demo.service`).
Never invent `targetPackage` + last legacy segment
(`com.demo.coolstore` is wrong when `targetPackage` is `com.demo`).

**M1 hands you a spec input bundle — consume it, do not re-derive
it** (docs/MTA-TO-SPEC-MAPPING.md):

- `migration/findings-inventory.md` — every mandatory finding already
  classified via the MAPPINGS rule-join: `recipe` rules are ALREADY
  EXECUTED (listed in `migration/recipe-log.md` — create NO tasks for
  them); `rewrite`/`infer` rules carry their decided target; OPEN
  DESIGN rows are where your judgment goes. Confirm the listed
  preserve-candidates against migration.yaml.
- `migration/staging/src` — legacy sources already recipe-transformed
  (e.g. jakarta imports). Harvest tasks pull from the staging tree,
  NOT from /projects/legacy.
- `migration/dependency-order.md` — the conversion order (below).

Your M3 judgment budget belongs to: the behavioral contract (from
legacy tests + code reading — findings only say where to look) and the
OPEN DESIGN / infer shapes.

Ordering and test placement (MigIQ-derived, validated against cart
run #2's failures):

- **Conversion order within a story:** extensions and BOM first, then
  models, then resources, then config keys, then tests
  (`extensions → models → resources → config → tests`).
- **Conversion tasks follow `migration/dependency-order.md`** (M1
  emits it): dependencies before dependents — models and utilities
  first, endpoints last — so the tree compiles at every commit. Cart
  run #2's three red commits all came from harvesting dependents before
  their dependencies. Classes in a listed circular group convert in ONE
  task.
- **Characterization tests come EARLY, not as a tail — but only for
  types this story owns.** Immediately after the mechanical rewrite
  tasks, port legacy tests / pin behavior for classes **in this story's
  scope**. Model-harvest stories characterize **models** (constructors,
  equals, cart item math on the model types). Do **not** schedule
  service/endpoint characterization (`ShoppingCartServiceTest` against
  a real `ShoppingCartService`) until the service story owns those
  redesign types — otherwise workers invent `src/main` services or ship
  placeholder `assertThat(true)` tests (V8 S02 T-005 abort / G-PLACE).
  God nodes flagged in dependency-order.md get characterization **in
  the story that converts them**, before or with that conversion.
- **Tests pin the TARGET for redesign classes, LEGACY for harvest
  classes** (architecture-profile §7). A HARVEST class's tests assert
  legacy values. A REDESIGN class's tests assert its §7 target contract;
  where the target deliberately differs from legacy (GET→404,
  invalid→400), the test task cites the profile decision in one line
  ("GET returns 404 on missing — target contract, profile §7; not legacy
  create-on-GET"). NEVER write a test that pins a behavior the target
  removes — that test would have to be rewritten, which is the
  write-then-rewrite waste this process eliminates (V4 shipped faithful
  because its tests pinned legacy create-on-GET/dedupe-order). The infer
  task for a redesign class must state its §7 target shape (plan-lint
  §7-traceability enforces this); MAPPINGS "Production-grade defaults" is
  the source of the shapes.
- **A test task never precedes the classes it exercises.** A task that
  ports or framework-converts tests referencing types X, Y, Z must be
  ordered AFTER the conversion tasks for X, Y, Z — the test compiles
  against the destination, so those classes must already exist there.
  V4 T-010 put "convert tests to @QuarkusTest" before the model/service
  conversions (T-011–T-015); the session fabricated the missing classes
  to make it compile, the stray sweep archived them, and the milestone
  broke on a compile error — one wasted session plus a sensor-fix. Order
  test tasks by their widest dependency, not their file type.
- **A characterization task uses TEST DOUBLES for not-yet-converted
  REDESIGN types — it NEVER creates the real class in `src/main`.** When a
  test in story S needs a service/endpoint that a LATER story owns (per
  architecture-profile §7 / the roadmap), stub it with a Mockito mock or a
  test-local fake in `src/test`, not by writing `src/main/.../Service.java`.
  Creating the real later-story class early fabricates it (no harvest
  source, wrong shape) and poisons the later story, which then "converts"
  the stub instead of redesigning from the brief. V5 T-004 (S01 models
  story) invented `CatalogService` + a HashMap `ShoppingCartServiceImpl`
  to pass its test; fidelity caught it and a fix session then tried to
  waive the gate. The story-scope sensor now REVERTS an `src/main`
  REDESIGN class a later story owns — plan the test with doubles instead.

Two task-authoring constraints (from cart run #2):

- **Every task changes code or tests.** No ceremonial tasks ("final
  commit", "run validation", "prepare for gate") — commits happen per
  task and the gate runs in the factory; a task whose only product is a
  commit message or a report executes as an empty commit and wastes a
  session.
- **The plan's test tasks must be sized to the quality gate.** The
  factory fails new-code coverage < 80%; a tail that validates but never
  expands tests plans its own gate failure. Include explicit test tasks
  covering every migrated class (models and services included, not just
  endpoints).

### K1 — incident ownership (plan-lint)

Naming a Findings rule id is not enough when the rule has incidents.
Every in-scope mandatory incident **file** must be claimed by exactly one
task via **declared fields** (not Out-of-scope disclaimers):

1. a **Target** / **Target design** line with the path (`→ src/…`), or
2. **Absorbs:** when the legacy file is deleted/merged, or
3. **Owns:** for an explicit path claim without a Target arrow.

```text
**Target design**: → `src/main/java/<targetPackage>/service/CartService.java`
**Absorbs**: src/main/java/<legacyPackage>/rest/OldHelper.java
**Owns**: src/main/java/<targetPackage>/model/Product.java
**Out of scope:** do NOT touch src/main/java/<targetPackage>/Beta.java — later story
```

`Out of scope:` / “owned by T-00x” lines do **not** count as ownership
(K1-OWN / K1-CONF). `plan-lint` emits `LINT:incident-unowned:` /
`LINT:incident-conflict:` when a file has zero owners or two+. Package
mapping is `legacyPackage` → `targetPackage` from `migration.yaml`.


---
name: bootstrap-destination
description: >
  Use at M2 PLAN, after the evidence bundle and before the first
  verification, to produce the deterministic destination baseline for the
  Spring-compatibility path: import the frozen legacy source into the
  destination tree, rewrite the pom from the compat-mapping catalog and
  the pins (Quarkus BOM and plugin, starters and JDBC drivers to
  extensions, compiler/surefire pins), rename mapped property keys, and
  delete the @SpringBootApplication main class. Pure stdlib
  (ElementTree, line-based properties); no third-party tool, no regex, no
  model. Idempotent. Refuses without the catalog, the pins, or the frozen
  copy. Never run inside an M3 card.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - migration
    - m2
    category: migration
    kind: guidance
    paths:
      reads: ["/projects/modernized/.derived/frozen-input", "/projects/modernized/decisions.yaml", "/projects/modernized/migration.yaml", "/projects/modernized/decided-repairs", "/projects/modernized/operator-patches", "/projects/modernized/.hermes/planning", "/projects/modernized/.hermes/pins.json", "/projects/modernized/evidence/planning/evidence-bundle.json"]
      writes: ["/projects/modernized/decisions.yaml", "/projects/modernized/pom.xml", "/projects/modernized/src", "/projects/modernized/evidence/producers/bootstrap.json", "/projects/modernized/evidence/producers/decided-repairs.json"]
---
# Bootstrap the destination (step 0 of fix-until-green)

Owns `evidence/producers/bootstrap.json` and the first product commit of
the run (the loop's baseline). After this step the compiler, the tests,
and the MTA rescan produce the real plan: the work list.

## Procedure

```bash
python3 "${HERMES_SKILL_DIR}/scripts/stamp-run-resources.py" --root /projects/modernized --verify
python3 "${HERMES_SKILL_DIR}/scripts/probe-bom-managed.py" --root /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap-destination.py" --root /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/check-datasource-decision.py" /projects/modernized
```

The probe measures, with Maven's own `help:effective-pom`, which artifacts
the pinned BOM manages (`evidence/build/bom-managed.json`); network once.

0a. **run resources** — every run owns its parity database, its credentials
   secret and its fixture identities; trusted platform code creates them when
   the workspace is initiated, never by hand and never shared, and writes a
   receipt into the run's own workspace secret. The golden therefore names no
   database: `stamp-run-resources.py` writes `decisions.yaml`
   `datasource.instance` from `migration.yaml` `resources.parity_database`. It
   is idempotent, it rewrites exactly that one line, and it compares rather
   than rewrites the credential variable NAMES (a disagreement between the
   run's resources and the decision refuses).
   `--verify` is not optional here. It establishes OWNERSHIP first — the
   endpoint is parsed into host, port and database and compared with the
   assignment and the receipt — and a refusal writes nothing, so a wrong target
   can never end this step with a stamped decision that a later run reads as
   settled. A destination with no `resources` block predates per-run resources
   and is left alone under the legacy exception. dest-init already ran this at
   workspace start; it is repeated here because M2 plans against the decision.

0. **settings** — refuses `MAVEN_SETTINGS_MISSING` unless `.mvn/maven.config`
   wires `-s .mvn/settings.xml` and that file declares the catalog's
   `maven_settings.profile` (Red Hat GA repository: the pinned
   `com.redhat.quarkus.platform` artifacts are not on Maven Central, and
   Maven 3 does not auto-read `.mvn/settings.xml`).
1. **import** — copies `pom.xml` and `src/` from the freeze receipt's
   `analysis_copy` (byte-identical to the frozen legacy mount) into the
   destination root. Packages are kept: the compat path does not rename.
   A file listed in `decisions.yaml` `retired_sources` (an accepted ADR,
   one path, one reason) is never imported and, if present, deleted and
   recorded as `source.delete` with the ADR; a retired path the frozen
   legacy never had blocks `RETIRED_SOURCE_MISSING`.
1b. **datasource** — the effective database is a decision, not a discovery:
   `decisions.yaml` `datasource` (under an accepted ADR) names the engine,
   its approved version, the matching JDBC extension, the build/run profile,
   the isolated instance, credential *references*, the reset procedure, and
   who owns schema and seed. The bootstrap renders it as **unprefixed**
   `quarkus.datasource.*` keys and adds the documented extension; the
   profile-prefixed families the legacy carried are REMOVED for every profile
   this run does not select, with each removal recorded against the decision:
   they name other databases, several carry literal credentials, and the
   source's own record is `.derived/frozen-input`, which keeps the legacy
   configuration verbatim. A second copy in the destination is residue, and
   `check-datasource-decision.py` refuses it -- bootstrap and its own checker
   disagreeing is not a state a worker can resolve (measured: v8 M2 blocked on
   exactly that, 2026-09-11). An engine the platform documents no extension for
   (`DATASOURCE_UNSUPPORTED`) or an extension that does not match the engine
   (`DATASOURCE_EXTENSION_MISMATCH`) blocks. `check-datasource-decision.py`
   then measures the rendered tree against the decision. It does not prove the
   configuration works: packaging and boot verification do that, and neither
   replaces the other.
1b. **build profiles** (ADR-010) — the legacy chose which implementation
   exists with `spring.profiles.active`; the platform resolves
   `@IfBuildProfile` at build time, so a profile nobody activates removes
   every bean gated on it and the build fails one missing implementation at
   a time with nothing naming the cause (measured on pilot v7). So every
   profile condition over the destination's own source roots must be
   *accounted for*: activated in `build_profiles.active`, or retired — and a
   retirement is **enumerated**, one row per condition
   (`build_profiles.retire[] = {path, type, member, annotation, profile}`),
   bound to the inventory it was read from
   (`build_profiles.inventory_sha256`). `propose-profile-retirement.py`
   proposes those rows and writes nothing; a person accepts them. The
   bootstrap applies them here, before the annotation remapping, and refuses
   a list that is unbound (`PROFILE_RETIREMENT_UNBOUND`), bound to another
   inventory (`PROFILE_RETIREMENT_STALE`) or describing a condition this tree
   does not have (`PROFILE_RETIREMENT_ABSENT`). Anything left over is
   `BUILD_PROFILE_UNACCOUNTED`. A bare `retire_gates: true` retires nothing:
   a retirement nobody can read is a deletion.
2. **pom** — from `.hermes/planning/catalogs/compat-mapping.json` and
   `.hermes/pins.json`: removes `spring-boot-starter-parent`, imports the
   pinned `quarkus-bom`, maps every listed starter and JDBC driver to its
   Quarkus extension, removes the Spring Boot plugin, adds the pinned
   Quarkus plugin and compiler/surefire pins. A Spring Boot dependency
   with no catalog row **stays in the pom** and is recorded as
   `UNMAPPED_DEPENDENCY`: removing it could drop runtime auto-configuration
   that still compiles. Removing the parent also removes its version
   management: a version-less dependency the BOM manages stays
   version-less; one it does not manage is pinned to the version the
   legacy build resolved (`managed_versions` in the build receipt, from
   the legacy effective pom) and recorded as `pom.pin-legacy-version`;
   no legacy version → `VERSION_UNMANAGED`; no probe → `BOM_PROBE_MISSING`.
3b. **baseline data** (ADR-009) — the engine is a decision; the DATA the
   destination starts from is not. It is the dataset the application contract
   DECLARES — the corpus's `initial_state` (`derived_from.seed`, else the
   `.sql` path the prose names), and only when the corpus names nothing is it
   discovered by the same rule the derivation uses (the source engine's
   `db/<engine>/populateDB.sql`). The bootstrap derives
   `src/main/resources/db/<engine>/baseline-data.sql` (the one name, the
   constant `BASELINE_FILENAME` in `scripts/_baseline_data.py`) from it: the
   INSERT statements translated for the destination engine one literal at a
   time, then one sequence-alignment statement per generated-identity column
   the **destination schema asset** declares, so every sequence continues from
   the seeded maximum. The source's own per-engine seed stays in the tree,
   untouched; it is simply no longer what the reset loads.
   Why it exists: v9 installed the source's `db/postgresql` assets while the
   corpus declared `db/hsqldb/populateDB.sql`. The two hold the same rows and
   differ in **17 date literals**, and the PostgreSQL schema `RESTART`s seven
   identity sequences at a fixed 100 where the engine the source was captured
   on continued from the seeded maximum — so a `POST` returned a `Location`
   with the wrong id and a read-back could differ in a date, with nothing in
   the build to say so.
   The asset carries its own header: the marker, the translator version, the
   contract digest, and the declared dataset and schema asset it came from
   (path + sha256); the receipt records the same plus the rows per table and
   the sequences aligned with their seeded values. `--reapply-catalog`
   regenerates it deterministically. A literal form the translator has no rule
   for is `BASELINE_UNTRANSLATABLE` with the statement quoted; a copy carrying
   the marker that no longer matches what its own contract generates is
   `BASELINE_HAND_EDITED` **by name** and is never overwritten. A tree with no
   declared dataset, no destination schema asset, or an engine the translator
   has no rules for records the reason and blocks nothing — the reset then
   keeps its previous behaviour and prints that the baseline is unverified.
3. **config** — renames mapped `application*.properties` keys and maps
   documented values (`create-drop` → `drop-and-create`); keys with no
   Quarkus equivalent are commented out and recorded.
4. **main** — deletes the class the JDK model marks
   `@SpringBootApplication` only when it is a trivial launcher (no fields,
   no other annotation, no method but `main`). A launcher that declares
   beans or configuration is kept and recorded as `MAIN_CLASS_NOT_TRIVIAL`.
4b. **decided repairs** (ADR-019) — repairs accepted ADRs already made enter a
   fresh run here, before the loop's first baseline, instead of as mid-run
   Operator steps. `decisions.yaml` `decided_repairs` names the specimen
   manifest (`decided-repairs/<specimen>/manifest.json`, schema
   `decided-repairs-manifest.schema.json`) and pins its sha256;
   `scripts/_decided_repairs.py` applies it. The engine knows KINDS, never an
   application -- every type, member, annotation, coordinate and key is
   manifest data:
   - `add_file` — a reviewed new file, only where absent or byte-identical;
     other bytes are `REPAIR_FILE_CONFLICT` and the file is never overwritten.
   - `replace_reviewed_file` — a reviewed replacement, only over the exact
     source bytes its review applies to; the independent review record (two
     distinct seats, the reviewed artifact's sha256, its source applicability)
     is reused only while all of them match the installed bytes; an ADR id is
     not a record (`REPAIR_REVIEW_MISSING` / `_NOT_INDEPENDENT` /
     `_ARTIFACT_MISMATCH` / `_APPLICABILITY`). Fresh test execution stays
     mandatory: it is written into the receipt's `obligations`.
   - `java_annotation_expression` — every annotation of one type resolved by
     the JDK parse tree plus JLS import rules (`scripts/java-structure/
     JavaStructure.java`, no regex, no classpath) gets its string attribute
     rewritten through a template that keeps the original expression
     verbatim; only the literal token changes. The site inventory of the
     frozen source is the applicability; a destination site that is neither
     original nor rewritten is `REPAIR_SITE_MISMATCH`, a non-literal value
     `REPAIR_ANNOTATION_VALUE_NOT_LITERAL`, an unresolvable simple name
     `REPAIR_ANNOTATION_UNRESOLVED`; the file is re-parsed after the edit and
     restored if it no longer parses.
   - `java_member_annotation` — one annotation on one type or field, plus its
     imports (`REPAIR_ANNOTATION_CONFLICT`, `REPAIR_IMPORT_CONFLICT`).
   - `pom_dependency` — one row, XML DOM; another version/scope/type is
     `REPAIR_DEPENDENCY_CONFLICT`; a version-less row the BOM probe does not
     list is `REPAIR_DEPENDENCY_UNMANAGED`.
   - `property` — one `key=value`; an existing different value, unprefixed or
     under any `%profile`, is `REPAIR_PROPERTY_CONFLICT`.
   - `pom_retire_execution` — removes ONLY the decided execution when its
     goals, phase and configuration equal the decision and the preserved
     goals stay; the goal bound anywhere else, other thresholds or a lost
     preserved goal is `REPAIR_EXECUTION_MISMATCH`; the thresholds go to the
     receipt's `coverage_account` as `retired-not-achieved` (and from there to
     `compose-coverage-account.py`). After the producer's LAST pom write the
     retirement is checked on `mvn help:effective-pom` under the decided
     build profiles and each declared Maven profile
     (`REPAIR_EFFECTIVE_MISMATCH`, `REPAIR_EFFECTIVE_UNVERIFIED`).
   Every transformation binds the frozen source's structure
   (`REPAIR_NOT_APPLICABLE` when the source differs), is atomic, and leaves a
   row in `evidence/producers/decided-repairs.json` (schema
   `decided-repairs-receipt.schema.json`): ADR, applicability expected and
   observed, implementation version plus engine and tool digests, input and
   output digests, files, symbols, status applied / already-applied /
   refused. `inventory` is the bootstrap repair inventory the run report
   reads. A second run changes no product file and records already-applied.
   A refusal is a bootstrap block; `bootstrap.json` `decided_repairs` binds
   the receipt by sha256; `advance.py --baseline` refuses
   (`LOOP_BASELINE_REPAIRS_PENDING`) and admission stays INCONCLUSIVE
   (`DECIDED_REPAIRS_MISSING` / `_STALE` / `_INCOMPLETE`,
   `DECIDED_REPAIR_REFUSED`) until every row is applied or already-applied.
   Admission records the run as `autonomous_execution_with_predecided_repairs`
   and seals the receipt. Authoring aid:
   `python3 scripts/_decided_repairs.py --root . --describe-source` prints the
   applicability the frozen copy yields for each transformation.
5. **receipt** — every change, every block, the catalog digest, the bundle
   digest and the pins used. A block exits 1 and keeps admission
   `INCONCLUSIVE` (`BOOTSTRAP_BLOCKED`) until a catalog row or an ADR
   resolves it; nothing is removed on a block. Admission also refuses
   `BOOTSTRAP_MISSING` / `BOOTSTRAP_STALE`.

Then `build-worklist` verifies the tree and records the baseline.

## Verification

- `scripts/../fix-until-green/scripts/fix-until-green.test.py` proves the
  pom/properties/main-class outcome on the http specimen and that a
  second run changes nothing.

## Scripts

- `scripts/probe-bom-managed.py` — what the pinned BOM manages (Maven effective pom → `evidence/build/bom-managed.json`)
- `scripts/bootstrap-destination.py` — the transform + receipt
- `scripts/_baseline_data.py` — the declared dataset → `baseline-data.sql` translator, the sequence alignment, and the reset contract (`plan_from_asset`, `verification_sql`, `verify_observations`); also the CLI the parity reset calls
- `scripts/_decided_repairs.py` — the ADR-019 decided-repair engine (kinds above), its receipt, the effective-pom check, `--describe-source`
- `scripts/java-structure/JavaStructure.java` — JDK compiler parse tree: imports, types, members, annotations with exact ranges and decoded literals
- `scripts/decided-repairs.test.py` — selftest on a synthetic project: every kind, idempotency, every typed refusal, review reuse, admission/baseline gaps, bootstrap integration
- `scripts/bootstrap-destination.test.py` — selftest (trivial launcher deleted; launcher with behavior kept + block; unmapped starter kept + block; second run preserves the tree; the derived baseline carries the declared dataset, aligns every identity sequence, regenerates deterministically, and refuses a hand-edited or untranslatable one)

## Pitfalls

- Editing the mapping to "make it compile". The catalog is a versioned
  contract of documented Quarkus mappings; anything else is a work-list
  item for the loop.
- Running it on a tree that already has accepted loop steps: the import
  is idempotent, but a re-bootstrap after steps is a new run.
- Editing `baseline-data.sql` to make a comparison pass. It is derived: the
  edit is refused by name on the next run, and the thing to fix is the
  declared dataset or the destination schema asset it was derived from.
  Generalizing one specimen's sequence strategy into the translator is the
  same mistake in the other direction — the alignment is read from the
  schema's own identity columns, never assumed.

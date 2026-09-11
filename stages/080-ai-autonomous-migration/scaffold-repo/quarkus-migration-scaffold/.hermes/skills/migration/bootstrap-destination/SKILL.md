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
      reads: ["/projects/modernized/.derived/frozen-input", "/projects/modernized/.hermes/planning", "/projects/modernized/.hermes/pins.json", "/projects/modernized/evidence/planning/evidence-bundle.json"]
      writes: ["/projects/modernized/pom.xml", "/projects/modernized/src", "/projects/modernized/evidence/producers/bootstrap.json"]
---
# Bootstrap the destination (step 0 of fix-until-green)

Owns `evidence/producers/bootstrap.json` and the first product commit of
the run (the loop's baseline). After this step the compiler, the tests,
and the MTA rescan produce the real plan: the work list.

## Procedure

```bash
python3 "${HERMES_SKILL_DIR}/scripts/probe-bom-managed.py" --root /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/bootstrap-destination.py" --root /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/check-datasource-decision.py" /projects/modernized
```

The probe measures, with Maven's own `help:effective-pom`, which artifacts
the pinned BOM manages (`evidence/build/bom-managed.json`); network once.

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
3. **config** — renames mapped `application*.properties` keys and maps
   documented values (`create-drop` → `drop-and-create`); keys with no
   Quarkus equivalent are commented out and recorded.
4. **main** — deletes the class the JDK model marks
   `@SpringBootApplication` only when it is a trivial launcher (no fields,
   no other annotation, no method but `main`). A launcher that declares
   beans or configuration is kept and recorded as `MAIN_CLASS_NOT_TRIVIAL`.
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
- `scripts/bootstrap-destination.test.py` — selftest (trivial launcher deleted; launcher with behavior kept + block; unmapped starter kept + block; second run preserves the tree)

## Pitfalls

- Editing the mapping to "make it compile". The catalog is a versioned
  contract of documented Quarkus mappings; anything else is a work-list
  item for the loop.
- Running it on a tree that already has accepted loop steps: the import
  is idempotent, but a re-bootstrap after steps is a new run.

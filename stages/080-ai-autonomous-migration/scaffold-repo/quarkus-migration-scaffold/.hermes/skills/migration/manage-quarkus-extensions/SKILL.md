---
name: manage-quarkus-extensions
description: Before adding or removing a Quarkus extension on an M3 destination pom — inventory installed deps, search the RH catalog, apply add/rm without rewriting the Red Hat BOM, and carry per-extension obligations (config/SQL/migrations) owned by the needing story
license: Apache-2.0
compatibility: Linux seat; Red Hat Quarkus platform; quarkus CLI optional
metadata:
  author: rhoai3-harness-team
  version: "1.1.0"
  hermes:
    tags:
    - migration
    - quarkus
    category: migration
    kind: guidance
---
# Manage Quarkus extensions (M3 / T-3)

Guidance only (R-SK.14). Does **not** replace persistence/JDBC/compile
preflight gates. Version **values** live in
`.hermes/pins.json` and the destination `pom.xml` — never
restate platform versions in this skill.

**DD3:** the story that needs an extension **adds it and owns** its
configuration/artifacts. Do not paste a fixed foundation menu.

Obligations once present: `references/extension-obligations.md`.
Spring→extension decision aid: `references/spring-dep-to-extension.md`.

## When to Use

- Before the first `pom.xml` dependency change that adds a Quarkus extension
  for an M3 story (REST, JDBC, security, Flyway, Jacoco, …).
- When deciding whether a Spring dependency implies an extension at all.
- When deciding whether an extension is **unused** and can be removed.
- When `quarkus ext ls` / Maven `quarkus:list` disagrees with what the story
  thinks is on the classpath.
- **Not** for project create / skeleton retirement — use
  `bootstrap-quarkus-project` + `reference-rh-quarkus-pom`.
- **Not** for Spring→Quarkus form mapping (`spring-to-quarkus-patterns`).

## Procedure

1. Read `references/rh-bom-and-mandatory-deps.md` (shared BOM policy + Jacoco
   gotcha). Confirm destination `quarkus.platform.*` matches
   `.hermes/pins.json` (or run
   `scripts/check-pom-platform-pins.py <root>`). Run
   `scripts/assert-extension-tooling.py` (W3) before the first CLI/Maven
   extension mutation — CLI without RH-first registry is a hard fail;
   CLI absent → typed `MAVEN_FALLBACK`.
2. If the ask comes from a Spring dependency, consult
   `references/spring-dep-to-extension.md` first — many deps need **no**
   extension or a native rewrite pair, not a lookalike add.
3. **Inventory** installed extensions:
   - Prefer: `quarkus ext ls` (inside the RH-pinned project).
   - Fallback: `mvn -q quarkus:list` via the Red Hat
     `quarkus-maven-plugin` from the pom (CLI absent / air-gap).
4. **Search** before inventing GAVs:
   - Prefer: `quarkus ext list --installable -s <term> --support-scope`
     (support-scope **column may be blank** on RH streams — still use RH
     versions; do not over-claim support metadata).
   - Fallback: Maven plugin list/search goals; never paste community
     `io.quarkus.platform` coords into an RH-pinned pom.
   - Ambiguous partial names fail loudly (`Multiple extensions matching`) —
     narrow the term; do not guess.
5. **Add** (inherits BOM version — never pin extension versions independently):
   - Prefer: `quarkus ext add <artifactId>`
   - Fallback: `mvn -q quarkus:add-extension -Dextensions="<artifactId>"`
   - After add: confirm `quarkus.platform.group-id` is still
     `com.redhat.quarkus.platform` (must not rewrite to
     `io.quarkus.platform`).
6. **Carry obligations** from `references/extension-obligations.md` for that
   family in this story's write-set (config, SQL, migrations, annotations).
   Artifact-only adds with silent-inert defaults are not done.
7. **Remove** only when the remove-unused BAR in
   `references/rh-bom-and-mandatory-deps.md` is met. Prefer **do not remove**
   when uncertain. Removal does **not** auto-clean orphaned
   `quarkus.<ext>.*` properties — scrub or leave intentionally.
8. Refuse `quarkus-spring-*` compatibility extensions (native Quarkus only —
   AGENTS + `spring-to-quarkus-patterns`).
9. OpenAPI generator plugin: a DEST_GENERATOR refusal from
   `assert-dest-generator-configured.py` emits the required
   `<library>native</library>` / `<useJakartaEe>true</useJakartaEe>` block
   (same constants the gate validates). Do not invent Gson or a second recipe.

## Pitfalls

- Running `quarkus ext *` without RH-first `~/.quarkus/config.yaml` (community
  catalog silently wins — run `assert-extension-tooling.py` first).
- Treating compile-clean alone as proof an extension is unused (build-time
  wiring; see remove-unused BAR).
- Adding `quarkus-jacoco` without dual Sonar paths + surefire `argLine`.
- Adding Flyway / security-jdbc / cache and stopping at the dependency line
  (silent failure modes in `extension-obligations.md`).
- Over-provisioning from "Spring has X → Quarkus must have X" without the
  mapping table.

## Verification

- `scripts/check-pom-platform-pins.py <root>` exits 0 with
  `OK: pom platform pins match `.hermes/pins.json``.
- When pom exists: `scripts/check-pom-jacoco-wiring.py <root>` exits 0
  (foundation Jacoco / dual Sonar paths / surefire argLine).
- `scripts/assert-extension-tooling.py` exits 0 (CLI+RH-first or Maven fallback).
- After add/rm: `quarkus.platform.group-id` remains
  `com.redhat.quarkus.platform` and `quarkus.platform.version` still matches
  `.hermes/pins.json` (no community rewrite).
- After add: story write-set includes the family's required obligations (or a
  typed wait with destination-inventory citation).
- Removals: story notes cite inventory + wiring absence + runtime smoke; else
  REFUSE the remove.
- `scripts/spring_dep_map.py --check` → `OK: spring-dep-to-extension.md n=…`
  (the only Spring→Quarkus map; JDBC `jdbc:hsqldb` is a cited row).

---
name: manage-quarkus-extensions
description: Before adding or removing a Quarkus extension on an M3 destination pom — inventory installed deps, search the RH platform catalog, and apply add/rm without rewriting the Red Hat BOM or claiming unused from compile alone
license: Apache-2.0
compatibility: Linux seat; Red Hat Quarkus platform; quarkus CLI optional
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - migration
    - quarkus
    category: migration
    kind: guidance
---
# Manage Quarkus extensions (M3)

Guidance only (R-SK.14). Does **not** replace persistence/JDBC/compile
preflight gates. Version **values** live in
`governance/contracts/tooling-pins.md` and the destination `pom.xml` — never
restate platform versions in this skill.

## When to Use

- Before the first `pom.xml` dependency change that adds a Quarkus extension
  for an M3 story (REST, JDBC, security, Flyway, Jacoco, …).
- When deciding whether an extension is **unused** and can be removed.
- When `quarkus ext ls` / Maven `quarkus:list` disagrees with what the story
  thinks is on the classpath.
- **Not** for project create / skeleton retirement — use
  `bootstrap-quarkus-project`.
- **Not** for Spring→Quarkus form mapping (`spring-to-quarkus-patterns`).

## Procedure

1. Read `references/rh-bom-and-mandatory-deps.md` (shared BOM policy + Jacoco
   gotcha). Confirm destination `quarkus.platform.*` matches
   `governance/contracts/tooling-pins.md` (or run
   `scripts/check-pom-platform-pins.py <root>`).
2. **Inventory** installed extensions:
   - Prefer: `quarkus ext ls` (inside the RH-pinned project).
   - Fallback: `mvn -q quarkus:list` via the Red Hat
     `quarkus-maven-plugin` from the pom (CLI absent / air-gap).
3. **Search** before inventing GAVs:
   - Prefer: `quarkus ext list --installable -s <term> --support-scope`
     (support-scope **column may be blank** on RH streams — still use RH
     versions; do not over-claim support metadata).
   - Fallback: Maven plugin list/search goals; never paste community
     `io.quarkus.platform` coords into an RH-pinned pom.
4. **Add** (inherits BOM version — never pin extension versions independently):
   - Prefer: `quarkus ext add <artifactId>`
   - Fallback: `mvn -q quarkus:add-extension -Dextensions="<artifactId>"`
   - After add: confirm `quarkus.platform.group-id` is still
     `com.redhat.quarkus.platform` (must not rewrite to
     `io.quarkus.platform`).
5. **Remove** only when the remove-unused BAR in
   `references/rh-bom-and-mandatory-deps.md` is met. Prefer **do not remove**
   when uncertain.
6. Refuse `quarkus-spring-*` compatibility extensions (native Quarkus only —
   AGENTS + `spring-to-quarkus-patterns`).

## Gotchas

- CLI without `registry.quarkus.redhat.com` **first** + Red Hat GA Maven
  reachability resolves community catalogs and may fail RH `-P` create.
- `--support-scope` values can be empty on RH platforms — do not treat blank
  as "unsupported".
- "Nothing imports it" is **not** unused on Quarkus (build-time wiring).
- Jacoco: adding `quarkus-jacoco` alone is incomplete — see shared reference.

## Verification

- `scripts/check-pom-platform-pins.py <root>` exits 0 with
  `OK: pom platform pins match tooling-pins.md`.
- After add/rm: `quarkus.platform.group-id` remains
  `com.redhat.quarkus.platform` and `quarkus.platform.version` still matches
  `tooling-pins.md` (no community rewrite).
- Removals: story notes cite inventory + wiring absence + runtime smoke; else
  REFUSE the remove.

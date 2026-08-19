# Destination Quarkus Constitution

Non-negotiable principles for this migration destination. Every `/speckit-*`
command consults this file; a plan's **Constitution Check must validate
against these articles by name** — a check that lists generic principles
instead is a failed check.

Version literals live in `.hermes/pins.json`. Do not invent GAVs.

## I. Red Hat Quarkus platform

The destination is a Quarkus application on the Red Hat build:
`com.redhat.quarkus.platform` BOM artifact `quarkus-bom` version
**3.27.3.SP1-redhat-00002** (see `.hermes/pins.json` `quarkus_platform`).
The Quarkus Maven plugin uses the same group/version. Foundation Jacoco /
Sonar wiring and extension coordinates come from that BOM import — never
from a community BOM and never from an invented version.

## II. Java 21

Compiler release is Java 21. The seat's default JDK may be older; shells
that compile or test must pin `JAVA_HOME` to Java 21 before `mvn`. Maven
has no wrapper — use `mvn`.

## III. Native layering

- Package root: `com.demo`.
- **Native Quarkus only** — never add `quarkus-spring-*` compatibility
  extensions (MTA may suggest them; reject).
- Default CDI scope for services and repositories: `@ApplicationScoped`.
- Prefer constructor injection; config via `@ConfigProperty` / `%profile`
  keys (or `QUARKUS_PROFILE`). Do not invent Spring-style
  `application-*.properties` trees on the destination.
- REST resources under `/api/`; JSON via Jackson; health at `/q/health`
  (`/q/*` sits outside the application root path).
- One `pom.xml` writer (foundation story) owns BOM, plugin, and the
  sorted-unique extension union. Later stories do not rewrite the POM
  structure.

## IV. Quality is an input

Tests ship with the code. Delivery bars: **zero new Sonar violations**,
**≥ 80% new-code line coverage**, **≤ 3% duplicated new lines**. Never
weaken tests or suppress rules to pass. The repository must build
self-contained from Maven Central and in-repo sources.

## V. Security

Constructor injection over field injection. Do not widen authz, disable
CSRF/auth, or add a permit-all fallback to make a test green. Persistence
and secrets stay in destination config — no credentials in Git. Reject
Spring Security compatibility extensions; map to Quarkus Security.

## VI. Performance and simplicity (YAGNI)

Build only what the spec and harvest require. Extra config classes,
wrapper DTOs, error taxonomies, and pre-flight probes of downstream
services the spec does not demand are complexity-tracking violations.
Hot-path work stays in native Quarkus APIs, not compatibility shims.

## VII. The legacy HTTP contract is immutable

Guidance for the planner (Architect `070430Z` — not a gate). Every HTTP
row in `evidence/entry-point-inventory.json` should be claimed by exactly
one story. The plan should not introduce a route absent from that
inventory. Additive endpoints (health, root `/`, documentation) are out
of scope. Do not treat a green `speckit-analyze` as route fidelity.
Plan-level enforcement is only
`assert-partition-invented-routes.py` (receipt endpoints vs inventory).
Compiled-tree drift (`.bak`) is `assert-compiled-route-fidelity.py`.

## Governance

- `.hermes/pins.json` is the version authority; this constitution names
  the stack so every native spec-kit command sees it as context.
- After `/speckit-tasks`, convert `tasks.md` into Hermes Kanban cards.
  **Never run `/speckit-implement`.** Run `specify workflow run speckit`
  so the project overlay removes `implement`.
- Phase acceptance criteria name the proving test in **that story's**
  write-set (T-8). An HTTP assertion is a `@QuarkusTest` there, not
  `curl`. Live HTTP acceptance is M4/M5.
- File-granular write ownership is assigned **after** story grouping
  exists: each destination file has exactly one owner story.
- Deviations from these articles must appear in the plan's Complexity
  Tracking table — silent deviations are review findings.

**Version**: 1.2.0 | **Ratified**: 2026-08-15 | **Last Amended**: 2026-08-19

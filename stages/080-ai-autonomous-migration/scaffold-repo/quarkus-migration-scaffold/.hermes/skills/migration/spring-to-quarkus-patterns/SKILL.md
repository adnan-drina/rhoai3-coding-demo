---
name: spring-to-quarkus-patterns
description: Before an M3 destination write — the required Quarkus form per Spring construct, and the parity it must prove
license: Apache-2.0
compatibility: Linux seat; guidance only, no scripts
metadata:
  author: rhoai3-harness-team
  version: "1.3.0"
  hermes:
    tags:
    - migration
    - quarkus
    category: migration
    kind: guidance
---
## When to Use

- Before the **first destination write** of an M3 story that ports a Spring
  construct: MVC controllers, `@ExceptionHandler` / advice classes, DI + config
  (`@Component`, `@Value`, `@Profile`, MapStruct), Spring Data or raw
  `JdbcTemplate` repositories, Spring Security config, Actuator health
  indicators, or Spring test slices.
- When a Quarkus counterpart looks **missing** — no advice-class annotation, no
  injectable `JdbcTemplate` bean, no framework error-body type. Each has a card;
  read it before declaring `dependency_wait` or a typed BLOCK.
- When the answer is drifting into a classpath/architecture essay or a
  javadoc-only shell — the `*-anti-essay` overlays exist for exactly that:
  cite, then write.
- Before `kanban_complete`, when the summary is about to name a technology
  (Panache, Quarkus security, "tests roll back") — the cards state what must
  appear in the diff to earn each claim.
- **Not** for authoring or validating story bodies (`check-spec-readiness`), and not
  for the Boot 2→3 precondition (`derive-legacy-boot3`).


# Spring → Quarkus patterns (IMPLEMENT)

Load for M3 HARVEST/REDESIGN *how* (AD-H §17 pri-5). Does **not** authorize
new behaviour, weaken G-1…G-4, or replace free-primitives / MTA.

## Invariants (conflict with AGENTS → AGENTS wins)

- **Native Quarkus only** — reject `quarkus-spring-*` compatibility extensions.
- Prefer **constructor injection**; default services/repos `@ApplicationScoped`.
  Prefer `@ApplicationScoped` over `@Singleton` when the type must be mockable
  in tests (`@Singleton` is not client-proxyable).
- Schema migrations: **Flyway** (or project-declared equivalent) — do not invent
  ad-hoc DDL on boot.
- Consult order: packet → brief → legacy RO → destination/`AGENTS.md` → this skill.

## References (progressive disclosure)

| File | Use when |
|------|----------|
| `references/rest-annotations.md` | JAX-RS / RESTEasy → `quarkus-rest` annotation map |
| `references/exception-mapping.md` | Local/global exception handlers; the advice-class gotcha; legacy error-body shape |
| `references/di-config.md` | Scopes, profiles, MapStruct `componentModel=cdi` (Phase-4 feedforward) |
| `references/persistence.md` | Spring Data → Panache **or** EntityManager (decide before claim) |
| `references/jdbc-anti-essay.md` | Raw `JdbcTemplate` on destination — write the Agroal/injection form, do not essay |
| `references/testing.md` | `@QuarkusTest` / REST Assured vs Spring test slices; **§Failure / Import / Mock procedures** + golden REST fixture path |
| `references/security-config.md` | A-bar security map + golden basic-authz (R-HX.13) |
| `references/security-anti-essay.md` | Write-first / anti-placeholder (synced from extensions) |
| `references/spring-compat-reject.md` | REJECT `quarkus-spring-*` — metadata shim ≠ Spring runtime (mechanism only) |
| `references/observability.md` | Actuator `HealthIndicator` → SmallRye `HealthCheck`; probe-type choice; fixed `/q/health*` paths |

## Source policy

- Prefer Apache-2.0 `quarkusio/skills` `migrate-spring-to-quarkus` wording for
  overlapping Full-path rows.
- Book citations are **locus only** (Deandrea et al., *Quarkus for Spring
  Developers*, 2021, Table/Ch) — paraphrased cards; **no** verbatim chapter
  paste or `tmp/` extract in this tree.
- Modernize names: `javax`→`jakarta`, RESTEasy Classic → `quarkus-rest` /
  `quarkus-rest-jackson` as used by this scaffold (RH BOM 3.27).


## Procedure

This skill carries no scripts — it is a consult-then-write contract.

1. **Consult order** before touching the destination: packet → brief → legacy RO
   → destination `AGENTS.md` → this skill. Conflicts resolve to AGENTS.
2. **Classify the construct**, then open only the References rows that match it.
   Overlays are additive and Hermes does not merge them: for `repository/jdbc/**`
   read the base skill **and** `references/jdbc-anti-essay.md`; for
   `security/**` read `references/security-config.md` **and**
   `references/security-anti-essay.md` — both before the first edit of that
   class.
3. **Preflight deps for that class** before sinking file writes (scripts live
   under the `check-spec-readiness` skill): `check-persistence-bom.py` /
   `check-compile-deps-preflight.py` ahead of entity/repository writes,
   `check-jdbc-deps-preflight.py` ahead of the first JDBC repository write.
   Security deps land in the same story as the security write, not a follow-up.
4. **Take the forced decisions before the claim**, not after: Panache repository
   vs injected `EntityManager`; automatic `@Valid` vs manual validation;
   `@Liveness` vs `@Readiness`. Each card names the failure that follows the
   wrong pick.
5. **Write one operand at a time** from checkpoint `next`, stamping after each
   successful destination write. Copy the golden fixtures rather than inventing:
   `governance/fixtures/security/golden-basic-authz/`,
   `governance/fixtures/testing/golden-rest-controller/`,
   `governance/fixtures/testing/golden-test-application.properties`.
6. **Run `mvn -q test-compile` in-loop** after test writes. Once a pattern is
   green in this task, copy it — do not restate the map per file.


## Verification

Verification here is the migrated code's provable parity, not a script exit.

- **Route + error parity** for each touched resource: valid request → expected
  2xx; invalid request matches the legacy contract on status, headers and body
  shape; one deliberately-triggered mapped exception returns its mapped status
  rather than a container-default 500.
- **Discovery, not just compile:** every `@Path` resource and every
  mapper-holding class carries an explicit CDI scope and sits outside the
  framework's own package prefix (build-time discovery skips it). A handler that
  compiles but never fires is the signature failure of this migration.
- **Runnable DB profile:** a clean checkout against an empty intended DB starts,
  `/q/health` answers, Flyway history + schema are present, a seeded-entity read
  succeeds, and a **second** start is idempotent. `schema-generation=none` with
  no schema owner is a BLOCK, not an accept.
- **Security, when touched:** destination tests prove 401 anonymous / 403 wrong
  role / 200 allowed, and
  `python3 .hermes/skills/gates/check-release-readiness/scripts/check-empty-security.py <tree>`
  does not flag the destination (it must still fail on
  `governance/fixtures/runnable-db-security/bad-placeholder-security/`).
- **Health, when touched:** the `/q/health` payload names **every** check
  migrated from a legacy indicator; `/q/health/live` and `/q/health/ready` both
  resolve; a dependency-backed check reports DOWN under readiness.
- **Claim accuracy:** no `quarkus-spring-*` extension in `pom.xml`, and every
  technology named in the completion summary is visible in the diff — "Panache",
  "Quarkus security" and "tests roll back" each require their types or
  annotations to be present.

---
name: spring-to-quarkus-patterns
description: Before an M3 destination write — the required Quarkus form per Spring construct, and the parity it must prove
license: Apache-2.0
compatibility: Linux seat; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.5.0"
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
  read it before declaring `dependency_wait` or a typed BLOCK. JDBC
  repositories are retired on this specimen (ADR-004).
- When the answer is drifting into a classpath/architecture essay or a
  javadoc-only shell — the `*-anti-essay` overlays exist for exactly that:
  cite, then write.
- Before `kanban_complete`, when the summary is about to name a technology
  (Panache, Quarkus security, "tests roll back") — the cards state what must
  appear in the diff to earn each claim.
- **Not** for authoring or validating increment bodies (K1 `k1_validate.py`), and not
  for the Boot 2→3 precondition (`derive-legacy-boot3`).


# Spring → Quarkus patterns (IMPLEMENT)

Load for M3 HARVEST/REDESIGN *how* (AD-H §17 pri-5). Does **not** authorize
new behaviour, weaken G-1…G-4, or replace free-primitives / MTA.

## Invariants (conflict with AGENTS → AGENTS wins)

- **Spring-compatibility path first** (ADR-001): the `quarkus-spring-*` extensions are the baseline; keep Spring annotations the compat guides support, and go native only where a guide documents no support (no Spring `ApplicationContext`: `@Conditional`, `@Profile`, `BeanPostProcessor`, `@Import`, `@Autowired(required=false)`, `Set`/`Map` injection; Spring Boot test features → `@QuarkusTest` + RestAssured).
- Prefer **constructor injection**; default services/repos `@ApplicationScoped`.
  Prefer `@ApplicationScoped` over `@Singleton` when the type must be mockable
  in tests (`@Singleton` is not client-proxyable).
- Schema migrations: **Flyway** (or project-declared equivalent) — do not invent
  ad-hoc DDL on boot.
- Consult order: packet → brief → legacy RO → destination/`AGENTS.md` → this skill.

## References (progressive disclosure)

| File | Use when |
|------|----------|
| `references/rest-annotations.md` | JAX-RS / RESTEasy → `quarkus-rest` annotation map; Location via a request-aware `@Context UriInfo` builder (never an introduced checked exception) |
| `references/exception-mapping.md` | Local/global exception handlers; the advice-class gotcha; legacy error-body shape |
| `references/di-config.md` | Scopes, profiles, MapStruct (doctrine pending R-SKILL-F; do not mandate `componentModel=cdi`) |
| `references/persistence.md` | Entity / tx / schema cards; this specimen's default is Spring Data JPA (ADR-004) |
| `references/spring-data-jpa.md` | Supported subset, unsupported methods, one-repository batching; official Quarkus Spring Data JPA guide |
| `references/transitive-supporting-types.md` | Partitioned DTO/mapper closure — supporting types decision (R-SKILL-A) |
| `references/jdbc-anti-essay.md` | Raw `JdbcTemplate` on destination — write the Agroal/injection form, do not essay |
| `references/testing.md` | `@QuarkusTest` / REST Assured vs Spring test slices; **§Failure / Import / Mock procedures** + golden REST fixture path |
| `references/security-config.md` | A-bar security map + declarative props vs Java identity (R-SKILL-B) |
| `references/security-anti-essay.md` | Write-first / anti-placeholder (synced from extensions) |
| `references/cache-adopt-defer.md` | `@Cacheable` → `@CacheResult` adopt/defer (R-SKILL-C) |
| `references/cdi-service-facade.md` | `@Service` → CDI ctor inject / `@Transactional` / `readOnly` (R-SKILL-D) |
| `references/spring-compat-reject.md` | Historical (native-only era): what the compat shim does **not** provide — read it as the list of features that must go native |
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

This skill's write contract is consult-then-write. W6 bootstrap is a
**check**, not an essay: `scripts/assert-no-trivial-quarkusmain.py`.

1. **Consult order** before touching the destination: packet → brief → legacy RO
   → destination `AGENTS.md` → this skill. Conflicts resolve to AGENTS.
2. **Classify the construct**, then open only the References rows that match it.
   Overlays are additive and Hermes does not merge them: for `repository/jdbc/**`
   read the base skill **and** `references/jdbc-anti-essay.md`; for
   `security/**` read `references/security-config.md` **and**
   `references/security-anti-essay.md` — both before the first edit of that
   class.
3. **Preflight deps for that class** before sinking file writes: under DD3
   (declare/apply/own / W5): **declare** needed Quarkus extensions on
   `identity.extensions_declared` and own config/SQL in **this** write-set.
   Do **not** write `pom.xml` unless this story is the sole pom writer.
   The pom writer applies `identity.extensions_apply` via
   `manage-quarkus-extensions`. Do **not** call retired
   `check-persistence-bom.py` / `check-compile-deps-preflight.py`.
   Still run `check-jdbc-deps-preflight.py` ahead of the first JDBC repository
   write when that path applies. Security deps land in the same story as the
   security write, not a follow-up.
4. **Take the forced decisions before the claim**, not after: this specimen
   keeps Spring Data JPA (ADR-004) inside the supported subset; reach for
   `@Inject EntityManager` only when that subset cannot express the query.
   Panache is not the default. Also: automatic `@Valid` vs manual validation;
   `@Liveness` vs `@Readiness`. Each card names the failure that follows the
   wrong pick.
5. **Write one operand at a time** from checkpoint `next`, stamping after each
  successful destination write. Copy the golden fixtures rather than inventing:
  `.hermes/skills/migration/spring-to-quarkus-patterns/fixtures/golden/security/golden-basic-authz/`,
  `.hermes/skills/migration/spring-to-quarkus-patterns/fixtures/golden/testing/golden-rest-controller/`,
  `.hermes/skills/migration/spring-to-quarkus-patterns/fixtures/golden/testing/golden-test-application.properties`.
6. **Run `mvn -q test-compile` in-loop** after test writes. Once a pattern is
   green in this task, copy it — do not restate the map per file.
7. **Bootstrap:** if the legacy `@SpringBootApplication` main only calls
   `SpringApplication.run`, do **not** add dest `@QuarkusMain` (Quarkus
   generates main). Run
   `python3 .hermes/skills/migration/spring-to-quarkus-patterns/scripts/assert-no-trivial-quarkusmain.py`
   on the destination (idle when dest has no `@QuarkusMain`).
   `StartupEvent` / `QuarkusApplication` only when the legacy main has
   custom startup (`CommandLineRunner` / `@PostConstruct` / extra main body).


## Pitfalls

- Adding a `quarkus-spring-*` extension that `compat-mapping.json` does not
  list, or expecting Spring runtime infrastructure (context, conditions,
  post-processors) to exist under the shim.
- Translating Spring Boot properties by supplementation; Quarkus does not
  auto-map them — replace keys explicitly.
- Inventing specimen-specific type names in skill prose (R-SK.5).
- Emitting `@QueryParam(defaultValue=…)` — Spring leftover. JAX-RS is
  `@QueryParam` plus a separate `@DefaultValue` (`references/rest-annotations.md`
  `rest-query-default`).
- Wrapping a trivial `SpringApplication.run` main as dest `@QuarkusMain`
  (`assert-no-trivial-quarkusmain.py` REFUSE).

## Verification

Verification here is the migrated code's provable parity, not a script exit
except the W6 bootstrap check:

- **Bootstrap:** `scripts/assert-no-trivial-quarkusmain.py` exit 0 (idle or
  custom legacy startup). dest `@QuarkusMain` on a trivial Boot wrapper is
  REFUSE (`TRIVIAL_QUARKUSMAIN`).

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
  does not flag the destination.
- **Health, when touched:** the `/q/health` payload names **every** check
  migrated from a legacy indicator; `/q/health/live` and `/q/health/ready` both
  resolve; a dependency-backed check reports DOWN under readiness.
- **Claim accuracy:** only catalog-mapped `quarkus-spring-*` extensions in `pom.xml`, and every
  technology named in the completion summary is visible in the diff — "Panache"
  (not the default here), "Quarkus security" and "tests roll back" each require
  their types or annotations to be present. A "Spring Data" claim on this
  specimen is the ADR-004 path (`quarkus-spring-data-jpa`), not a Panache rewrite.

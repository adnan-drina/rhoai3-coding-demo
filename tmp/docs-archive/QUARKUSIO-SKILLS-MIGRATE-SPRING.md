# quarkusio/skills `migrate-spring-to-quarkus` — harness notes

Written 2026-07-29. **Analysis only — no scaffold changes.**  
Umbrella backlog: [SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md](SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md).

**Source (cloned):** [quarkusio/skills](https://github.com/quarkusio/skills)  
Local: `tmp/quarkusio-skills/`  
Focus skill: [`migrate-spring-to-quarkus`](https://github.com/quarkusio/skills/tree/main/skills/migrate-spring-to-quarkus)  
(Also present: `quarkus-update` — Quarkus version/build freshness; wrong job for Spring→Quarkus, same class as OpenRewrite upgrade aggregates.)

Official README note: work in progress; use at your own risk.

## 1. What it is

An **agent skill** (not OpenRewrite, not MTA) that drives an interactive,
modular, **gate-driven** Spring Boot → Quarkus migration:

| Piece | Role |
|---|---|
| `SKILL.md` | Critical rules, strategy choice, module gates, verify checklist, migration report |
| `modules/*` | jdk, build (maven/gradle), code, frontend, testing, cleanup, git |
| `references/annotation-map.md` | Spring → Full Quarkus vs Compat columns (DI, REST, Data, Security, Cache, Scheduling, Testing, Lifecycle) |
| `references/config-map.md` | Spring Boot property → Quarkus property (server, datasource, JPA, Flyway, logging, profiles, CORS, cache, security, actuator, static, Thymeleaf, Cloud Config) |
| `references/dependency-map.md` | Starters → Full vs Compat extensions (includes modern **`quarkus-rest`**) |

Our MAPPINGS already cites an earlier harvest of this annotation map
(2026-07). This review is of the **current** upstream skill as cloned.

## 2. Process vs our harness

| quarkusio skill | Stage 080 harness | Fit |
|---|---|---|
| Interactive: analyze → **ask user** compat vs full | Autonomous M1–M5; strategy decided by platform (`targetContract`, native policy) | Process conflict — do not adopt ask-user loop |
| **Recommends Spring compatibility** as default | Native-only; reject `quarkus-spring-*` | Policy conflict |
| In-place transform of the Spring project | Side-by-side scaffold + harvest | Architecture conflict |
| Community `io.quarkus.platform` BOM in build module | RH `com.redhat.quarkus.platform` 3.27.3.SP1 | BOM conflict |
| Compile after each module; leave `// TODO: Migration required` | Sensors + debt.md; no “TODO in src as done” | Different honesty model — closer to our `debt.md` than to shipping TODOs |
| Gate table: jdk / build / code / frontend / testing / cleanup | M1 inventory + story gates + sensors | **Conceptual** similarity; keep our gates |
| Verify: package, no Spring deps, Quarkus present, tests, `/q/health` | `sensors.sh` + factory + acceptance | Aligns in spirit |
| Migration report + skill improvement suggestions | `retro-proposals.md` / run-log | Aligns in spirit |
| JDK **21+** hard stop | Java 21 | **Aligned** |
| Optional git branch + draft PR workflow | Outer loop commits; factory is merge authority | Different CI model |

**Verdict on process:** treat as a **reference catalog + module checklist
idea**, not as a replacement orchestrator. Lock strategy to **Full
Quarkus** columns only.

## 3. Reference files — what to borrow

### 3.1 `annotation-map.md` — highest value

Richer than our current MAPPINGS extended Spring catalog. Full-migration
column is the authority for enrichment; Compat column is documentation of
what MTA/skills may suggest and we must **not** take.

Notable Full-path rows we should capture later (when implementing docs
enrichment):

| Area | Useful Full-migration content |
|---|---|
| DI | `@Primary` → `@DefaultBean` / `@Alternative`+`@Priority`; `@Conditional*` → `@IfBuildProfile` / `@LookupIfProperty`; SpEL in `@Value` **not** supported |
| REST | `@RestPath`/`@RestQuery`/`@RestHeader`/`@RestCookie` aliases; `@CrossOrigin` → `quarkus.http.cors.*`; one global advice limitation called out for compat |
| Data | PanacheRepository vs active record; `@Transactional` Spring attrs vs Jakarta `TxType`; SpEL in `@Query` unsupported |
| Scheduling | `fixedDelay` unsupported in compat; property placeholder `{...}` vs `${...}` |
| Security | `@RolesAllowed`; limited `@PreAuthorize` expressions; `@AuthenticationPrincipal` → `SecurityIdentity` |
| Cache | `@CacheResult` / `@CacheInvalidate` / `@CacheInvalidateAll` |
| Testing | `@InjectMock` package move (3.2+); `@TestProfile`; `@TestHTTPResource` |
| Lifecycle | `CommandLineRunner` → `@Observes StartupEvent`; `@EventListener` → `@Observes` |

**Conflict to keep ours:** prefer `@ApplicationScoped` (book + us) even
where compat maps stereotypes to `@Singleton`. Skill Full column already
uses `@ApplicationScoped` for `@Component`/`@Service`/`@Repository`.

**Conflict:** skill shows Panache **active record** as primary entity
AFTER example; we prefer EntityManager/Flyway or Panache**Repository**.
Borrow repository pattern; do not make active record the default.

### 3.2 `config-map.md` — high value (fills book gap on Flyway)

Especially useful vs our prior sources:

| Topic | Why it matters for us |
|---|---|
| Flyway property map (`spring.flyway.*` → `quarkus.flyway.*`) | Book omitted Flyway; this maps it |
| `%prod.` on datasource URLs for Dev Services | Good guidance; reconcile with factory/prod profiles |
| **Naming strategy warning** (Spring snake_case vs Quarkus preserve names) | Easy silent breakage — belongs in persistence skill / MAPPINGS |
| `ddl-auto=update` → `database.generation=update` | Document as Spring map only; **our law remains `validate` + Flyway** |
| Actuator paths → `/q/health`, `/q/metrics` | Reinforces acceptance/health |
| Static resources → `META-INF/resources/` | UI surface / acceptance root |
| Qute strict-rendering vs Thymeleaf silent missing vars | Frontend BYO |
| CORS via properties | REST skill |

### 3.3 `dependency-map.md` — high value, already modern

Full column uses **`quarkus-rest`** (not RESTEasy Classic) — closer to our
scaffold than the 2021 book. Keep Full column; reject Compat column for
destination. Note actuator → health+micrometer (we have both).

### 3.4 Modules — selective ideas only

| Module idea | Borrow? |
|---|---|
| Gate-before-execute per concern | Already have stronger M-process gates |
| Compile after each phase | Similar to sensors; keep Maven **clean** + isolated repo |
| Frontend Thymeleaf→Qute module | BYO / plan-lint UI surface |
| Cleanup: grep leftover `org.springframework` | Good M5 / preflight idea |
| “Never delete code you cannot migrate” → TODO comments | Prefer **`migration/debt.md`** over shipping TODOs in `src/main` |
| Simplify interface+impl services | Optional style note; don’t force — can fight HARVEST fidelity |

## 4. Recommendations (proposed — not authorized)

Add to the umbrella Tier A when implementing guide enrichment:

1. **Diff `annotation-map.md` Full column → MAPPINGS** — fill gaps
   (`@Primary`, `@Conditional*`, cache annos, StartupEvent,
   InjectMock package, CORS, PreAuthorize limits, Query SpEL ban).
2. **Import Flyway + naming-strategy + `%prod` datasource notes** from
   `config-map.md` into MAPPINGS / `quarkus-persistence-conventions`
   (keeping `validate`, not `update`).
3. **Align dependency starter table** with `dependency-map.md` Full
   column (`quarkus-rest`, not resteasy-*).
4. **Optional:** cleanup gate “no `org.springframework` imports in
   src/main” as a sensor or preflight check.
5. **Do not** install this skill as the stage 080 orchestrator, recommend
   compat, or rewrite destination pom to community BOM.
6. **Do not** treat `quarkus-update` as part of Spring migration (separate
   concern).

## 5. Relationship to other review sources

| Source | Overlap with this skill |
|---|---|
| Red Hat book | Same native thesis; skill maps are more current (`quarkus-rest`, Flyway, InjectMock) |
| OpenRewrite | Skill is agent procedure + tables; OpenRewrite is AST recipes — complementary |
| Main Thread blog | Same Full-path examples; skill is more complete |
| Snowdrop | Skill’s gates ≈ richer module gates; Snowdrop’s rule-card schema still useful for MAPPINGS formatting |

## 6. Bottom line

`quarkusio/skills` `migrate-spring-to-quarkus` is the **best living
annotation/config/dependency catalog** we reviewed for Full Quarkus
migration, and it already partially feeds MAPPINGS. Use its **Full**
reference columns to enrich guides later. Reject its **default compat
strategy**, interactive stop-and-ask loop, in-place community-BOM build
rewrite, and TODO-in-source honesty model in favor of our native,
scaffold-based, sensor + `debt.md` harness.

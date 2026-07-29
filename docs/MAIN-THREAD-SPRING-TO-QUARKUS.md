# Markus Eisele Spring→Quarkus walkthrough — harness notes

Written 2026-07-29. Lightweight notes — analysis only. Umbrella backlog:
[SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md](SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md).

**Source:**
[Modernizing Your Stack: Migrating a Spring Boot App to Quarkus Step-by-Step](https://www.the-main-thread.com/p/spring-to-quarkus-migration-guide)
(Markus Eisele, 2025-05-28).

Hands-on tutorial for a small Spring Boot app (REST + JPA/PostgreSQL +
`application.properties` + `@SpringBootTest`) rewritten onto Quarkus
native APIs. Community BOM example (`io.quarkus.platform` 3.23.0). Ends
by recommending the Spring compatibility layer as an incremental aid —
that recommendation conflicts with our native-only policy.

## Already aligned (no change needed)

These steps match decisions we already encode in the scaffold / MAPPINGS /
OpenCode skills:

| Blog step | Our equivalent |
|---|---|
| Scaffold Quarkus before porting code | Side-by-side destination scaffold |
| Extensions replace starters; platform BOM | Scaffold `pom.xml` + RH BOM 3.27.3.SP1 |
| `@RestController`/`@GetMapping` → `@Path`/`@GET` | MAPPINGS + `quarkus-rest-conventions` |
| Spring datasource keys → `quarkus.datasource.*` | MAPPINGS properties row |
| `@ConfigurationProperties` → `@ConfigMapping` | MAPPINGS extended catalog |
| `@SpringBootTest` → `@QuarkusTest` + RestAssured | `project-test-standards` |
| Models/repos before (or with) REST surfaces | M2 dependency-order / story cuts |

## What to borrow

### 1. Concrete BEFORE/AFTER property map (MAPPINGS / rule cards)

The datasource rewrite is a clear card we can paste into MAPPINGS (or a
Snowdrop-style rule card) for DB stories:

| Spring | Quarkus |
|---|---|
| `spring.datasource.url` | `quarkus.datasource.jdbc.url` (+ `quarkus.datasource.db-kind`) |
| `spring.datasource.username` / `password` | `quarkus.datasource.username` / `password` |

Useful when `needsDatabase: true`; cart (stateless) does not need it today.

### 2. Persistence target nuance (MAPPINGS + persistence skill)

Blog default: **Panache active record** (`extends PanacheEntity`).
Also mentions `PanacheRepository<T>`.

Our skill: Flyway owns schema; Hibernate `validate`; constructor-inject
`EntityManager` **or** Panache repositories — never field injection;
never `drop-and-create` in the factory path.

**Borrow:** when a story chooses Panache, prefer **`PanacheRepository`**
(matches MAPPINGS `JpaRepository` → `PanacheRepository`) over active
record for service-layer separation. Keep Flyway + `validate` as law —
do not adopt the blog's `database.generation=drop-and-create` example.

### 3. Test ladder wording (`project-test-standards`)

Blog distinguishes:

- `@QuarkusTest` — in-process, Dev Services / Testcontainers for DB
- `@QuarkusIntegrationTest` — tests the **built artifact** (jar / native / image)

**Borrow:** one short note in test standards that deploy / M5 acceptance
stories may use `@QuarkusIntegrationTest` when proving the packaged app,
while ordinary HTTP coverage stays `@QuarkusTest`. Do not weaken the
"plain JUnit for services" rule.

### 4. Story narrative order (briefs / PLANNING)

Blog order: scaffold → dependencies/extensions → JPA → REST → config →
tests. Close to our conversion graph; the useful phrasing for briefs is
**"extensions and BOM first, then persistence types, then resources,
then config keys, then tests"** — already implied by dependency-order,
worth stating once in PLANNING if agents still invent pom/test-first
tasks.

## Do not borrow

| Blog guidance | Why not |
|---|---|
| Spring Compatibility Layer as the recommended incremental path | Same REJECT as OpenRewrite compat / MAPPINGS native-only |
| Field injection as acceptable | Sonar + our REST/persistence skills require constructor injection |
| `hibernate-orm.database.generation=drop-and-create` | Factory contract is Flyway + `validate` |
| Community BOM / "latest" Quarkus | Pin RH `3.27.3.SP1-redhat-00002` |
| Panache active record as the default entity style | Optional; repository or EntityManager preferred for this harness |

## Suggested enrichment targets (when implementing)

| Target | Change |
|---|---|
| `MAPPINGS.md` | Add Spring→Quarkus datasource property table; clarify PanacheRepository over PanacheEntity |
| `quarkus-persistence-conventions.md` | Explicit "no drop-and-create; blog-style Dev Services OK in `@QuarkusTest` only" |
| `project-test-standards.md` | Mention `@QuarkusIntegrationTest` for packaged-artifact checks |
| `PLANNING.md` | One line on extension→model→resource→config→test ordering |

## Related

| Document | Relation |
|---|---|
| [OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md](OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md) | Recipe-level adopt/adapt/reject |
| [SNOWDROP-SPRINGBOOT-TO-QUARKUS-GUIDE.md](SNOWDROP-SPRINGBOOT-TO-QUARKUS-GUIDE.md) | Rule-card schema + M1 preflights |
| Stage 080 `MAPPINGS.md` / OpenCode skills | Live enrichment targets |
| Upstream article | https://www.the-main-thread.com/p/spring-to-quarkus-migration-guide |

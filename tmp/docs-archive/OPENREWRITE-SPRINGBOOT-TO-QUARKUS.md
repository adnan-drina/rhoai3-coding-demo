# OpenRewrite Spring→Quarkus — harness alignment assessment

Written 2026-07-29. Analysis only — nothing here is implemented unless a
follow-up change lands it in the scaffold. Umbrella backlog:
[SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md](SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md).
Grounded in:

- Catalog index: [Spring to Quarkus](https://docs.openrewrite.org/recipes/quarkus/spring)
- Composite: [Migrate Spring Boot to Quarkus](https://docs.openrewrite.org/recipes/quarkus/spring/springboottoquarkus)
  (`org.openrewrite.quarkus.spring.SpringBootToQuarkus`, artifact
  `org.openrewrite.recipe:rewrite-spring-to-quarkus:0.10.3`)
- Stage 080 harness under
  `stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/`
  (destination: Red Hat Quarkus **3.27.3.SP1**,
  `com.redhat.quarkus.platform:quarkus-bom:3.27.3.SP1-redhat-00002`)

**Out of scope for this migration path:** Quarkus version-upgrade
aggregates such as
[MigrateToQuarkus_v3_26_0](https://docs.openrewrite.org/recipes/quarkus/migratetoquarkus_v3_26_0)
— those upgrade apps that already depend on `quarkus-core` (&lt; 3.26.0).
They are not Spring Boot → Quarkus recipes, and our scaffold is already
past 3.26.

## 1. Verdict

Align with a **curated subset** of `SpringBootToQuarkus` — not the full
composite.

The composite optimizes for **in-place** Spring Boot **3.x** → community
Quarkus, and it bundles `AddSpringCompatibilityExtensions`
(`quarkus-spring-di`, `quarkus-spring-web`,
`quarkus-spring-boot-properties`). Our harness is the opposite shape:

- side-by-side legacy (read-only) + Quarkus **destination scaffold**
- Red Hat platform BOM (`com.redhat.quarkus.platform`)
- **native** CDI / JAX-RS — MAPPINGS explicitly rejects `quarkus-spring-*`
  compat ("compat hides the migration")
- M1 recipe stage today runs **only**
  `JavaxMigrationToJakarta`; Spring Boot mappings are mostly
  rewrite/infer tasks

The OpenRewrite page is strongest as a **recipe catalog and ordering
reference** for expanding M1's mechanical share.

## 2. What the composite does vs what we do today

| OpenRewrite `SpringBootToQuarkus` | Stage 080 harness today |
|---|---|
| In-place transform of a Spring Boot 3.x module | Side-by-side: legacy → harvest into Quarkus scaffold |
| Adds `io.quarkus.platform:quarkus-bom` | Scaffold already on Red Hat `com.redhat.quarkus.platform` |
| Runs ~25 sub-recipes, including Spring compat extensions | M1 `recipe-transform.sh` runs only jakarta OpenRewrite |
| `SpringApplication.run` → `Quarkus.run` | MAPPINGS: **delete** main / `@SpringBootApplication` |
| Mechanical DI / Web / Value / Config / Test transforms | Mostly infer/rewrite tasks citing manual MAPPINGS tables |
| Precondition: `org.springframework.boot:spring-*` **3.x** | Demo cart-class apps may be Boot 2.x — composite may not fire |

Recipe list (from the upstream YAML definition):

1. Add managed Maven dependency (`io.quarkus.platform:quarkus-bom`)
2. Add or replace Spring Boot build plugin with Quarkus build plugin
3. Migrate database drivers to Quarkus JDBC extensions
4. Replace Spring Boot starter dependencies with Quarkus equivalents
5. Replace `SpringApplication.run()` with `Quarkus.run()`
6. Replace `@SpringBootApplication` with Quarkus equivalent
7. Migrate `@EnableXyz` annotations to Quarkus extensions
8. **Add Spring compatibility extensions for commonly used annotations**
9. Convert Spring `ResponseEntity` to JAX-RS `Response`
10. Migrate Spring annotations to CDI
11. Replace Spring `@Value` with CDI `@ConfigProperty`
12. Convert Spring Web annotations to JAX-RS
13. Remove Spring Boot 3.x parent POM
14. Migrate Spring Validation to Quarkus
15. Migrate Spring Boot Actuator to Quarkus Health and Metrics
16. Migrate Spring Boot Testing to Quarkus Testing
17. Migrate `@ConfigurationProperties` to Quarkus `@ConfigMapping`
18. Migrate Spring `@Transactional` to Jakarta `@Transactional`
19. Migrate Spring Events to CDI Events
20. Migrate JPA Entities to Panache Entities
21. Migrate Spring Data MongoDB to Quarkus Panache MongoDB
22. Migrate Spring Cloud Config Client to Quarkus Config
23. Migrate Additional Spring Web Parameter Annotations
24. Migrate Spring Cloud Service Discovery to Quarkus
25. Remove Spring Boot DevTools
26. Customize Quarkus BOM Version

## 3. Policy conflicts — do not adopt blindly

| Conflict | Detail |
|---|---|
| `AddSpringCompatibilityExtensions` | Adds `quarkus-spring-di` / `quarkus-spring-web` / `quarkus-spring-boot-properties` when Spring annotations remain. Direct contradiction of MAPPINGS Windup joins (`springboot-di-to-quarkus-`, `springboot-web-to-quarkus-`, `springboot-properties-to-quarkus-`: native, NOT the spring-* extensions). |
| Main class strategy | OpenRewrite keeps/`Quarkus.run`; harness deletes `@SpringBootApplication` + main. |
| BOM ownership | Community `io.quarkus.platform` + CustomizeQuarkusVersion fights the RH BOM already in the scaffold. |
| Boot 3.x precondition | Composite may no-op on Boot 2.x legacy inputs. Invoke named sub-recipes, or gate on Boot major, if adopting recipe execution. |
| Architecture | Pom-rewriting recipes assume the Spring module *becomes* Quarkus. We keep destination pom as scaffold truth; staging is for **source** transforms harvest can pull. |

## 4. Sub-recipe → harness benefit matrix

### 4.1 High value — promote to M1 `recipe:` (deterministic)

Match our native-Quarkus MAPPINGS. Candidates for a curated staging pass
(sources-focused; skip or post-filter pom/BOM steps).

| OpenRewrite sub-recipe | Aligns with | Harness effect |
|---|---|---|
| `StereotypeAnnotationsToCDI` | `@Service`/`@Component`/`@Autowired` → CDI | Reclassify `springboot-di-to-quarkus-` infer→recipe where safe |
| `WebToJaxRs` + `MigrateRequestParameterEdgeCases` | Spring Web → JAX-RS | Same for `springboot-web-to-quarkus-` |
| `ValueToCdiConfigProperty` | `@Value` → `@ConfigProperty` | Extended Spring catalog → recipe |
| `MigrateConfigurationProperties` | `@ConfigurationProperties` → `@ConfigMapping` | Extended catalog |
| `MigrateSpringTransactional` | Spring → Jakarta `@Transactional` | Persistence path |
| `MigrateSpringEvents` | Spring events → CDI `@Observes` | Already decided for in-process pub/sub |
| `ResponseEntityToJaxRsResponse` | Spring MVC response → JAX-RS | REST conventions |
| `MigrateSpringValidation` | Bean Validation → Quarkus/Hibernate Validator | Supports `targetContract.validateInput` |
| `MigrateSpringTesting` (with care) | `@SpringBootTest` → `@QuarkusTest` | `project-test-standards` |
| `MigrateSpringActuator` (health path) | Actuator → SmallRye Health | Already rewrite for actuator |

### 4.2 Medium value — guidance alignment only

Keep as rewrite/infer tasks, or selective recipes that do not fight the
scaffold.

| Sub-recipe | Why not full auto on staging |
|---|---|
| `MigrateBootStarters` / `MigrateMavenPlugin` / `RemoveSpringBootParent` | Destination scaffold owns pom; use as catalog truth for plan packets |
| `MigrateDatabaseDrivers` / `MigrateEntitiesToPanache` | Cart is DB-less; Panache vs EntityManager is `quarkus-persistence-conventions`' call — don't force Panache |
| `EnableAnnotationsToQuarkusDependencies` | Useful dependency adds; must not pull spring-* compat |
| Mongo / Cloud Config / Service Discovery / DevTools | Out of cart demo scope; good MAPPINGS rows for bring-your-own-app |

### 4.3 Reject / explicitly exclude

| Sub-recipe | Why |
|---|---|
| `AddSpringCompatibilityExtensions` | Contradicts native-only policy |
| Full `SpringBootToQuarkus` composite as-is | Bundles compat + wrong BOM/main strategy |
| Unconditional `MigrateEntitiesToPanache` | May conflict with EntityManager + Flyway validate conventions |

## 5. Which harness components benefit

Ranked for enrichment when adopting the curated subset.

| Component | Path | Benefit |
|---|---|---|
| **MAPPINGS.md** | `.hermes/skills/migration-harness/MAPPINGS.md` | Expand "Deterministic (OpenRewrite)" with curated `rewrite-spring-to-quarkus` recipes; document exclusions; reclassify Windup joins; update discover command to that artifact |
| **recipe-transform.sh** + inventory join | `.hermes/harness/recipe-transform.sh`, `findings-inventory.py` | Second recipe pass after jakarta: selected Spring→native recipes on staging; log resolved rule ids |
| **PLANNING.md / EXECUTION.md** | migration-harness skill | More files become true HARVEST; packets cite staging; fewer open-ended DI/Web infer tasks |
| **ANALYSIS.md §7 / BRIEF-TEMPLATE** | migration-harness skill | REDESIGN shrinks to behavior/`targetContract`; HARVEST grows for annotation-only classes |
| **OpenCode Quarkus skills** | `.opencode/skills/quarkus-rest-conventions.md`, `project-test-standards.md` | Match post-recipe shapes so workers don't re-litigate transforms |
| **plan-lint / findings-inventory** | `.hermes/harness/` | Accept recipe-resolved Spring rules the way jakarta rules are accepted today |
| **Sensor FIX / harvest-fidelity** | `sensors.sh`, `harvest-fidelity.py` | After Spring recipes, fidelity must allow the approved annotation-swap transform set |

Lower priority for this source: `outer-loop.sh`, `supervisor.sh` (orchestration unchanged), `SHIPPING.md`, constitution (unless skill law references new recipes).

## 6. Recommended alignment strategy

1. **Do not** wire `org.openrewrite.quarkus.spring.SpringBootToQuarkus` as a single M1 recipe.
2. **Do** define a harness-owned recipe list in MAPPINGS (e.g. "Spring→native staging set") that excludes compat / BOM / main-run recipes. Prefer picking recipes from the [Spring to Quarkus catalog](https://docs.openrewrite.org/recipes/quarkus/spring) individually rather than the umbrella composite.
3. **Gate** on Spring Boot major, or invoke named sub-recipes without the composite's 3.x precondition.
4. **Keep** jakarta recipe first; then Spring source recipes on the same staging tree.
5. **Leave** pom/BOM/plugin ownership with the scaffold + rewrite tasks (or a carefully filtered starter recipe that does not import the community BOM).
6. **Validate on cart** before promoting Windup joins from `infer`→`recipe` — especially DI/Web, which today stay infer so packets carry constructor-injection and `/api/` decisions.
7. When choosing Web starter recipes, prefer **Quarkus REST**
   (`Replace Spring Boot Web with Quarkus REST`) over RESTEasy Classic —
   the scaffold already depends on `quarkus-rest-jackson`.

## 7. Standing recommendations (keep until implemented)

Operational notes agreed 2026-07-29 — do not lose these when implementing:

1. Treat this document as the **contract** before changing
   `recipe-transform.sh`. High-value wins are **source** transforms
   (CDI, JAX-RS, `@Value`, validation, testing) — not the full composite.
2. **Validate on cart** before promoting Windup joins `infer` → `recipe`.
   DI/Web staying infer today is intentional so packets carry constructor
   injection and `/api/`; a staging dry-run must prove harvest-fidelity
   still green.
3. **Pin versions explicitly** (`rewrite-maven-plugin` +
   `rewrite-spring-to-quarkus`), same pattern as the jakarta recipe line
   in MAPPINGS — avoid floating `RELEASE` tags in the harness.
4. **Treat Boot major as a gate.** If cart (or other demos) are Boot 2.x,
   invoke named sub-recipes; do not rely on the composite's 3.x
   precondition.
5. **Leave RH BOM / main-delete / no-compat as hard exclusions** in
   MAPPINGS so a future "just run SpringBootToQuarkus" change cannot
   regress the native policy.
6. Next enrichment pass that may matter more than OpenRewrite: official
   Quarkus / MTA product guidance into MAPPINGS + OpenCode skills when
   that material is ready.

## 8. Suggested enrichment order (implementation follow-up)

Not done in this document — tracked for a future change:

1. Draft adopt / adapt / reject rows into `MAPPINGS.md` with proposed `recipe:` join lines (use §9 as the catalog checklist).
2. Extend `recipe-transform.sh` to run the curated list (pin plugin + `rewrite-spring-to-quarkus` versions).
3. Reclassify Windup joins only after a cart staging dry-run proves harvest-fidelity green.
4. Align OpenCode REST/test skills with post-recipe annotation shapes.
5. Update discover snippet in MAPPINGS to include `rewrite-spring-to-quarkus`.

## 9. Full catalog evaluation — Spring to Quarkus index

Source: [docs.openrewrite.org/recipes/quarkus/spring](https://docs.openrewrite.org/recipes/quarkus/spring)
(composite recipes + individual recipes). Classification relative to the
stage 080 harness (native CDI/JAX-RS, RH BOM 3.27.3.SP1, side-by-side
scaffold, cart demo is DB-less / Feign / Jersey-heavy).

Legend:

| Tag | Meaning |
|---|---|
| **ADOPT** | Candidate for M1 staging `recipe:` (source transform) or MAPPINGS join |
| **ADAPT** | Useful as packet/catalog guidance; do not run blindly on staging/pom |
| **DEFER** | Valid for bring-your-own-app; out of cart demo scope |
| **REJECT** | Conflicts with harness policy or scaffold ownership |

### 9.1 Build / BOM / plugin (scaffold-owned)

| Recipe | Tag | Notes |
|---|---|---|
| Migrate Spring Boot to Quarkus (umbrella) | **REJECT** as drop-in | See §1–§3; use curated subset only |
| Add Quarkus Maven plugin | **ADAPT** | Scaffold already has `quarkus-maven-plugin` pinned to RH platform version |
| Add or replace Spring Boot build plugin with Quarkus build plugin | **ADAPT** | Same — destination pom truth |
| Customize Quarkus BOM Version | **REJECT** | Would point at community BOM; we pin `com.redhat.quarkus.platform` |
| Customize Quarkus Maven Plugin Goals | **ADAPT** | Scaffold already configures build/generate-code goals |
| Configure Quarkus Native Build Support | **ADAPT** | Scaffold native profile conventions live in pom rewrite tasks / MAPPINGS |
| Remove Spring Boot 3.x parent POM | **ADAPT** | Destination has no Spring parent; useful only if transforming legacy pom in place (we don't) |
| Replace Spring Boot starter dependencies with Quarkus equivalents | **ADAPT** | Catalog for plan packets; staging pom rewrites fight RH BOM / scaffold deps |
| Remove Spring Boot DevTools | **ADAPT** | Harmless; low value in our model (legacy never builds as destination) |
| Add Spring compatibility extensions… | **REJECT** | `quarkus-spring-di/web/boot-properties` — native-only policy |

### 9.2 Application entry / annotations (core Spring → native)

| Recipe | Tag | Notes |
|---|---|---|
| Migrate Spring annotations to CDI | **ADOPT** | Core DI path; aligns MAPPINGS `@Service`/`@Autowired` |
| Replace Spring `@Bean` with CDI `@Produces` | **ADOPT** | Matches extended Spring catalog |
| Replace Spring `@Value` with CDI `@ConfigProperty` | **ADOPT** | Same |
| Convert Spring Web annotations to JAX-RS | **ADOPT** | Prefer over leaving Spring Web + compat |
| Migrate Additional Spring Web Parameter Annotations | **ADOPT** | Complements Web→JAX-RS |
| Convert Spring `ResponseEntity` to JAX-RS `Response` | **ADOPT** | REST conventions |
| Migrate `@ConfigurationProperties` / Convert class to `@ConfigMapping` | **ADOPT** | Extended catalog |
| Migrate Spring `@Transactional` to Jakarta `@Transactional` | **ADOPT** | Persistence path |
| Migrate Spring Events / Convert `@EventListener` to `@Observes` | **ADOPT** | Matches in-process CDI events decision |
| Migrate Spring Validation / Replace Validation with Hibernate Validator | **ADOPT** | Supports `validateInput` |
| Migrate Spring Boot Testing / Replace Test with Quarkus JUnit 5 | **ADOPT** (care) | Align `project-test-standards`; validate coverage/mocking rules |
| Migrate Spring Boot Actuator… / Replace Actuator with SmallRye Health / Convert HealthIndicator | **ADOPT** | Scaffold already has `quarkus-smallrye-health` |
| Replace `@SpringBootApplication` with Quarkus equivalent | **ADAPT** | Harness prefers **delete** main; do not keep `Quarkus.run` without an explicit policy change |
| Replace `SpringApplication.run()` with `Quarkus.run()` | **REJECT** (current policy) | Conflicts with "no main by default" |
| Migrate `@EnableXyz` annotations to Quarkus extensions | **ADAPT** | Useful dependency adds; audit so it never pulls spring-* compat |

### 9.3 Web stack choice

| Recipe | Tag | Notes |
|---|---|---|
| Replace Spring Boot Web with Quarkus REST | **ADOPT** (preferred) | Matches scaffold `quarkus-rest-jackson` + MAPPINGS `quarkus-rest` |
| Replace Spring Boot Web with Quarkus RESTEasy Classic | **REJECT** for this scaffold | Wrong REST stack for our destination |
| Replace Spring Boot WebFlux with Quarkus REST Client | **DEFER** | Cart uses Feign/sync; map Feign separately (`@RegisterRestClient`) — not covered cleanly by WebFlux recipe |
| Replace Spring Boot WebSocket with Quarkus WebSockets | **DEFER** | Out of cart scope |
| Replace Spring Boot Data REST with Quarkus REST | **DEFER** | Out of cart scope |

### 9.4 Persistence / data

| Recipe | Tag | Notes |
|---|---|---|
| Replace Spring Boot JDBC with Quarkus Agroal | **ADAPT** | When `needsDatabase: true`; scaffold persistence skill owns Flyway/validate |
| Replace Spring Boot Data JPA with Hibernate ORM Panache | **ADAPT** | Panache optional — EntityManager path is also valid per skill |
| Migrate JPA Entities to Panache / Convert JPA Entity to Panache Entity | **ADAPT** | Do not force; only if plan chooses Panache |
| Migrate database drivers / Replace H2 / Derby (and test-scope) | **ADAPT** | DB stories only |
| Replace Spring Boot Data MongoDB / Migrate Mongo / Convert MongoRepository | **DEFER** | No Mongo in cart/scaffold |
| Replace Spring Boot Data Redis | **DEFER** | Out of cart scope |

### 9.5 Messaging / integration / cloud

| Recipe | Tag | Notes |
|---|---|---|
| Replace Spring Boot AMQP (RabbitMQ / AMQP) | **DEFER** | MAPPINGS: in-process → CDI events; out-of-process messaging only when genuine |
| Replace Spring Boot ActiveMQ / Artemis | **DEFER** | Same |
| Replace Spring Kafka (client / messaging) | **DEFER** | Out of cart scope |
| Replace Spring Boot Integration with Camel Quarkus | **DEFER** | Out of cart scope |
| Replace Spring Boot Batch / Quartz / Cache / Mail | **DEFER** | Catalog rows for BYO apps; Scheduler maps to `@Scheduled` in MAPPINGS |
| Replace Spring Boot Security / OAuth2 Client / OIDC Resource Server | **DEFER** | Important for secured services; not cart demo |
| Migrate Spring Cloud Config / Service Discovery | **DEFER** | Prefer env-driven `preserve:` / rest-client URL pattern we already enforce |
| Replace Spring Boot Elasticsearch / Thymeleaf→Qute | **DEFER** | Out of cart scope |

### 9.6 Catalog takeaway

The [Spring to Quarkus](https://docs.openrewrite.org/recipes/quarkus/spring)
index is the right **menu** for a harness-owned curated list. For stage
080 today:

- **ADOPT first** (~dozen): CDI stereotypes/`@Bean`/`@Value`, Web→JAX-RS
  (+ param edge cases, `ResponseEntity`), ConfigMapping, Validation,
  Transactional, Events, Testing, Actuator→Health, **Web→Quarkus REST**
  (not RESTEasy Classic).
- **Never from this catalog without an explicit policy change:** Spring
  compatibility extensions, community BOM customization,
  `Quarkus.run`/keep-main, RESTEasy Classic for this scaffold.
- **Everything else** is MAPPINGS/catalog guidance for broader Spring
  Boot estates; wire as `recipe:` only when a legacy app's findings
  inventory proves the dependency is present.

## 10. Related docs

| Document | Relation |
|---|---|
| [MTA-TO-SPEC-MAPPING.md](MTA-TO-SPEC-MAPPING.md) | Findings → inventory → recipe/rewrite/infer classification (R3 recipe-executed rewrites) |
| [MIGRATION-PROCESS-REDESIGN.md](MIGRATION-PROCESS-REDESIGN.md) | M1–M5 process and gates |
| [MIGIQ-ANALYSIS.md](MIGIQ-ANALYSIS.md) | Prior methodology inputs |
| Stage 080 scaffold `MAPPINGS.md` | Live mapping catalog agents cite |
| Catalog index | https://docs.openrewrite.org/recipes/quarkus/spring |
| Umbrella composite | https://docs.openrewrite.org/recipes/quarkus/spring/springboottoquarkus |
| Compat sub-recipe (rejected) | https://docs.openrewrite.org/recipes/quarkus/spring/addspringcompatibilityextensions |
| Quarkus upgrade aggregates (different job) | https://docs.openrewrite.org/recipes/quarkus/migratetoquarkus_v3_26_0 |

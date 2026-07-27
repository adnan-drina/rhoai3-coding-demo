# Jakarta EE → Quarkus mapping catalog

Decided defaults for this migration class. Plans cite these instead of
re-deriving them; packets copy the target shape from here.

## Contents
- Deterministic (OpenRewrite) transforms
- Decided manual mappings
- Discovering further recipes

## Deterministic (OpenRewrite) transforms

Run on `/tmp/rewrite-staging` per EXECUTION.md:

| Legacy | Recipe |
|---|---|
| `javax.*` imports/deps → `jakarta.*` | `org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta` (artifact `org.openrewrite.recipe:rewrite-migrate-java`) |

## Decided manual mappings (infer tasks — copy these shapes into packets)

| Legacy pattern | Target (decided) |
|---|---|
| `@Stateless` session bean | `@ApplicationScoped` CDI bean |
| `@Stateful` session bean | Redesign: `@ApplicationScoped` + per-key `ConcurrentHashMap` state (no server sessions) |
| `@Remote` interface / remote EJB | Drop the interface; direct `@Inject` of the implementation |
| JNDI `InitialContext.lookup(...)` | `@Inject` the service |
| JMS MDB / Topic within the app | **CDI events** (`Event<T>.fire` / `@Observes`) — in-process pub/sub needs no broker. Use SmallRye Reactive Messaging ONLY when messaging is genuinely out-of-process |
| `persistence.xml` + `@PersistenceContext` | `application.properties` datasource + constructor-injected `EntityManager`; schema via Flyway (see the worker's `quarkus-persistence-conventions` skill) |
| Startup servlets / init `@PostConstruct` | `void onStart(@Observes StartupEvent ev)` |
| `javax.json` (JSON-P) | Jackson (`ObjectMapper`) |
| JAX-RS resources | `quarkus-rest` + Jackson under `/api/` (worker's `quarkus-rest-conventions` skill) |
| Vendored/enterprise jars unavailable in Central | Vendor in-repo (`lib/` + file-based `<repository>` in `pom.xml`) — the repository must build self-contained |

## Spring Boot → Quarkus (decided manual mappings)

For Spring-Boot-class legacy inputs (e.g. the Coolstore cart service):

| Legacy pattern | Target (decided) |
|---|---|
| `@SpringBootApplication` / `SpringApplication.run` | Delete — Quarkus has no main class by default |
| `@Service` / `@Component` + `@Autowired` | `@ApplicationScoped` + constructor injection |
| `@FeignClient(url = "${VAR}")` interface | MicroProfile REST client: `@RegisterRestClient(configKey=...)` + `@Path`; URL via `quarkus.rest-client.<key>.url=${VAR}` |
| `spring-boot-starter-jersey` + `ResourceConfig` | Drop — `quarkus-rest` serves JAX-RS resources directly; keep the `javax→jakarta` rewrite on the resources |
| Spring `@GetMapping` etc. on client interfaces | JAX-RS `@GET`/`@Path` equivalents |
| `spring-boot-starter-actuator` | `quarkus-smallrye-health` (`/q/health`) |
| `application.properties` (Spring keys) | Quarkus keys; plain `KEY=value` pass-throughs keep working |
| `spring-boot-maven-plugin` | `quarkus-maven-plugin` |
| `@PostConstruct` (javax.annotation) | `jakarta.annotation.PostConstruct` (rewrite covers it) |

Extended Spring catalog (harvested from the upstream
[quarkusio/quarkus-skills](https://github.com/quarkusio/quarkus-skills)
`migrate-spring-to-quarkus` annotation map, 2026-07 — decided for this
harness: NATIVE Quarkus targets, never `quarkus-spring-*` compat
extensions; compat mode hides the migration instead of doing it):

| Legacy pattern | Target (decided) |
|---|---|
| `@Value("${prop}")` | `@ConfigProperty(name = "prop")` |
| `@Configuration` + `@Bean` | `@ApplicationScoped` bean with `@Produces` methods |
| `@Qualifier("name")` | `@Named` or a custom CDI qualifier |
| `@PathVariable` / `@RequestParam` / `@RequestHeader` | `@PathParam` / `@QueryParam` / `@HeaderParam` |
| `@RequestBody` | no annotation — JAX-RS body param |
| `@ConfigurationProperties(prefix="app")` | `@ConfigMapping(prefix = "app")` |
| `@Scheduled(cron=...)` / `(fixedRate=1000)` | `@io.quarkus.scheduler.Scheduled(cron=...)` / `(every = "1s")` |
| `@Secured` / `@PreAuthorize("hasRole('X')")` | `@RolesAllowed("X")` |
| `CrudRepository`/`JpaRepository<T,ID>` | `PanacheRepository<T>`; `@Query` JPQL → Panache `find()` |
| `@SpringBootTest` / `@MockBean` | `@QuarkusTest` / `@InjectMock` (+ `@RestClient` qualifier when mocking a REST client) |

## Windup rule joins (machine-readable)

`findings-inventory.py` parses THIS table to classify every mandatory
finding at Phase A. `class` semantics: `recipe:<plugin-version>:<recipe-artifact>:<recipe-name>`
= executed by the supervisor as a scripted OpenRewrite step (validated
2026-07-27 against the real cart legacy tree); `rewrite` = mechanical,
executed in a task packet; `infer` = judgment — the decided shape is in
the tables above. NOTE: several Windup rules SUGGEST `quarkus-spring-*`
compat extensions; the join records OUR decision (native Quarkus,
compat rejected — it hides the migration instead of doing it). Only
rule ids observed in real analyses are listed; unmatched mandatory
rules are flagged OPEN DESIGN by the inventory.

| rule id prefix | class | decided target |
|---|---|---|
| javax-to-jakarta- | recipe:5.46.1:org.openrewrite.recipe:rewrite-migrate-java:2.30.1:org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta | jakarta.* imports |
| javaee-pom-to-quarkus- | rewrite | scaffold pom conventions: platform BOM, pinned quarkus/compiler/surefire/failsafe plugins, native profile, quarkus junit |
| springboot-parent-pom-to-quarkus- | rewrite | Quarkus platform BOM replaces the Spring parent |
| springboot-plugins-to-quarkus- | rewrite | `quarkus-maven-plugin` (pinned, `${quarkus.platform.group-id}`) |
| jakarta-jaxrs-to-quarkus- | rewrite | `quarkus-rest` dependency |
| springboot-actuator-to-quarkus- | rewrite | `quarkus-smallrye-health` (`/q/health`) |
| springboot-metrics-to-quarkus-01 | rewrite | Micrometer dependency → `quarkus-smallrye-metrics` |
| springboot-metrics-to-quarkus-02 | infer | metrics call sites → MP Metrics annotations (design per site) |
| springboot-annotations-to-quarkus- | rewrite | delete `@SpringBootApplication` + main class |
| springboot-di-to-quarkus- | infer | native CDI constructor injection (NOT the spring-di extension) |
| springboot-web-to-quarkus- | infer | native JAX-RS resources (NOT the spring-web extension) |
| springboot-properties-to-quarkus- | rewrite | Quarkus keys in application.properties (plain pass-throughs keep working; NOT the spring-boot-properties extension) |
| spring-components- | infer | umbrella version-incompatibility rules — resolved by the conversion tasks as a whole; map to the service/endpoint conversion tasks |
| demo-env-integration- | infer | the surface IS the preserve contract: record under migration.yaml `preserve:`; target keeps env-driven config (`${VAR:default}` / `quarkus.rest-client.<key>.url`) |
| localhost-http- | infer | cloud-readiness: hardcoded/localhost service URLs → env-driven config (`${VAR:default}`), tied to the `preserve:` contract |
| removed-javaee- | rewrite | JEE modules removed from the JDK → provided by Quarkus platform dependencies (BOM) — resolved with the pom conversion |

## Discovering further recipes

Enumerate what the classpath offers before hand-coding a mechanical
transform:

```bash
mvn -q org.openrewrite.maven:rewrite-maven-plugin:6.12.0:discover \
  -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:3.12.0
```

Only cite recipes the discover output actually lists.

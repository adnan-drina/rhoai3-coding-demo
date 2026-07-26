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

## Discovering further recipes

Enumerate what the classpath offers before hand-coding a mechanical
transform:

```bash
mvn -q org.openrewrite.maven:rewrite-maven-plugin:6.12.0:discover \
  -Drewrite.recipeArtifactCoordinates=org.openrewrite.recipe:rewrite-migrate-java:3.12.0
```

Only cite recipes the discover output actually lists.

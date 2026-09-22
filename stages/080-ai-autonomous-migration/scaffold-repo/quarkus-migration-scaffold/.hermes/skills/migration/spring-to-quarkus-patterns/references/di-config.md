# DI and config map (cards)

## Source

- Living map: quarkusio/skills `migrate-spring-to-quarkus` (prefer on overlap)
- Pedagogical locus: Deandrea et al., 2021, Ch 2 (scopes / config) — cite only
- [Quarkus 3.27 Spring DI](https://quarkus.io/version/3.27/guides/spring-di/)
  (`@Value` property placeholders and defaults) and
  [HTTP reference](https://quarkus.io/version/3.27/guides/http-reference/)
  (`quarkus.http.root-path`).

## Cards

| id | Spring | Quarkus | status | note |
|----|--------|---------|--------|------|
| di-component | `@Component` / `@Service` | `@ApplicationScoped` (or stereotype) | ADOPT | Default for services |
| di-repo | `@Repository` | Spring Data repository bean (ADR-004) or `@ApplicationScoped` helper | ADOPT | See persistence.md / spring-data-jpa.md |
| di-inject | `@Autowired` field | constructor injection | STRENGTHEN | Field injection refuse where cheap |
| di-singleton | `@Service` singleton intent | `@ApplicationScoped` preferred over `@Singleton` | STRENGTHEN | `@Singleton` not client-proxyable / harder to mock |
| cfg-value | `@Value("${k}")` | `@ConfigProperty(name="k")` | ADOPT | |
| cfg-context-path | `@Value("#{servletContext.contextPath}")` | Inject `quarkus.http.root-path`, for example `@Value("${quarkus.http.root-path:/}")` in the decided Spring compatibility mode | ADOPT | When joining a slash-prefixed path, remove the root's trailing slash; `/` then contributes an empty prefix, as a servlet root context does. Preserve the suffix and compare the actual first-response Location against the source. No blanket rewrite of other SpEL expressions. |
| cfg-mapping | `@ConfigurationProperties` | `@ConfigMapping` | ADOPT | |
| cfg-profile | `spring.profiles.active` / `application-dev.properties` | `%dev.key` in `application.properties` or `QUARKUS_PROFILE` | ADOPT | Quarkus also loads `application-<profile>.properties` when that profile is active |
| di-profile | Spring `@Profile("x")` on beans | `@IfBuildProfile("x")` (`io.quarkus.arc.profile`) | ADOPT | **FORBIDDEN:** `io.quarkus.arc.Profile` / `@IfProfileActive` — not on Quarkus 3.27 classpath (Phase-3 Class B) |
| di-mapstruct | Spring `@Mapper` / `@Autowired` mapper | **doctrine pending R-SKILL-F** | MEASURED | v19: `componentModel = "cdi"` produced ten Unsatisfied beans. Do not mandate that shape. |

The decided Spring compatibility mode may retain `quarkus-spring-di`;
it does not run Spring Boot autoconfiguration or a Spring application context.
**REJECT:** `import io.quarkus.arc.Profile` or `IfProfileActive` — use `IfBuildProfile` / `UnlessBuildProfile`.

For `unsupported-spel` on `org.springframework.beans.factory.annotation.Value`,
inspect the exact expression and its consumer. The context-path row covers only
that expression: a configuration placeholder is not a general SpEL evaluator.
Do not substitute `@Value("")`, which names an empty configuration property,
or remove the context prefix to make packaging pass. If the named file lies
outside the issued scope, preserve the candidate and report the prerequisite;
the gate has not passed merely because its first error changed.

## MapStruct / CDI (B-3 — measured, doctrine pending R-SKILL-F)

**Do not instruct a worker to use a shape v19 measured as broken.**

v19 measured `MapStruct @Mapper(componentModel = "cdi")` plus `@Inject` of the
generated mapper: `quarkus:build` UnsatisfiedResolutionException (ten beans).
`Mappers.getMapper` failed under `@QuarkusTest`. The GAV `1.5.5.Final` was
invented by S-003 and is **unpinned** (`pins.json` mapstruct.status=unpinned).
Do not invent a replacement GAV here.

**Incident repair is not doctrine.** A Lead dest wrap (`@ApplicationScoped
*MapperCdi` delegating to `new *MapperImpl()`) unblocked M4 twice. That is an
incident fix. **Do not promote it to ADOPT** until R-SKILL-F lands official
grounding.

Until R-SKILL-F:

- Do **not** mandate `componentModel = "cdi"`.
- Do **not** REJECT `@Mapper` default as if that were the proven fix.
- Prefer a compiling, injectable mapper the story's own tests prove.
- Pin a MapStruct GAV only in `pins.json` after R-SKILL-F — not in a story POM
  as a freehand version.

## Agent text

Prefer ctor injection + `@ApplicationScoped`. Express config with Quarkus
`%profile` / `@ConfigProperty` — do not copy Spring `application-*.properties`
layout into the destination unless the brief requires equivalent keys.
For DTO mappers, open this file and **do not** stamp `componentModel = "cdi"`
as a required pattern. Doctrine pending R-SKILL-F.

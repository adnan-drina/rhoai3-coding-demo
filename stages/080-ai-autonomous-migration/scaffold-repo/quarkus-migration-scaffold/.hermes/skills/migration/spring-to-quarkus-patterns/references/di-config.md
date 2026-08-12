# DI and config map (cards)

## Source

- Living map: quarkusio/skills `migrate-spring-to-quarkus` (prefer on overlap)
- Pedagogical locus: Deandrea et al., 2021, Ch 2 (scopes / config) — cite only

## Cards

| id | Spring | Quarkus | status | note |
|----|--------|---------|--------|------|
| di-component | `@Component` / `@Service` | `@ApplicationScoped` (or stereotype) | ADOPT | Default for services |
| di-repo | `@Repository` | `@ApplicationScoped` + Panache repository | ADOPT | See persistence.md |
| di-inject | `@Autowired` field | constructor injection | STRENGTHEN | Field injection refuse where cheap |
| di-singleton | `@Service` singleton intent | `@ApplicationScoped` preferred over `@Singleton` | STRENGTHEN | `@Singleton` not client-proxyable / harder to mock |
| cfg-value | `@Value("${k}")` | `@ConfigProperty(name="k")` | ADOPT | |
| cfg-mapping | `@ConfigurationProperties` | `@ConfigMapping` | ADOPT | |
| cfg-profile | `spring.profiles.active` / `application-dev.properties` | `%dev.key` in `application.properties` or `QUARKUS_PROFILE` | ADOPT | Quarkus also loads `application-<profile>.properties` when that profile is active |
| di-profile | Spring `@Profile("x")` on beans | `@IfBuildProfile("x")` (`io.quarkus.arc.profile`) | ADOPT | **FORBIDDEN:** `io.quarkus.arc.Profile` / `@IfProfileActive` — not on Quarkus 3.27 classpath (Phase-3 Class B) |
| di-mapstruct | Spring `@Mapper` / `@Autowired` mapper | MapStruct `@Mapper(componentModel = "cdi")` + inject interface | ADOPT | Phase-3 exp FAIL: interface without CDI componentModel ⇒ UnsatisfiedResolutionException |

**REJECT:** `quarkus-spring-di` / Spring Boot autoconfig on destination.  
**REJECT:** `import io.quarkus.arc.Profile` or `IfProfileActive` — use `IfBuildProfile` / `UnlessBuildProfile`.  
**REJECT:** MapStruct `@Mapper` default (no `componentModel`) when controllers `@Inject` the mapper — Arc will not see a bean.

## MapStruct / CDI (Phase-4 feedforward — Architect E-20260811T101551Z)

Measured on experiment arm: package fails with
`UnsatisfiedResolutionException` for `*Mapper` injection points when MapStruct
does not emit a CDI bean.

**Required pattern**

```java
@Mapper(componentModel = "cdi")
public interface PetTypeMapper {
    PetTypeDto toDto(PetType entity);
}
```

**Checklist before `kanban_complete` / M4 package**

1. Every injected `*Mapper` interface uses `componentModel = "cdi"` (or `"jakarta"`
   if the project MapStruct version documents that synonym — prefer `"cdi"`).
2. `mapstruct` + annotation processor present in `pom.xml` (BOM-aligned).
3. `mvn -q -DskipTests compile` resolves injection (no Unsatisfied `*Mapper`).
4. Do **not** invent hand-written `@Produces` mapper shells to paper over a missing
   `componentModel` — fix the annotation (tip law for v12 create).

**Anti-pattern (experiment residual):** `@Mapper` + `@Inject PetTypeMapper` with
Spring/`default` component model — compiles Java but Quarkus Arc fails at build.

Official: MapStruct CDI/`componentModel` docs; Quarkus Arc unsatisfied resolution.

## Agent text

Prefer ctor injection + `@ApplicationScoped`. Express config with Quarkus
`%profile` / `@ConfigProperty` — do not copy Spring `application-*.properties`
layout into the destination unless the brief requires equivalent keys.
For DTO mappers under Quarkus, always set MapStruct `componentModel = "cdi"`.

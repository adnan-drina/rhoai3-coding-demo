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
| cfg-profile | `spring.profiles.active` / `application-dev.properties` | `%dev.key` in `application.properties` or `QUARKUS_PROFILE` | ADOPT | Do not invent parallel Spring profile files |

**REJECT:** `quarkus-spring-di` / Spring Boot autoconfig on destination.

## Agent text

Prefer ctor injection + `@ApplicationScoped`. Express config with Quarkus
`%profile` / `@ConfigProperty` — do not copy Spring `application-*.properties`
layout into the destination unless the brief requires equivalent keys.

# Spring dependency → Quarkus extension (T-3)

Use this when deciding whether a legacy dependency implies a Quarkus
extension. **Half the common Spring Boot starters do not map 1:1** — some stay
libraries, some are native rewrites, some need a mechanism pair.

Official landing: [Migrate from Spring to Quarkus](https://quarkus.io/spring/migrate/).
This project forbids `quarkus-spring-*` compatibility extensions — prefer
native Quarkus targets.

| Legacy concern | Quarkus target | Notes |
|----------------|----------------|-------|
| Spring Web / MVC REST | `quarkus-rest` + `quarkus-rest-jackson` | Native rewrite, not compat |
| Spring Data JPA | `quarkus-hibernate-orm` (+ Panache if chosen) | See `extension-obligations.md` |
| Spring JDBC starter | `quarkus-agroal` + `quarkus-jdbc-*` | Driver + pool |
| Spring Data JDBC / `JdbcTemplate` usage | Often **no** extension | Narrow usage may stay a library dependency (house JDBC-as-library pattern) |
| Spring Security | `quarkus-security` + concrete mechanism (e.g. `quarkus-elytron-security-jdbc`) | Base alone is insufficient |
| Bean Validation | `quarkus-hibernate-validator` | Closest 1:1 |
| Spring Cache | `quarkus-cache` | Annotation rewrite; different key rules — see obligations |
| Spring AOP | CDI `@Interceptor` | No direct extension |
| Actuator health | `quarkus-smallrye-health` (+ micrometer only if metrics in scope) | Bundle ≠ one extension |
| springfox / OpenAPI | `quarkus-smallrye-openapi` | Separate from the eight core families |
| MapStruct | None | Annotation processor only |

**Rule:** "Spring dependency present" ≠ "must `ext add` something." Check this
table (or the official migrate page) per dependency; over-provisioning a fixed
menu is the failure DD3 retires.

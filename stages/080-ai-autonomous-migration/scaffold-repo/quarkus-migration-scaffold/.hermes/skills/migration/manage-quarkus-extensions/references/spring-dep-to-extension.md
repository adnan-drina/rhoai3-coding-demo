# Spring dependency → Quarkus extension (T-3)

Use this when deciding whether a legacy dependency implies a Quarkus
extension. **Half the common Spring Boot starters do not map 1:1** — some stay
libraries, some are native rewrites, some need a mechanism pair.

Official landing: [Migrate from Spring to Quarkus](https://quarkus.io/spring/migrate/).
This project forbids `quarkus-spring-*` compatibility extensions — prefer
native Quarkus targets.

`emit-required-extensions.py` parses the **Legacy keys** and **Quarkus
targets** columns (backtick tokens). Do not keep a second Python dict.

JDBC driver kind is **not** dest `db-kind` (that file does not exist at M1).
Parse `jdbc:<kind>:` from the **legacy** datasource URL and map it through
the `jdbc:*` rows. Quarkus 3.27 dropped `quarkus-jdbc-hsqldb` — that is a
cited row, not a fallback constant.

| Legacy keys | Quarkus targets | Notes |
|-------------|-----------------|-------|
| `spring-web` `spring-boot-starter-web` `spring-webmvc` `spring-boot-starter-webflux` | `quarkus-rest` `quarkus-rest-jackson` | Native rewrite, not compat |
| `spring-data-jpa` `spring-boot-starter-data-jpa` `hibernate-core` `hibernate-orm` | `quarkus-hibernate-orm` | See `extension-obligations.md` |
| `spring-boot-starter-jdbc` `spring-jdbc` | `quarkus-agroal` `quarkus-jdbc-*` | Pool + driver; expand `*` from legacy `jdbc:` URL |
| `jdbc:hsqldb` | `quarkus-jdbc-h2` | Quarkus 3.27 dropped HSQLDB (AR-2.1 / B7) |
| `jdbc:h2` | `quarkus-jdbc-h2` | |
| `jdbc:postgresql` `jdbc:pgsql` `jdbc:pg` | `quarkus-jdbc-postgresql` | |
| `jdbc:mysql` | `quarkus-jdbc-mysql` | |
| `jdbc:mariadb` | `quarkus-jdbc-mariadb` | |
| Spring Data JDBC / `JdbcTemplate` (no starter) | none | House JDBC-as-library; no extra extension |
| `spring-boot-starter-security` `spring-security` | `quarkus-security` | Base alone is insufficient for a mechanism |
| `spring-boot-starter-validation` `hibernate-validator` `validation-api` `jakarta.validation-api` | `quarkus-hibernate-validator` | Closest 1:1 |
| `spring-cache` `spring-boot-starter-cache` | `quarkus-cache` | Annotation rewrite; different key rules |
| `spring-di` `spring-boot-starter-aop` `spring-aop` | none | CDI / interceptor; no extra extension |
| `spring-boot-starter-actuator` | `quarkus-smallrye-health` | Bundle ≠ one extension |
| `springfox-swagger2` `springfox-swagger-ui` | `quarkus-smallrye-openapi` `openapi-generator-maven-plugin` | Plugin, not an extension |
| `springdoc-openapi-ui` | `quarkus-smallrye-openapi` | |
| `openapi-generator-maven-plugin` | `openapi-generator-maven-plugin` | Maven **plugin** (`kind: plugin`) |
| `mapstruct` | none | Annotation processor only |

**Rule:** "Spring dependency present" ≠ "must `ext add` something." Check this
table per dependency; over-provisioning a fixed menu is the failure DD3
retires.

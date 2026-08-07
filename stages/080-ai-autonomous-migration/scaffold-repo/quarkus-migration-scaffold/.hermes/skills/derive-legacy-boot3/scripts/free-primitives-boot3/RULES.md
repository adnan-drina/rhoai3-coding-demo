# Free-primitives Boot 2→3 composite — admit table

**Version:** `1.0.0` · **Path:** W2 §12 SETTLED · Operator free-primitives
**Invocation:** `run-composite.sh` (default `DERIVE_UPGRADE_CMD`)

Specimen-agnostic: no coolstore/petclinic literals. Behavioral rules require
G-4 dual-mode later — compile success is not behavioral proof.

| id | cite | pre | post | scope | behavioral? |
|---|---|---|---|---|---|
| `javax-to-jakarta` | MTA Windup `org.jboss.windup.JavaxToJakarta` (EPL; free primitives `ChangePackage`/`ChangeType`); fallback = same package map | tree contains `javax.(persistence\|validation\|annotation\|transaction\|ws.rs\|inject\|servlet\|xml.bind)` in sources/pom | those EE refs are `jakarta.*`; `javax.sql` / `javax.annotation.processing` untouched | java, pom, xml | N |
| `bump-boot-parent` | [Spring Boot 3.0 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide) — system requirements (Java 17+) | `spring-boot-starter-parent` version `< 3` | parent `3.0.13`, `java.version` ≥ 17 | pom | N |
| `mysql-connector-j` | Boot 3.0 Migration Guide — dependency management / MySQL Connector/J coordinate rename (`mysql:mysql-connector-java` → `com.mysql:mysql-connector-j`) | pom has `mysql:mysql-connector-java` | artifact is `com.mysql:mysql-connector-j`; version managed by BOM when possible | pom | N |
| `jaxb-api-jakarta` | Boot 3.0 Migration Guide — Jakarta EE APIs (JAXB no longer on default classpath) | pom has `javax.xml.bind:jaxb-api` **or** Boot≥3 and JAXB types referenced without jakarta dep | `jakarta.xml.bind:jakarta.xml.bind-api` present; javax jaxb-api gone | pom | N |
| `security6-wsca` | [Spring Security 6.0 migration](https://docs.spring.io/spring-security/reference/migration/index.html) — `WebSecurityConfigurerAdapter` removed | `.java` contains `WebSecurityConfigurerAdapter` | class no longer extends adapter; `SecurityFilterChain` `@Bean` present; Sec6 request/csrf APIs | java | **Y** — G-4 security-off + security-on |
| `openapi-jakarta-ee` | OpenAPI Generator `configOptions.useJakartaEe` (generator ≥6) | pom configures `openapi-generator-maven-plugin` without jakarta EE | plugin ≥6.6.0; `configOptions.useJakartaEe=true`; `swagger-annotations` ≥2.2 when generator emits `requiredMode` | pom / generator-config | N |

**Never-automatic (not in this composite):** Moderne `UpgradeSpringBoot_3_0`,
specimen-literal patches, Security rewrites without later G-4, LLM free edits.

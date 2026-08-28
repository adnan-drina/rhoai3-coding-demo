# Free-primitives Boot 2→3 composite — admit table

**Version:** `1.2.1` · **Path:** W2 §12 SETTLED · Operator free-primitives
**Invocation:** `run-composite.sh` (default `DERIVE_UPGRADE_CMD`)

Specimen-agnostic: no coolstore/petclinic/jhipster literals. Behavioral rules
require G-4 dual-mode later — compile success is not behavioral proof.

| id | cite | pre | post | idempotent | relevance | scope | behavioral? |
|---|---|---|---|---|---|---|---|
| `javax-to-jakarta` | MTA Windup `org.jboss.windup.JavaxToJakarta` (EPL; free primitives `ChangePackage`/`ChangeType`); fallback = same package map | tree contains EE `javax.(persistence\|validation\|annotation\|transaction\|ws.rs\|inject\|servlet\|xml.bind)` in sources/pom | those EE refs are `jakarta.*`; `javax.sql` / `javax.annotation.processing` untouched | Y — skip when no EE javax refs; re-run digest-stable (see COMPOSITE-VALIDATION) | fires only when pre true | java, pom, xml | N |
| `bump-boot-parent` | [Spring Boot 3.0 Migration Guide](https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide) — Java 17+ / dependency management | `spring-boot-starter-parent` `< 3` **or** `<spring-boot.version>` `< 3` **or** `java.version` `< 17` | parent and/or property ≥ `3.0.13`; when property-managed **without** starter-parent, `spring-boot-dependencies` BOM imported ahead of other BOMs; `java.version` ≥ 17 | Y — no write when already satisfied | fires only when pre true | pom | N |
| `mysql-connector-j` | Boot 3.0 Migration Guide — MySQL Connector/J coordinate rename (`mysql:mysql-connector-java` → `com.mysql:mysql-connector-j`) | pom has `mysql:mysql-connector-java` | artifact is `com.mysql:mysql-connector-j`; version managed by BOM when possible | Y — skip when coord absent/already renamed | fires only when pre true | pom | N |
| `jaxb-api-jakarta` | Boot 3.0 Migration Guide — Jakarta EE APIs (JAXB no longer on default classpath) | pom has `javax.xml.bind:jaxb-api`, stale `${jaxb-api.version}` on jakarta artifact, **or** JAXB types without jakarta dep | `jakarta.xml.bind:jakarta.xml.bind-api` present; javax jaxb-api / stale pin gone | Y — skip when already clean | fires only when pre true | pom | N |
| `security6-wsca` | [Spring Security 6.0 migration](https://docs.spring.io/spring-security/reference/migration/index.html) — `WebSecurityConfigurerAdapter` removed | `.java` contains `WebSecurityConfigurerAdapter` | class no longer extends adapter; `SecurityFilterChain` `@Bean` present; Sec6 request/csrf APIs | Y — skip when adapter absent | fires only when pre true | java | **Y** — G-4 security-off + security-on |
| `security6-matchers` | [Spring Security 6 servlet config migration](https://docs.spring.io/spring-security/reference/migration/servlet/config.html) — `authorizeHttpRequests` / `requestMatchers` | `.java` contains `authorizeRequests` / `antMatchers` / `mvcMatchers` / `ignoringAntMatchers` | those APIs rewritten to Sec6 names (`authorizeHttpRequests`, `requestMatchers`, `ignoringRequestMatchers`) | Y — skip when markers absent | fires only when pre true | java | **Y** — G-4 security-off + security-on |
| `openapi-jakarta-ee` | OpenAPI Generator `configOptions.useJakartaEe` (generator ≥6) | pom configures `openapi-generator-maven-plugin` without jakarta EE | plugin ≥6.6.0; `configOptions.useJakartaEe=true`; `swagger-annotations` ≥2.2 when generator emits `requiredMode` | Y — skip when already configured | fires only when plugin present and incomplete | pom / generator-config | N |
| `springfox-to-springdoc` | [springdoc migrating-from-springfox](https://springdoc.org/#migrating-from-springfox) + Boot 3.0 Migration Guide (Jakarta / no javax.servlet) | pom or sources reference `io.springfox` / `springfox.*` | springfox deps and springfox-importing `.java` gone; `org.springdoc:springdoc-openapi-starter-webmvc-ui` present | Y — skip when springfox absent | fires only when pre true | pom, java | **Y** — G-4 OpenAPI path subset (`/v3/api-docs` and/or swagger-ui) before DEMONSTRATED |
| `thymeleaf-spring6` | Boot 3.0 Migration Guide — Thymeleaf spring5 → spring6 | sources reference `org.thymeleaf.spring5` | those refs are `org.thymeleaf.spring6` | Y — skip when spring5 absent | fires only when pre true | java | N |

**Parent/child entity-slice note (Architect E-20260808T095454Z):** first prove may use
typed **OpenAPI descope** (remove springfox without springdoc) instead of this
rule — declare descope; G-4 OpenAPI N/A for that slice. This rule is the
admitted general composite path for later specimens / full migration.

**P13 admit (Architect E-20260808T184742Z):** gaps 1–3 above. Vendor framework
pins (e.g. jhipster-framework javax binaries) stay **outside** this composite —
typed residual / template, not a golden recipe.

**Never-automatic (not in this composite):** Moderne `UpgradeSpringBoot_3_0`,
specimen-literal patches, vendor framework pin upgrades, Security rewrites
without later G-4, LLM free edits.

# Spring Boot → Quarkus property keys

**Quarkus does not automatically translate Spring Boot properties.** Replace
Spring-prefixed keys; do not leave them hoping for a shim.

| Spring Boot | Quarkus |
|-------------|---------|
| `spring.datasource.url` | `quarkus.datasource.jdbc.url` |
| `spring.datasource.username` | `quarkus.datasource.username` |
| `spring.datasource.password` | `quarkus.datasource.password` |
| `spring.jpa.hibernate.ddl-auto=create-drop` | `quarkus.hibernate-orm.database.generation=drop-and-create` |
| `server.port` | `quarkus.http.port` |
| `springdoc.api-docs.path` | `quarkus.smallrye-openapi.path` |
| `springdoc.swagger-ui.path` | `quarkus.swagger-ui.path` |

Prefer `@ConfigMapping` (typed, nestable) over recreating Spring
`@ConfigurationProperties` trees.

Automation corroboration (not a substitute for review): MTA rules that flag
Spring datasource keys; OpenRewrite `SpringBootToQuarkus` recipes for
mechanical swaps.

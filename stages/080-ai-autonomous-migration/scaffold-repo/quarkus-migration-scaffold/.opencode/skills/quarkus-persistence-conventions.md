---
description: How this team does persistence in Quarkus — Hibernate 6 id generation, Flyway discipline, and the schema-validation contract. Apply on every entity, migration, or datasource change.
---

# Quarkus Persistence Conventions

The runtime contract: `quarkus.hibernate-orm.database.generation=validate`
against a PostgreSQL schema owned entirely by Flyway. Hibernate validates —
it never creates. Every mismatch is a startup crash in the factory. Do not
use `drop-and-create` or Spring's `ddl-auto=update` — the book and blog
examples that do are not the factory path.

## Spring Data → Panache (when a story chooses Panache)

Prefer repository style over active record:

```java
@ApplicationScoped
public class ProductRepository implements PanacheRepository<Product> {
    public Optional<Product> findBySku(String sku) {
        return find("sku", sku).firstResultOptional();
    }
}
```

Constructor-inject the repository into services; keep `@Transactional` on
mutating service methods (`jakarta.transaction.Transactional` — same name as
Spring, Jakarta package).

## Config and naming

Spring datasource keys map to Quarkus (`spring.datasource.url` →
`quarkus.datasource.jdbc.url` + `quarkus.datasource.db-kind`). Flyway:
`spring.flyway.*` → `quarkus.flyway.*`. Use `%prod.` prefix on prod JDBC
URLs when dev/test rely on Dev Services.

**Naming-strategy trap:** Spring's default snake_case physical naming differs
from Quarkus (preserves Java field names). Align `@Column(name=...)` in
entities or set `quarkus.hibernate-orm.physical-naming-strategy` explicitly —
silent schema mismatch fails at startup under `validate`.

## Entity id generation

- Use explicit generators, never bare AUTO:
  `@GeneratedValue(strategy = SEQUENCE, generator = "<name>_gen")` with
  `@SequenceGenerator(name = "<name>_gen", sequenceName = "<name>_seq",
  allocationSize = 1)`.
- **Every declared `sequenceName` MUST have a matching
  `CREATE SEQUENCE IF NOT EXISTS <name>_seq ...` in a Flyway migration in
  the SAME change.** A generator without DDL is a deploy-time crash
  (schema-validation: missing sequence), not a test failure — local tests
  will not catch it.

## Flyway discipline

- Migrations live in `src/main/resources/db/migration/` named
  `V<N>__Description.sql`; never edit an applied migration — add a new one.
- Seed data must satisfy every constraint it touches, including id columns
  whose values must not collide with sequence start values.
- `quarkus.flyway.migrate-at-start=true` is the only schema writer.

## Service/data access

- Constructor-inject `EntityManager` (or Panache repositories); no field
  injection.
- `@Transactional` on every mutating service method.

## Tests

- Services: plain JUnit 5 + Mockito (the coverage gate's instrument) —
  mock `EntityManager`/repositories.
- Reserve `@QuarkusTest` for endpoint/integration coverage.

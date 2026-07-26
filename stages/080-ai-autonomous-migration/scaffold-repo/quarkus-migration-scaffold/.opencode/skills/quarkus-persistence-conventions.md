---
description: How this team does persistence in Quarkus — Hibernate 6 id generation, Flyway discipline, and the schema-validation contract. Apply on every entity, migration, or datasource change.
---

# Quarkus Persistence Conventions

The runtime contract: `quarkus.hibernate-orm.database.generation=validate`
against a PostgreSQL schema owned entirely by Flyway. Hibernate validates —
it never creates. Every mismatch is a startup crash in the factory.

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

# Panache vs EntityManager

Both forms share the same `EntityManager` plumbing — this is structure /
testability, not performance.

This specimen's repository layer is **Spring Data JPA** (ADR-004,
`references/spring-data-jpa.md`). The table below is for types that are
**not** those Spring Data repositories (custom persistence helpers), or for
a later ADR that supersedes ADR-004.

| Prefer | When |
|--------|------|
| Spring Data JPA (`JpaRepository` / `CrudRepository` / fragments) | Default on this specimen. Supported subset only |
| `@Inject EntityManager` | Custom JPQL/merge the Spring Data subset cannot express; hierarchical/DDD aggregates; test doubles |
| `PanacheRepository` / `PanacheEntity` | Not the default. Requires an ADR that supersedes ADR-004 |

**Hard constraint:** a Panache entity attaches to **only one** persistence
unit. Multi-PU designs disqualify Panache on the affected entities.

Do not add a second `quarkus-spring-data-*` GAV. Do not rewrite ADR-004
repositories as Panache to clear `UnableToParseMethodException`. Do not
claim "Panache" in completion text unless Panache types appear in the diff.

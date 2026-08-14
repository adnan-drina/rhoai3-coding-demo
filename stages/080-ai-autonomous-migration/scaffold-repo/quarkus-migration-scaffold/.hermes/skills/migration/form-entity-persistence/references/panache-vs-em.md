# Panache vs EntityManager

Both forms share the same `EntityManager` plumbing — this is structure /
testability, not performance.

| Prefer | When |
|--------|------|
| `PanacheEntity` / active record | Simple entities; discoverability; no multi-PU |
| `PanacheRepository` | CRUD with injectable bean; still Panache ops |
| `@Inject EntityManager` | Custom JPQL/merge; hierarchical/DDD aggregates; test doubles |

Maintainer rule of thumb: active record fits simpler types; repositories /
EM fit hierarchies, aggregates, entities that extend other classes, complex
ops. Forms may combine (helpers + repository) when useful.

**Hard constraint:** a Panache entity attaches to **only one** persistence
unit. Multi-PU designs disqualify Panache on the affected entities.

Refuse `quarkus-spring-data-*`. Do not claim "Panache" in completion text
unless Panache types appear in the diff.

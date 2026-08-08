# Persistence map (cards)

## Source

- Living map: quarkusio/skills `migrate-spring-to-quarkus` (prefer on overlap)
- Pedagogical locus: Deandrea et al., 2021, Ch 4 — cite only

## Cards

| id | Spring | Quarkus | status | note |
|----|--------|---------|--------|------|
| pers-repo | `JpaRepository` / Spring Data | Panache **repository** pattern | ADOPT | Active record allowed, not default |
| pers-entity | `@Entity` JPA | `@Entity` (Jakarta) | ADOPT | `javax`→`jakarta` |
| pers-tx | `@Transactional` (Spring) | `@Transactional` (Quarkus / Narayana) | ADOPT | Same name; confirm import |
| pers-migrate | Flyway/Liquibase Spring setup | **Flyway** (project law) | STRENGTHEN | Do not invent boot-time DDL |

**DEFER:** reactive Panache, Kafka, SSE — not default specimen path.

## Agent text

Default to Panache repositories matching legacy persistence behaviour. Keep
Flyway as the schema path. Do not add Spring Data or `quarkus-spring-data-*`.

# Persistence map (cards)

## Source

- Living map: quarkusio/skills `migrate-spring-to-quarkus` (prefer on overlap)
- Pedagogical locus: Deandrea et al., 2021, Ch 4 — cite only

## Cards

| id | Spring | Quarkus | status | note |
|----|--------|---------|--------|------|
| pers-repo | `JpaRepository` / Spring Data | Panache **repository** pattern | ADOPT | Active record allowed, not default |
| pers-em | `@PersistenceContext EntityManager` | `@Inject EntityManager` CDI | ADOPT | Valid when Panache repo does not fit (S-004) |
| pers-entity | `@Entity` JPA | `@Entity` (Jakarta) | ADOPT | `javax`→`jakarta` |
| pers-tx | `@Transactional` (Spring) | `@Transactional` (Quarkus / Narayana) | ADOPT | Same name; confirm import |
| pers-migrate | Flyway/Liquibase Spring setup | **Flyway** (project law) | STRENGTHEN | Do not invent boot-time DDL |
| pers-jdbc | Spring datasource | `quarkus-jdbc-*` matching `db-kind` + URL | ADOPT | AR-2.1 — mismatch = non-startable |
| pers-flyway-run | Flyway at boot | `quarkus-flyway` + `migrate-at-start=true` + `V*__*.sql` under `db/migration` | STRENGTHEN | Default migrate-at-start is **false** (Quarkus Flyway guide) |

### Runnable DB profile (AR-2.1 — binding)

A profile is **not** migrated until a **clean checkout** against an empty intended
DB: starts → `/q/health` → Flyway history + schema → required seed → Owner/Pet
query succeeds; **second start idempotent**. `hibernate.schema-generation=none`
without Flyway (or other schema owner) is a **BLOCK**, not ACCEPT.

Primary cites: Research `20260810-artifact-review-quarkus-cites.md` (datasource +
Flyway). Do not leave `db-kind=h2` with `jdbc:hsqldb:` URLs or non-Flyway
`initDB.sql` filenames as the default runnable path.

### EntityManager vs Panache (decide before claim)

| Prefer | When |
|--------|------|
| **Panache repository** | CRUD aligned with Spring Data method names; simple queries |
| **`@Inject EntityManager`** | Custom JPQL/merge/delete patterns; profile-specific impl merge (S-004) |
| **Neither Spring Data** | Never `quarkus-spring-data-*` |

Do **not** claim “Panache” in the completion summary unless Panache types appear
in the diff (`claim_accuracy` / S-004 lesson).

**DEFER:** reactive Panache, Kafka, SSE — not default specimen path.

## Agent text

Default to Panache repositories when they fit legacy behaviour; otherwise CDI
`EntityManager` is an acceptable Quarkus layer — name what you shipped. Keep
Flyway as the schema path. Do not add Spring Data or `quarkus-spring-data-*`.

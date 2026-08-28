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
| pers-migrate | Spring `sql.init` / Flyway / Liquibase | **one working schema mechanism** | ADOPT | Flyway only if the legacy used Flyway; else Hibernate schema generation + import/init SQL |
| pers-jdbc | Spring datasource | `quarkus-jdbc-*` matching `db-kind` + URL | ADOPT | AR-2.1 — mismatch = non-startable |
| pers-flyway-run | Flyway at boot | `quarkus-flyway` + `migrate-at-start=true` + `V*__*.sql` under `db/migration` | STRENGTHEN | Only when dest chose Flyway; default migrate-at-start is **false** |

### Runnable DB profile (AR-2.1 — binding)

A profile is **not** migrated until a **clean checkout** against an empty intended
DB: starts → `/q/health` → schema + required seed → a seeded-entity read
succeeds; **second start idempotent**. Require **one working schema mechanism**,
not a named one: Flyway complete if dest chose it, otherwise schema generation
+ import/init SQL. `hibernate.schema-generation=none` without a schema owner
is a **BLOCK**, not ACCEPT.

Primary cites: Research `20260810-artifact-review-quarkus-cites.md` (datasource).
Do not leave `db-kind=h2` with `jdbc:hsqldb:` URLs. Do not demand Flyway when
the harvest referent has none.

### Datasource kind (tip-bank B7 — Quarkus 3.27+)

**Prefer** `h2` (scaffold starter / tests), `postgresql`, or `mysql` —
extensions Quarkus still ships. **Do not** target `db-kind=hsqldb` or
`jdbc:hsqldb:` as the destination runnable profile: Quarkus dropped the
HSQLDB JDBC extension from the current catalog (extension catalog /
Quarkus JDBC guides). Legacy Spring specimens that used HSQLDB must map
to **h2 mem** (or postgres/mysql profiles), not a 1:1 hsqldb retarget.
`application-hsqldb.properties` profiles are **RETIRE candidates** — do not
mint new stories that require them. Cite AR-2.1 mismatch rules above when
URLs and `db-kind` disagree.

### EntityManager vs Panache (decide before claim)

Deep form (MappedSuperclass vs Inheritance, entity-only oracles): skill
`form-entity-persistence`.

| Prefer | When |
|--------|------|
| **Panache repository** | CRUD aligned with Spring Data method names; simple queries |
| **`@Inject EntityManager`** | Custom JPQL/merge/delete patterns; profile-specific impl merge |
| **Neither Spring Data** | Never `quarkus-spring-data-*` |

Do **not** claim “Panache” in the completion summary unless Panache types appear
in the diff (`claim_accuracy`).

### Absent result + transactions (AR-3.5)

| Topic | Rule |
|-------|------|
| `getSingleResult()` | Throws when missing — **not** null. Declare finder contract: `Optional` / null / exception; map absence to **404**, not catch-all 400. |
| HQL/JPQL | Use **entity attribute paths**, not physical column names (`pet_id`) (AR-2.5). |
| `@Transactional` | Spring vs Jakarta are **not** drop-in for propagation/isolation/timeout/read-only — disposition each non-default attribute. One layer owns each use-case transaction (AR-2.7: no load-detach-merge across two txs without `@Version`). |
| Bulk DML + `remove()` | Do not mix bulk delete with managed `remove()` on the same instances in one flow. |

**DEFER:** reactive Panache, Kafka, SSE — not default specimen path.

## Agent text

Default to Panache repositories when they fit legacy behaviour; otherwise CDI
`EntityManager` is an acceptable Quarkus layer — name what you shipped. Use
Flyway when the legacy did; otherwise schema generation + import/init SQL.
Do not add Spring Data or `quarkus-spring-data-*`.
Name absent-result and transaction ownership in the completion summary when
touched.

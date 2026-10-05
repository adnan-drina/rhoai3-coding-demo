# Persistence map (cards)

## Source

- Living map: quarkusio/skills `migrate-spring-to-quarkus` (prefer on overlap
  for annotation/Jakarta rows)
- **This specimen:** ADR-004 in `decisions.yaml` — Spring Data JPA on
  `quarkus-spring-data-jpa`. Playbook:
  `references/spring-data-jpa.md`. Official guide:
  https://quarkus.io/version/3.27/guides/spring-data-jpa
- Pedagogical locus: Deandrea et al., 2021, Ch 4 — cite only

## Cards

| id | Spring | Quarkus | status | note |
|----|--------|---------|--------|------|
| pers-repo | `JpaRepository` / Spring Data | **same interfaces** on `quarkus-spring-data-jpa` (supported subset) | ADOPT | ADR-004. Not Panache for this specimen. See `spring-data-jpa.md` |
| pers-em | `@PersistenceContext EntityManager` | `@Inject EntityManager` CDI | ADOPT | Custom JPQL the Spring Data subset cannot express |
| pers-entity | `@Entity` JPA | `@Entity` (Jakarta) | ADOPT | `javax`→`jakarta` |
| pers-tx | `@Transactional` (Spring) | `@Transactional` (Quarkus / Narayana) | ADOPT | Same name; confirm import |
| pers-migrate | Spring `sql.init` / Flyway / Liquibase | **one working schema mechanism** | ADOPT | Flyway only if the legacy used Flyway; else Hibernate schema generation + import/init SQL |
| pers-jdbc | Spring datasource | `quarkus-jdbc-*` matching `db-kind` + URL | ADOPT | AR-2.1 — mismatch = non-startable. JDBC **repositories** are retired (ADR-004) |
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
Quarkus JDBC guides). This specimen's destination is PostgreSQL 16
(ADR-009). Legacy Spring HSQLDB is the frozen source baseline, not the dest
engine. Cite AR-2.1 mismatch rules above when URLs and `db-kind` disagree.

### Persistence choice (this specimen — ADR-004)

| Prefer | When |
|--------|------|
| **Spring Data JPA** (`quarkus-spring-data-jpa`) | Default. Keep `JpaRepository` / `CrudRepository` / fragments inside the [supported subset](https://quarkus.io/guides/spring-data-jpa) |
| **`@Inject EntityManager`** | Custom JPQL/merge/delete the subset cannot express |
| **Panache** | Not the default here. Only with an ADR that supersedes ADR-004 |

Do **not** claim “Panache” in the completion summary unless Panache types appear
in the diff (`claim_accuracy`). Do **not** add a second `quarkus-spring-data-*`
GAV or a freehand version — the BOM from `.hermes/pins.json` is the version.

### Absent result + transactions (AR-3.5)

| Topic | Rule |
|-------|------|
| `getSingleResult()` | Throws when missing — **not** null. Declare finder contract: `Optional` / null / exception; map absence to **404**, not catch-all 400. |
| HQL/JPQL | Use **entity attribute paths**, not physical column names (`pet_id`) (AR-2.5). |
| `@Transactional` | Spring vs Jakarta are **not** drop-in for propagation/isolation/timeout/read-only — disposition each non-default attribute. One layer owns each use-case transaction (AR-2.7: no load-detach-merge across two txs without `@Version`). |
| Bulk DML + `remove()` | Do not mix bulk delete with managed `remove()` on the same instances in one flow. |

**DEFER:** reactive Panache, Kafka, SSE — not default specimen path.

## Agent text

This specimen keeps Spring Data JPA repositories on `quarkus-spring-data-jpa`
(ADR-004). Stay inside the supported subset; put unsupported methods on a
fragment or an explicit JPQL `@Query`. Repair every applicable method in one
repository together (`references/spring-data-jpa.md`). Use CDI `EntityManager`
only when the subset cannot express the query. Do not add Panache to clear a
build-time parse failure. Name absent-result and transaction ownership in the
completion summary when touched.

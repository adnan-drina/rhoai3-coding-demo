# Extension — JDBC write-first / anti-essay (AD-011 / R-M3.10)

**Skill:** `spring-to-quarkus-patterns`  
**Layer:** B (L2 reference overlay)  
**Sources:** Architect R-AD011.2 · R-M3.10 `E-20260810T184700Z`

This file is an **additive** extension. Workers must `skill_view` the base
`spring-to-quarkus-patterns` skill **and** this path when migrating
`repository/jdbc/**` (Hermes does not merge overlays).

## Rules

1. **Write-first** — migrate one JDBC repository file at a time from checkpoint `next`.
2. **Mechanical map** — Spring `JdbcTemplate` / `NamedParameterJdbcTemplate` /
   `OneToManyResultSetExtractor` → keep extractor shape; do not redesign the
   persistence architecture in Reasoning.
3. **Anti-essay** — forbid multi-kB Spring-on-Quarkus classpath redesign debates.
   Cite base `references/persistence.md` + this note; then edit.
4. **Deps** — run `check-jdbc-deps-preflight.py` before first JDBC write; do not
   OOS-edit `pom.xml`.
5. **Never SOUL** — behavior changes belong here or in a workshop overlay, not
   in `SOUL.md`.

### Tip-bank B3 — CDI / MapStruct (v13 M4 REFUSE → PROVISIONAL_ACCEPT)

6. **No CDI `JdbcTemplate` bean** — Quarkus has no producer for Spring
   `JdbcTemplate`. Inject Agroal `javax.sql.DataSource` / `jakarta` DataSource
   and construct `new JdbcTemplate(dataSource)` in the repository ctor (or
   migrate to Panache / raw JDBC). Never `@Inject JdbcTemplate`.
7. **MapStruct + Arc** — after mapper interface changes, require `mvn clean`
   (or clean compile) so `*MapperImpl` still `implements` the mapper interface;
   stale bytecode → Arc `UnsatisfiedResolutionException` at boot.
8. **JDK** — floor/`mvn package` must use the pom `maven.compiler.release`
   toolchain (demo seats: JDK 21).

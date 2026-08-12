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

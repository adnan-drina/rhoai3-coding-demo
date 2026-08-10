# Testing map (cards)

## Source

- Living map: quarkusio/skills `migrate-spring-to-quarkus` (prefer on overlap)
- Pedagogical locus: Deandrea et al., 2021 — cite only
- **Primary (artifact review AR-3.3):** Research pack
  `source-analysis/external-review/20260810-artifact-review-quarkus-cites.md`
  — Quarkus testing guide (`@TestTransaction`, `@InjectMock`)

## Cards

| id | Spring | Quarkus | status | note |
|----|--------|---------|--------|------|
| test-unit | JUnit 5 + Mockito | JUnit 5 + Mockito | ADOPT | Same runner; Jakarta imports |
| test-slice | `@WebMvcTest` / `@DataJpaTest` | `@QuarkusTest` (+ `@InjectMock`) | REDESIGN | No Spring test slices |
| test-rest | MockMvc / RestAssured Spring | REST Assured + `@QuarkusTest` | ADOPT | Hit real JAX-RS stack |
| test-tx | Spring test `@Transactional` rollback | **`@TestTransaction`** for rollback; ordinary `@Transactional` **persists** | ADOPT | AR-3.3 — do **not** assume `@QuarkusTest` auto-rolls back |
| test-mock | `@MockBean` | `@InjectMock` + `quarkus-junit-mockito` | ADOPT | Scope restrictions apply (see Quarkus mock support) |
| test-security | `@WithMockUser` | Quarkus security test helpers / identity | REDESIGN | Do not claim Spring Security test APIs |

**DEFER:** Testcontainers / Dev Services wiring beyond project defaults — not required for first green.

## Binding (AR-3.3 / AR-2.8)

1. **`@QuarkusTest` does not auto-rollback.** Use `@TestTransaction` when the
   test must leave the DB unchanged; prove fixture counts unchanged after
   randomized rollback tests.
2. **`@InjectMock`** requires BOM-matched `quarkus-junit-mockito` and respects
   bean scopes — document if `convertScopes` is needed.
3. Acceptance tests must cover **product** behavior (CRUD statuses, mappings,
   validation, tx, security, intended DB) — harness probes are **not**
   acceptance evidence (AR-3.6).

## Agent text

Prefer `@QuarkusTest` for REST/service IT. Do not invent Spring Boot test
annotations. Name technologies that appear in the diff only (`claim_accuracy`).
Never claim “tests roll back” unless `@TestTransaction` (or equivalent) is in
the diff.

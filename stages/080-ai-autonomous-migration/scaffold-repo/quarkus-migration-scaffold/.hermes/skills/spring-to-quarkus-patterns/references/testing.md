# Testing map (cards)

## Source

- Living map: quarkusio/skills `migrate-spring-to-quarkus` (prefer on overlap)
- Pedagogical locus: Deandrea et al., 2021 — cite only

## Cards

| id | Spring | Quarkus | status | note |
|----|--------|---------|--------|------|
| test-unit | JUnit 5 + Mockito | JUnit 5 + Mockito | ADOPT | Same runner; Jakarta imports |
| test-slice | `@WebMvcTest` / `@DataJpaTest` | `@QuarkusTest` (+ `@InjectMock`) | REDESIGN | No Spring test slices |
| test-rest | MockMvc / RestAssured Spring | REST Assured + `@QuarkusTest` | ADOPT | Hit real JAX-RS stack |
| test-tx | `@Transactional` test helpers | `@Transactional` / Quarkus test tx | ADOPT | Confirm import |
| test-security | `@WithMockUser` | Quarkus security test helpers / identity | REDESIGN | Do not claim Spring Security test APIs |

**DEFER:** Testcontainers / Dev Services wiring beyond project defaults — not required for first green.

## Agent text

Prefer `@QuarkusTest` for REST/service IT. Do not invent Spring Boot test
annotations. Name technologies that appear in the diff only (`claim_accuracy`).

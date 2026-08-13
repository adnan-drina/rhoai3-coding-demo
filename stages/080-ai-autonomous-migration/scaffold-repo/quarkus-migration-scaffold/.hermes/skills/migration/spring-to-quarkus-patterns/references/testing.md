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

## Binding (AR-3.3 / AR-2.8 / S-010 Class A)

1. **`@QuarkusTest` does not auto-rollback.** Use `@TestTransaction` when the
   test must leave the DB unchanged; prove fixture counts unchanged after
   randomized rollback tests.
2. **`@InjectMock`** requires BOM-matched `quarkus-junit-mockito` and respects
   bean scopes — document if `convertScopes` is needed.
3. Acceptance tests must cover **product** behavior (CRUD statuses, mappings,
   validation, tx, security, intended DB) — harness probes are **not**
   acceptance evidence (AR-3.6).
4. **Toolchain:** scaffold `pom.xml` ships `assertj-core` + `rest-assured`
   (test scope). Prefer AssertJ `assertThat` over inventing a new library.
   After writing tests, run `mvn -q test-compile` in-loop
   (`governance/contracts/test-toolchain.md`).
5. **`quarkus.test.continuous-testing` enum (R-M3.59 / S-008 Class B):** valid
   values are `disabled` | `enabled` | `paused` only. Never write
   `false`/`true` — Quarkus rejects them (`SRCFG00049`) and `mvn test` fails
   before suites run. Prefer `disabled` for CI/`mvn test`. Golden snippet:
   `governance/fixtures/testing/golden-test-application.properties`.

## Agent text

Prefer `@QuarkusTest` for REST/service IT. Do not invent Spring Boot test
annotations. Name technologies that appear in the diff only (`claim_accuracy`).
Never claim “tests roll back” unless `@TestTransaction` (or equivalent) is in
the diff.

## Failure / Import / Mock procedures (≤40 lines — open this section first)

**Canonical import:** `io.quarkus.test.InjectMock` (artifact `quarkus-junit-mockito`
in pom). If `test-compile` fails, read the pom artifactId — **do not invent**
`junit5.mockito` / alternate packages.

**Mock granularity (stops 500/NPE loops):**
- If the controller calls a **Mapper** and you `@InjectMock` it → stub **every**
  method on the request path (default null ⇒ 500).
- Prefer MockMvc-isolation ports: `@InjectMock` the **service** above the mapper
  + REST Assured (card `test-rest-isolation`).
- Never leave happy-path mapper/service mocks unstubbed.

**Isolation card `test-rest-isolation`:** legacy MockMvc + `@MockBean(service)` →
Quarkus `@QuarkusTest` + `@InjectMock` **service** + REST Assured hitting the
real JAX-RS stack. Copy once:
`governance/fixtures/testing/golden-rest-controller/PetTypeRestControllerTests.java`

**Failure triage (red tests — once per failure class):**
1. Classify 400 vs 500 vs assertion.
2. For 500: open server log once; check unstubbed mocks.
3. Only then rewrite the test.
4. After the first green controller test in this task: **do not restate** the
   Spring→Quarkus map — copy the established pattern.

**Ack scripts:** exit 1 always means gate fail — do not reinterpret a
`status: acknowledged` substring inside FAIL output.

**Out of scope here:** AD-009 provider/connect faults (not skill-fixable).

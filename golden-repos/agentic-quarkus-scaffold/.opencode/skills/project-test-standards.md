# Skill: Project test standards

How this team tests. Apply on every change.

- Every REST endpoint gets a `@QuarkusTest` with RestAssured covering the
  happy path and at least one failure path.
- Test names describe behavior (`returnsNotFoundForUnknownClaim`), not
  methods (`testGet2`).
- Never weaken an assertion, delete a test, or raise a threshold to make a
  gate pass — fix the code. If a gate failure looks wrong, say so and stop.
- Business logic lives in `@ApplicationScoped` services tested with plain
  JUnit where possible; keep `@QuarkusTest` for the HTTP boundary.
- `mvn -q test` must pass locally before any push; the platform pipeline's
  SonarQube gate fails on any new issue.

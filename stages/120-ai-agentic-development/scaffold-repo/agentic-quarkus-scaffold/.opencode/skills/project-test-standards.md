# Skill: Project test standards

How this team tests. Apply on every change.

- Every REST endpoint gets a `@QuarkusTest` with RestAssured covering the
  happy path and at least one failure path.
- Every service ships a `HealthResourceTest` asserting `/q/health` returns
  200 with `status: UP` — the platform probes depend on it.
- List endpoints assert both content and size, leveraging the
  repository's deterministic seed order:
  `.body("itemId", contains("329299", "329199", "165613"))` plus
  `.body("$", hasSize(3))`. (Reference: `coolstore-inventory-service`.)
- Test names describe behavior (`returnsNotFoundForUnknownClaim`), not
  methods (`testGet2`).
- Never weaken an assertion, delete a test, or raise a threshold to make a
  gate pass — fix the code. If a gate failure looks wrong, say so and stop.
- Business logic lives in `@ApplicationScoped` services tested with plain
  JUnit where possible; keep `@QuarkusTest` for the HTTP boundary.
- Decimal JSON fields (prices, quantities): never assert with exact float
  equality — Jackson may render `10.00` as `10.0`. The complete working
  setup (copy exactly — `numberReturnType` takes the **enum**, not a
  class):

  ```java
  import static io.restassured.config.JsonConfig.jsonConfig;
  import static org.hamcrest.Matchers.comparesEqualTo;
  import io.restassured.RestAssured;
  import io.restassured.path.json.config.JsonPathConfig;
  import org.junit.jupiter.api.BeforeAll;

  @BeforeAll
  static void bigDecimalJson() {
      RestAssured.config = RestAssured.config().jsonConfig(
          jsonConfig().numberReturnType(JsonPathConfig.NumberReturnType.BIG_DECIMAL));
  }
  // then:
  .body("price", comparesEqualTo(new BigDecimal("10.00")))
  ```
- Never assert list responses by position (`[0].price`) — JSON array
  order is not part of the API contract, and positional assertions
  break on any seed reorder. Match by business key with a Groovy find
  closure:

  ```java
  .body("find { it.itemId == '329299' }.price",
        comparesEqualTo(new BigDecimal("10.00")))
  ```
- External HTTP dependencies are mocked in tests with WireMock — the
  canonical dependency is `org.wiremock:wiremock` in `test` scope; tests
  must pass with no live downstream service available. Beware: the
  artifact moved to `org.wiremock` but the **packages are still
  `com.github.tomakehurst.wiremock.*`** — and WireMock's JUnit5
  extension does not integrate with `@QuarkusTest` configuration. The
  only supported pattern here is a `QuarkusTestResourceLifecycleManager`
  that starts WireMock and overrides the client's config property:

  ```java
  import com.github.tomakehurst.wiremock.WireMockServer;
  import io.quarkus.test.common.QuarkusTestResourceLifecycleManager;
  import java.util.Map;

  public class InventoryWireMockResource implements QuarkusTestResourceLifecycleManager {
      private WireMockServer server;

      @Override
      public Map<String, String> start() {
          server = new WireMockServer(0);  // random free port
          server.start();
          return Map.of("catalog.inventory.url", server.baseUrl());
      }

      @Override
      public void stop() { if (server != null) server.stop(); }
  }
  ```

  Annotate the test class with
  `@QuarkusTestResource(InventoryWireMockResource.class)` (plus
  `@QuarkusTest`), keep a static reference or re-register stubs per
  test, and stub with the static DSL from
  `com.github.tomakehurst.wiremock.client.WireMock`:

  ```java
  server.stubFor(get(urlEqualTo("/api/inventory/329299/availability"))
      .willReturn(okJson("{\"itemId\":\"329299\",\"available\":true,\"quantity\":35}")));
  server.stubFor(get(urlPathMatching("/api/inventory/999999/.*"))
      .willReturn(aResponse().withStatus(404)));
  // timeout path: delay beyond the client timeout
  server.stubFor(get(urlPathMatching("/api/inventory/165613/.*"))
      .willReturn(okJson("{}").withFixedDelay(3000)));
  ```
- Per-test config overrides have exactly two mechanisms: a
  `QuarkusTestProfile` with `getConfigOverrides()`, or the WireMock
  `QuarkusTestResourceLifecycleManager`'s `start()` override map (the
  preferred pattern here). Any other config-override annotation you
  recall does not exist in Quarkus.
- `mvn -q test` must pass locally before any push; the platform pipeline's
  SonarQube gate fails on any new issue.

## Coverage attribution (the gate's instrument)

The factory coverage gate reads JaCoCo, and JaCoCo does NOT attribute
lines executed inside `@QuarkusTest` runs. Service/model coverage must
come from plain JUnit 5 + Mockito tests; `@QuarkusTest` exists for the
HTTP boundary, not for the coverage number. Converting plain unit tests
to `@QuarkusTest` reduces measured coverage even when behavior coverage
is identical.

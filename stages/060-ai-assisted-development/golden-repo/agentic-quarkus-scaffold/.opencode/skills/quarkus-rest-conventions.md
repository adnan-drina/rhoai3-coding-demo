# Skill: Quarkus REST conventions

How this team builds REST endpoints. Apply on every endpoint change.

- All resources live under the `/api/` path prefix.
- The path segment is named for the domain/service, not the entity type:
  `@Path("catalog")` for the catalog service (as inventory exposes
  `/api/inventory`) — never `@Path("products")` after the `Product` record.
  The spec's stated path is authoritative; do not re-derive it from the model.
- Resource classes end in `Resource`, live in `com.demo.<domain>`, and use
  constructor injection only — never field injection (`@Inject` on fields).
  SonarQube flags `@Inject` fields as a new issue, which fails the
  pipeline quality gate. The pattern:

  ```java
  public class CatalogResource {
      private final ProductRepository repository;

      public CatalogResource(ProductRepository repository) {
          this.repository = repository;
      }
  }
  ```

  (No `@Inject` needed on a single constructor — CDI resolves it.)
- Request/response bodies are Java records serialized with Jackson; never
  expose entities directly. Records are data-only: no business logic in
  records or their static factories — enrichment, mapping decisions, and
  fallbacks live in services and resources, where they can be injected
  and tested. Java records cannot extend anything — a projection
  duplicates the base fields and adds its own; never plan a record
  "extending" another type. Each distinct response shape gets its own
  record — a projection like an availability summary is its own record
  (`InventoryAvailability(itemId, available, quantity)`), not a trimmed
  reuse of the entity. (Reference: `coolstore-inventory-service`.)
- In-memory repositories are `@ApplicationScoped` beans holding a
  `LinkedHashMap` keyed by the business id — insertion order makes list
  responses and their tests deterministic. Lookups return
  `Optional<T>`; list methods return immutable snapshots
  (`List.copyOf(...)`). Seed data lives in the repository constructor.
- Resources convert an empty `Optional` to 404 in exactly one private
  helper (`requireItem(itemId)`) that throws
  `jakarta.ws.rs.NotFoundException` with a descriptive message — no
  duplicated orElseThrow chains per endpoint. Use `@ServerExceptionMapper`
  (below) when the spec requires an RFC-7807 body on top of the 404.
- Projections of a resource are sub-paths of it:
  `/api/inventory/{itemId}/availability`, not a new top-level path.
- Errors return RFC-7807-style JSON (`status`, `title`, `detail`) with
  `Content-Type: application/problem+json` — no empty catch blocks, no
  stack traces in responses. Map exceptions with the Quarkus-native
  `@ServerExceptionMapper` (package
  `org.jboss.resteasy.reactive.server`), which is always discovered:

  ```java
  @ServerExceptionMapper
  public Response mapNotFound(ProductNotFoundException e) {
      return Response.status(404)
          .type("application/problem+json")
          .entity(Map.of("status", 404, "title", "Not Found",
                         "detail", e.getMessage()))
          .build();
  }
  ```

  Name the mapper class after the domain (`CatalogExceptionMappers`) —
  a class named `ServerExceptionMapper` collides with the imported
  annotation and fails compilation with "already defined in this
  compilation unit".
  Do not fall back to inlining error responses in resource methods, and
  never use `@RegisterProvider` — that annotation belongs to the
  MicroProfile REST *Client* and does not exist in `jakarta.ws.rs.ext`.
  `jakarta.ws.rs.core.MediaType` has **no** problem+json constant
  (`APPLICATION_PROBLEM_JSON` / `_TYPE` do not exist) — always use the
  string literal `"application/problem+json"`.
- Money and prices are `BigDecimal`, constructed from string literals
  (`new BigDecimal("34.99")`) — never `double` literals (they do not
  convert implicitly and lose precision). Jackson serializes `BigDecimal`
  as a plain JSON number.
- Log through `org.jboss.logging.Logger` (one static logger per class);
  `System.out.println` is forbidden.
- Every endpoint gets an OpenAPI-visible description: meaningful method
  names, `@Produces`/`@Consumes` declared explicitly.
- `application.properties` always sets `quarkus.application.name` (and
  keeps `quarkus.http.port=8080`).
- Update the README API table in the same change as any endpoint change.
  The README follows the reference layout: a Technology table, the API
  table with base path, and JSON examples of each resource shape. The
  service root (`/`) serves a small `META-INF/resources/index.html`
  landing page linking every endpoint.
- Gate hygiene before declaring any change done: the pipeline's
  SonarQube gate fails on **any** new issue, including minor smells.
  The hygiene pass is an action, not an attestation — never tick a
  "verify no issues" task without performing it. The procedure:
  1. `git status --short` / `git diff --name-only` to enumerate **every**
     touched file yourself — main sources, tests, and test fixtures alike;
     do not rely on a list from memory.
  2. For each file: read the full import block — including
     `import static` lines — and delete every import not referenced in
     the file body (edit-cycle leftovers are the most common gate
     failure).
  3. Remove dead code and debugging artifacts. Java 17+
  API rules Sonar enforces: use `Stream.toList()` instead of
  `.collect(Collectors.toList())`.

## Calling other services (REST client)

Service-to-service calls use the MicroProfile REST client — never a
hand-rolled Vert.x/HTTP client. Dependency: `quarkus-rest-client-jackson`.
The complete pattern (copy exactly):

```java
@RegisterRestClient(configKey = "inventory")
@Path("/api/inventory")
public interface InventoryClient {
    @GET
    @Path("/{itemId}/availability")
    InventoryAvailability availability(@PathParam("itemId") String itemId);
}
```

Wire the domain config property to the client key in
`application.properties`. When the spec names the property (e.g.
`catalog.inventory.url`), that name is the contract — the rest-client
key maps to it and never replaces it; tests and clusters then only
override the domain property:

```properties
catalog.inventory.url=http://coolstore-inventory-service.coolstore-dev.svc:8080
quarkus.rest-client.inventory.url=${catalog.inventory.url}
quarkus.rest-client.inventory.connect-timeout=2000
quarkus.rest-client.inventory.read-timeout=2000
```

Inject with the `@RestClient` qualifier — still constructor injection:

```java
public CatalogResource(@RestClient InventoryClient inventory, ...) { ... }
```

Failure handling for graceful degradation: a 404 from the remote
surfaces as `WebApplicationException`, timeouts and connection failures
as `ProcessingException` — catch both, log a WARNING, return the
degraded value. Do not invent wrapper/error DTOs for this.

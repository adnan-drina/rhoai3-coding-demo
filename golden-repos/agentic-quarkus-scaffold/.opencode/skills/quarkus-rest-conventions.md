# Skill: Quarkus REST conventions

How this team builds REST endpoints. Apply on every endpoint change.

- All resources live under the `/api/` path prefix.
- Resource classes end in `Resource`, live in `com.demo.<domain>`, and use
  constructor injection only — never field injection (`@Inject` on fields).
- Request/response bodies are records or simple POJOs serialized with
  Jackson; never expose entities directly.
- Errors return RFC-7807-style JSON (`status`, `title`, `detail`) via an
  `ExceptionMapper` — no empty catch blocks, no stack traces in responses.
- Log through `org.jboss.logging.Logger` (one static logger per class);
  `System.out.println` is forbidden.
- Every endpoint gets an OpenAPI-visible description: meaningful method
  names, `@Produces`/`@Consumes` declared explicitly.
- Update the README API table in the same change as any endpoint change.

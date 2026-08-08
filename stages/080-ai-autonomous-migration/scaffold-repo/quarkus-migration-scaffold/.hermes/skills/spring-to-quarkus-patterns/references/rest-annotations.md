# REST annotation map (cards)

Paraphrased public API names. Prefer living Full-path from
`quarkusio/skills` `migrate-spring-to-quarkus` when present.

## Source

- Primary living map: quarkusio/skills (Apache-2.0)
- Pedagogical locus: Deandrea et al., *Quarkus for Spring Developers*, 2021,
  Tables 3.1–3.2 (cite only; not verbatim)

## Cards

| id | Spring | Quarkus (`quarkus-rest`) | status | note |
|----|--------|--------------------------|--------|------|
| rest-resource | `@RestController` / `@Controller` | `@Path` on resource class | ADOPT | Class is a JAX-RS resource |
| rest-get | `@GetMapping` | `@GET` + `@Path` | ADOPT | |
| rest-post | `@PostMapping` | `@POST` + `@Path` | ADOPT | |
| rest-put | `@PutMapping` | `@PUT` + `@Path` | ADOPT | |
| rest-delete | `@DeleteMapping` | `@DELETE` + `@Path` | ADOPT | |
| rest-path-var | `@PathVariable` | `@PathParam` | ADOPT | Table 3.2 locus |
| rest-query | `@RequestParam` | `@QueryParam` | ADOPT | |
| rest-header | `@RequestHeader` | `@HeaderParam` | ADOPT | |
| rest-body | `@RequestBody` | unannotated entity param / `@Consumes` | ADOPT | |
| rest-response-status | `@ResponseStatus` | `Response.status(...)` or exception mapper | ADOPT | |
| rest-advice | `@RestControllerAdvice` / `@ExceptionHandler` | `@ServerExceptionMapper` | ADOPT | Pair with problem+json if project uses it |

**REJECT:** Spring MVC stack on destination; `quarkus-spring-web` compat.

## Agent text

Map Spring Web annotations to JAX-RS (`quarkus-rest`). Keep `/api/` root and
Jackson JSON. Do not invent endpoints absent from legacy/brief.

# REST annotation map (cards)

Paraphrased public API names. Prefer living Full-path from
`quarkusio/skills` `migrate-spring-to-quarkus` when present.

## Source

- Primary living map: quarkusio/skills (Apache-2.0)
- Pedagogical locus: Deandrea et al., *Quarkus for Spring Developers*, 2021,
  Tables 3.1–3.2 (cite only; not verbatim)
- **Primary (artifact review AR-3.4):** Research pack
  `source-analysis/external-review/20260810-artifact-review-quarkus-cites.md`
  — Quarkus validation guide (REST `@Valid`)

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
| rest-valid | `@Valid` + `BindingResult` | Endpoint `@Valid` **or** manual validation — pick one strategy | ADOPT | AR-3.4 — `@Valid` runs before/with method; builtin violation mapper |
| rest-wildcard | Spring `/**` / `*` path patterns | Jakarta URI **templates** (`{param}` / regex in `{param:regex}`) | REDESIGN | Literal `*` in `@Path` is **not** a wildcard (AR-2.4) |
| rest-response-status | `@ResponseStatus` | `Response.status(...)` or exception mapper | ADOPT | |
| rest-advice | `@RestControllerAdvice` / `@ExceptionHandler` | `@ServerExceptionMapper` / `ExceptionMapper` | ADOPT | Do not map all `Exception` → 400 (AR-2.6) |

**REJECT:** Spring MVC stack on destination; `quarkus-spring-web` compat.

### Tip-bank B3 — discovery / CDI (v13 M5 JAX-RS 404)

| id | Spring habit | Quarkus rule | status |
|----|--------------|--------------|--------|
| rest-cdi-scope | implicit Spring component scan | `@ApplicationScoped` (or `@Singleton`) on every `@Path` resource + exception mappers | ADOPT |
| rest-package | keep `org.springframework.samples…` | **Move** JAX-RS resources out of `org.springframework.*` — Quarkus build-time discovery skips that prefix | ADOPT |
| rest-cors | `@CrossOrigin` / filters in story | **OUT OF SCOPE** for REST stories (tip-bank B2) — platform/infra | REJECT in-story |

## Binding (AR-3.4 / AR-2.4)

1. **Path patterns:** convert Spring wildcards to Jakarta templates; never leave
   literal `*` expecting glob semantics.
2. **Validation strategy (choose explicitly):**
   - automatic: `@Valid` on params + compatible violation mapper, **or**
   - manual: no endpoint `@Valid`; controller builds legacy-shaped error bodies.
   Mixing so `@Valid` short-circuits a custom BindingResult path is a defect.
3. Designate one authoritative OpenAPI/contract and validate registered routes
   against it (parent-nested child resources vs plural top-level collections).

## Agent text

Map Spring Web annotations to JAX-RS (`quarkus-rest`). Keep `/api/` root and
Jackson JSON. Do not invent endpoints absent from legacy/brief. Prove route +
invalid-request parity (status/headers/body) for touched resources.

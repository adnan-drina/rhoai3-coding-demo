# Exception mapping (cards)

Paraphrased public API names. Prefer living Full-path from
`quarkusio/skills` `migrate-spring-to-quarkus` when present.

## Source

- Primary living map: quarkusio/skills (Apache-2.0)
- Pedagogical locus: Deandrea et al., *Quarkus for Spring Developers*, 2021,
  Ch. 3 "Exception Handling", pp. 53–56 (cite only; not verbatim)
- **Harness:** dossier D3 error-handling coverage gap; artifact review AR-2.6
- Persistence contracts: [Spring 5.3 DataAccessException](https://docs.spring.io/spring-framework/docs/5.3.x/javadoc-api/org/springframework/dao/DataAccessException.html),
  Jakarta Persistence 3.2 [EntityManager](https://jakarta.ee/specifications/persistence/3.2/apidocs/jakarta.persistence/jakarta/persistence/entitymanager),
  [PersistenceException](https://jakarta.ee/specifications/persistence/3.2/apidocs/jakarta.persistence/jakarta/persistence/persistenceexception),
  [EntityNotFoundException](https://jakarta.ee/specifications/persistence/3.2/apidocs/jakarta.persistence/jakarta/persistence/entitynotfoundexception)
  and [OptimisticLockException](https://jakarta.ee/specifications/persistence/3.2/apidocs/jakarta.persistence/jakarta/persistence/optimisticlockexception).

## Cards

| id | Spring | Quarkus (`quarkus-rest`) | status | note |
|----|--------|--------------------------|--------|------|
| exc-local | `@ExceptionHandler` method inside the `@RestController` | `@ServerExceptionMapper` method inside the resource class | ADOPT | Same per-class placement; method name is irrelevant in both |
| exc-global | Separate class **annotated `@RestControllerAdvice`** holding `@ExceptionHandler` methods | Separate **plain class, no class-level annotation**, holding `@ServerExceptionMapper` methods | ADOPT | **Load-bearing gotcha** — no Quarkus equivalent of `@RestControllerAdvice` exists, and none is needed (locus p.56) |
| exc-return | `ResponseEntity<ErrorBody>` | `Response` | ADOPT | Same two-branch shape; wrapper type swaps 1:1 |
| exc-bind-time | Bindings resolved at **runtime** | Bindings resolved at **build time** | ADOPT | A bad mapper binding surfaces at build, not on first request |
| exc-scope | Implicit component scan | `@ApplicationScoped` on the mapper-holding class | ADOPT | B3 discovery rule applies to mappers, not just resources |
| exc-package | Keep `org.springframework.samples…` | **Move** mapper classes out of `org.springframework.*` | ADOPT | Build-time discovery skips that prefix — silently unregistered otherwise |
| exc-validation | `@Valid` + `BindingResult` inspected in the handler | Built-in `ConstraintViolationException` mapper, or your own `@ServerExceptionMapper` for it | ADOPT | See exc-legacy-body for the error-shape question |
| exc-legacy-body | Legacy-named error-body wrapper class (a Spring **naming convention**) | Plain POJO you define, populated from `ConstraintViolationException` | ADOPT | Not a missing Quarkus API — do **not** hunt for an equivalent type or declare `dependency_wait`; write the POJO |
| exc-catch-all | Broad `Exception` → single status handler | Map each exception type to its correct status | REJECT | AR-2.6 — do not map all `Exception` → 400 |

**REJECT:** `quarkus-spring-web` compat layer for advice classes; Spring MVC
exception infrastructure on destination.

## Binding

1. **Global mapper = plain class.** Do not search for a class-level annotation
   to mark it, and do not conclude the capability is missing because no
   `@RestControllerAdvice` analogue appears in the destination inventory. A
   class holding `@ServerExceptionMapper` methods is complete as written.
2. **Register for discovery.** Give the mapper-holding class an explicit CDI
   scope and keep it outside `org.springframework.*`. An exception mapper that
   compiles but never fires is almost always a discovery failure, not a mapping
   failure — check scope and package before re-reading the mapping table.
3. **Preserve legacy error-body shape when the contract requires it.** A
   Spring-named error wrapper is a convention, not an API: reimplement it as a
   POJO built from the violation set. Renaming the type is allowed; changing the
   JSON field names the contract asserts is not.
4. **One status per exception type.** Blanket handlers erase the parity signal
   the invalid-request gate depends on.

## Persistence exceptions: preserve the failure category

Use for `org.springframework.dao.DataAccessException`,
`org.springframework.dao.EmptyResultDataAccessException` and
`org.springframework.orm.ObjectRetrievalFailureException` retirement. These
are unchecked exceptions; a method's `throws` clause does not make them checked.
Read the throwing operation and its callers before choosing a replacement.
`EmptyResultDataAccessException` and `ObjectRetrievalFailureException` identify
missing results; they are not aliases for every persistence failure.

1. Separate declarations from catches. Removing an unavailable unchecked type
   from a method signature does not authorize widening a not-found-only catch.
   Never replace that catch with `PersistenceException`, `RuntimeException` or
   `IllegalArgumentException`: unrelated database failures must still propagate.
2. Follow the destination operation's actual missing-result contract:
   `EntityManager.find` returns null for absence; dereferencing `getReference`
   may throw `EntityNotFoundException`; `getSingleResult` may throw
   `NoResultException`. An explicit missing-entity helper may use
   `EntityNotFoundException(String)` with its caller catching that narrow type.
   Preserve the source's null/optional/error response and required message shape.
   Do not add catch alternatives unless the called operation can produce them.
3. `OptimisticLockException` denotes a version conflict, not a missing entity.
   Do not select a replacement by name or constructor arity. Check constructors
   on the shipped API using the verifier's existing classpath; Jakarta
   Persistence 3.2 has no `OptimisticLockException(Class, int)` constructor.
4. Keep helper and caller changes within the card's file boundary. A needed
   caller outside it requires a recorded scope amendment. On a permitted
   caller, remove an earlier broad not-found catch when making this replacement;
   merely fixing a related multi-catch compile error preserves the wrong behavior.

## Verification

Prove for each touched resource: valid request → expected 2xx; invalid-request
parity (status, headers, body shape) against the legacy contract; and at least
one deliberately-triggered mapped exception returning its mapped status rather
than a container-default 500.

For persistence handling, distinguish found, missing and unrelated database
failure. The third case must not become null or a not-found response. Use the
card's official verifier; record runtime behavior still unmeasured for later
parity. This guidance grants no extra test-write scope or separate Maven gate.

## Agent text

Map Spring exception handling to JAX-RS. Local handlers become
`@ServerExceptionMapper` methods in the same class; the global advice class
becomes a plain CDI-scoped class with no class-level annotation. Reimplement
legacy error-body wrappers as POJOs from `ConstraintViolationException` — they
are Spring naming conventions, not missing Quarkus types. Never map all
`Exception` to one status.

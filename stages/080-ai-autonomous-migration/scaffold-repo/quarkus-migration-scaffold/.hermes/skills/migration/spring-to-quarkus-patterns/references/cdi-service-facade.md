# CDI service facade (R-SKILL-D)

## Injection

ArC does not prefer constructor vs field in general. **Discouraged:**
`@Inject` on **private** fields (reflection or bytecode visibility transform).
Prefer constructor injection; sole constructor needs no `@Inject`. Quarkus
generates the no-args ctor for normal-scoped beans — **except** when the class
extends a type that lacks a no-args constructor.

```java
@ApplicationScoped
public class OrderService {
  private final OrderRepository repository;
  public OrderService(OrderRepository repository) {
    this.repository = repository;
  }
}
```

## `@Transactional`

For `org.springframework.transaction.annotation.Transactional` retirement,
inspect every annotation use in the sealed files along with the import swap
to `jakarta.transaction.Transactional`. An import-only edit leaves Spring-only
attributes unresolved. Preserve transaction boundaries and rollback behavior.

Jakarta `@Transactional` is an interceptor binding. Default
`quarkus.arc.fail-on-intercepted-private-method=true` — **`@Transactional` on a
private method fails the build** (loud). Fix visibility or move the boundary.

## Spring `readOnly`

Jakarta has no `readOnly` attribute. For a source annotation using the default
transaction boundary, `@Transactional(readOnly = true)` becomes
`@Transactional`; keep the transaction rather than deleting the annotation.
Inspect any other attributes before mapping them. Do not switch to `SUPPORTS`,
`NOT_SUPPORTED` or `NEVER` to simulate read-only behavior: these change whether
the method runs in a transaction. Source flush/dirty-check behavior may need
separate evidence; removing the hint is not a universal semantic-equivalence
claim. Record any unresolved dependency on it for runtime verification.

The [Jakarta Transactions 2.0 annotation contract](https://jakarta.ee/specifications/transactions/2.0/apidocs/jakarta/transaction/transactional)
defines the boundary and rollback attributes. Use the card's official verifier
after one coherent edit of imports and applicable attributes; a clean compiler
does not establish transaction parity.

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

Jakarta `@Transactional` is an interceptor binding. Default
`quarkus.arc.fail-on-intercepted-private-method=true` — **`@Transactional` on a
private method fails the build** (loud). Fix visibility or move the boundary.

## Spring `readOnly`

Even `quarkus-spring-tx` documents `readOnly` as **Unsupported | Ignored with
a warning**. Dropping it is **correctness-neutral**. If the flush/dirty-check
hint is truly required, use query-level `org.hibernate.readOnly` /
`QueryHint.READ_ONLY`, or a different transaction type (`SUPPORTS` /
`NOT_SUPPORTED` / `NEVER`) — do not invent a Jakarta `readOnly` attribute.

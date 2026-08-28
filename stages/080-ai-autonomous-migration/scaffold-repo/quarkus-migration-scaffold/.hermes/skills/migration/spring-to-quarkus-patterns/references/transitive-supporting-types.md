# Transitive / supporting types (R-SKILL-A)

Partitioned write-sets often reference types outside `files_writable`
(DTO nests, MapStruct `uses`, association targets). That is a **typed
decision**, not a free invent or silent skip.

## Procedure

1. Enumerate the closure reachable from in-scope types (fields, `uses=`,
   association targets).
2. For each type **not** in `files_writable`:
   - **(a)** Already delivered by a prior done story → read-only import.
   - **(b)** Missing with no owner → typed block / destination-inventory
     escalation — do **not** OOS-write to "finish".
   - **(c)** Trivial leaf folded into this story → **named exception** in the
     body/receipt, not a default.
3. Detect via **compile** (MapStruct generation / unresolved type) before
   claiming done — loud beat narrative.

```java
@Mapper(uses = { LineItemMapper.class })
public interface OrderMapper {
  OrderDto toDto(Order entity); // needs LineItemDto/mapper on classpath
}
```

Do **not** stamp `componentModel = "cdi"` as required (B-3; doctrine pending
R-SKILL-F). v19 measured that shape as Unsatisfied beans.

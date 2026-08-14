# Cache adopt / defer (R-SKILL-C)

Extends `manage-quarkus-extensions` `extension-obligations.md` (`quarkus-cache`).
No Spring-compat cache extension — rewrite annotations; do not expect auto-translate.

| Spring | Quarkus |
|--------|---------|
| `@Cacheable(value="n")` | `@CacheResult(cacheName="n")` |
| `@CacheEvict(value="n")` | `@CacheInvalidate(cacheName="n")` |
| `@CacheEvict(..., allEntries=true)` | `@CacheInvalidateAll(cacheName="n")` |
| SpEL `key="#id"` | `@CacheKey` on a parameter (no SpEL) |

## Decision

Caching is **correctness-neutral** when dropped (same data, recomputed).

1. Extension present **and** method in write-set → **adopt** mapping table.
2. Extension out of scope → **defer** with a typed one-liner receipt
   ("caching deferred — `quarkus-cache` not in this story") — not a silent drop.
3. Never invent an OOS `ext add` solely to preserve cache performance.

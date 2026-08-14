# Entity-only oracles

An entity-mapping story with no query/REST write-set still has an official
executable check:

- Config: `quarkus.hibernate-orm.database.generation=validate` at boot, or
- Programmatic: `sessionFactory.getSchemaManager().validateMappedObjects()`
  inside `@QuarkusTest`.

Honest scope: proves mapping ↔ schema agreement. Does **not** prove owning-side
wiring, cascade correctness, or fetch strategy.

Do **not** stamp `hql_entity_path` / `http_semantics` on mapping-only bodies —
wrong-class (see `derive-story-oracles` / R-SKILL-E). Prefer class-legal exits
from `OPERAND_CLASS_SEMANTIC_EXITS` for the `persistence` class (`mapping_valid`
only — Architect E-20260814T181701Z). Do **not** stamp `hql_entity_path` /
`http_semantics` / `create_fk` on mapping-only bodies. `oracle_unavailable` is
forbidden for `persistence` (F5a).

HQL/JPQL: attribute paths only (`book.title`), never column names — dialects
may silently pass a column identifier, which is non-portable.

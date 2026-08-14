---
name: form-entity-persistence
description: Before authoring or reminting JPA entity / persistence-form stories — choose MappedSuperclass vs Inheritance, Panache vs EntityManager, HQL attribute paths, owning-side associations, and schema-validate oracles for entity-only write-sets; use when mapping form is the story concern
license: Apache-2.0
compatibility: Linux seat; Jakarta Persistence; Quarkus Hibernate ORM
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - migration
    - quarkus
    - persistence
    category: migration
    kind: guidance
---
# Entity / persistence form (T-7)

Guidance only (R-SK.14). Complements `spring-to-quarkus-patterns`
`references/persistence.md` cards with the **form decisions** that burn
reasoning when guessed from memory.

Deep notes: `references/entity-mapping.md`, `references/panache-vs-em.md`,
`references/entity-only-oracles.md`.

## When to Use

- M3 stories whose write-set is primarily `@Entity` / relationships /
  repositories (no REST surface of their own).
- Choosing active-record Panache vs repository / `EntityManager`.
- Before stamping query-shaped exits on an entity-only body —
  `derive-story-oracles` first.
- **Not** for datasource/profile properties — `configure-quarkus-profiles`.
- **Not** for Flyway extension add alone — `manage-quarkus-extensions`
  obligations, then this skill for mapping form.

## Procedure

1. Every entity needs declared identity (`@Id` + generation when not
   application-assigned) — see `references/entity-mapping.md`.
2. Shared attributes without polymorphic query/associate needs →
   `@MappedSuperclass`. Real is-a with polymorphic queries → `@Inheritance`
   (+ strategy trade-offs in the same reference).
3. Bidirectional associations: set the **owning** side (`@JoinColumn`);
   `mappedBy` inverse alone does not persist.
4. Choose Panache vs `EntityManager` via `references/panache-vs-em.md`
   (hierarchy/aggregate/test-doubles → repository/EM; simple CRUD → Panache
   repo OK). Panache entities attach to **one** persistence unit only.
5. HQL/JPQL paths use **entity attribute names**, never column names
   (vendor-specific silent pass if column happens to match — not portable).
6. Entity-only done criteria: prefer schema validate
   (`references/entity-only-oracles.md`) — not HTTP or HQL exits with no
   query write-set.

## Pitfalls

- `@Inheritance` vs `@MappedSuperclass` chosen by habit, not query/associate
  needs.
- Persisting only the inverse side of a bidirectional association.
- Claiming "Panache" without Panache types in the diff.
- `hql_entity_path` / `http_semantics` exits on mapping-only stories
  (wrong-class — T-8 / R-SKILL-E).
- Treating schema-validate as proof of relationship semantics.

## Verification

- Identity present on every new entity.
- Owning-side fields set in write paths that create associations.
- Exits class-legal per `derive-story-oracles` /
  `check-surgical-scopes.py`.
- Entity-only: validate-mapped-objects / `database.generation=validate`
  style oracle preferred.

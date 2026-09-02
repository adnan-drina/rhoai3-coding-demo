---
name: form-entity-persistence
description: Before authoring JPA entity / persistence-form stories or M3 PROVISION_DATABASE — choose MappedSuperclass vs Inheritance, Panache vs EntityManager, and copy k8s-templates postgres into k8s/ only when harvest database.needed is true; use when mapping form or datasource provisioning is the story concern. Not for datasource profile properties (configure-quarkus-profiles) and not for a cut-time needsDatabase checkbox.
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
- M3 `PROVISION_DATABASE` (kind `database`): copy
  `k8s-templates/postgres.yaml` to `k8s/postgres.yaml` and merge
  `k8s-templates/app-datasource-env.yaml` into `k8s/app.yaml` **iff**
  `evidence/required-extensions.json` `database.needed` is true. K4
  mints this story; do not invent postgres for a greeting harvest.
- Choosing active-record Panache vs repository / `EntityManager`.
- Before stamping query-shaped exits on an entity-only body —
  `derive-story-oracles` first.
- **Not** for datasource/profile properties — `configure-quarkus-profiles`.
- **Not** for Flyway extension add alone — `manage-quarkus-extensions`
  obligations, then this skill for mapping form.
- **Not** a Developer Hub checkbox — harvest is the only provision signal.

## Procedure

1. Every entity hierarchy has exactly one effective identity (inherited
   `@Id` / `@EmbeddedId` counts) — `references/entity-mapping.md`. Run
   `scripts/assert-inherited-id-not-redeclared.py` on the destination.
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

- Identity present once per hierarchy (inherited `@Id` counts).
  `scripts/assert-inherited-id-not-redeclared.py` exit 0.
- Owning-side fields set in write paths that create associations.
- Exits class-legal per `derive-story-oracles` /
  `check-surgical-scopes.py`.
- Entity-only: validate-mapped-objects / `database.generation=validate`
  style oracle preferred.

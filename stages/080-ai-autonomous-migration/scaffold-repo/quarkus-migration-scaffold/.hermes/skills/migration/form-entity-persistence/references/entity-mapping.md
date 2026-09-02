# Entity mapping form

## Identity

Every entity hierarchy has **exactly one** effective identity. An inherited
`@Id` / `@EmbeddedId` on a `@MappedSuperclass` (or parent `@Entity`) counts.
Do not redeclare `@Id` on a subclass. Not optional.

`scripts/assert-inherited-id-not-redeclared.py` REFUSE a dest type that
declares `@Id`/`@EmbeddedId` when an ancestor already does.

## `@MappedSuperclass` vs `@Inheritance`

| | `@MappedSuperclass` | `@Inheritance` |
|--|---------------------|----------------|
| DB visibility | Invisible — attributes copied into subclass tables | Visible hierarchy in schema |
| Polymorphic `SELECT` on base | Not possible | Possible (the point of Inheritance) |
| Association *to* the shared base | Not possible | Possible (strategy-dependent) |
| When | Share mapping code; no query/associate against base | Real is-a needing polymorphic access |

Strategies when `@Inheritance` is chosen:

- **SINGLE_TABLE** (JPA default): one table + discriminator; fast reads;
  subclass-only columns cannot be DB `NOT NULL`.
- **JOINED**: subclass tables hold only subclass columns; better
  normalization; joins on fetch.
- **TABLE_PER_CLASS**: concrete class tables with full state; polymorphic
  queries need `UNION`.

## Owning vs inverse

Exactly one owning side carries the FK (`@JoinColumn`). Inverse uses
`mappedBy`. Updates only through the inverse side have **no** database
effect — compile/run clean, relationship missing.

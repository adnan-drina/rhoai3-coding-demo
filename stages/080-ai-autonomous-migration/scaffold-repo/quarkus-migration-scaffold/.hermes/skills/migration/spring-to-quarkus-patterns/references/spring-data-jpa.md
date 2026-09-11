# Spring Data JPA on Quarkus (this specimen)

ADR-004 is the accepted persistence decision: destination repositories are
the Spring Data JPA implementation (`quarkus-spring-data-jpa`, the legacy
`spring-data-jpa` profile). JDBC and plain-JPA profile implementations are
retired. Do **not** rewrite those interfaces as Panache for this specimen.

Official guide (Quarkus 3.27 line): https://quarkus.io/version/3.27/guides/spring-data-jpa
(also https://quarkus.io/guides/spring-data-jpa). Generation is **build-time**.
Unsupported methods fail as `UnableToParseMethodException` at augment, not at
a later HTTP call.

The catalog (`compat-mapping.json`) maps `spring-boot-starter-data-jpa` →
`quarkus-spring-data-jpa` + `quarkus-hibernate-orm`. Version comes from the
pinned BOM in `.hermes/pins.json` (`quarkus_platform`). Do not add a
freehand version. Do not add `quarkus-spring-data-jpa` a second time.

## Supported (keep these shapes)

Interfaces that extend any of:

- `org.springframework.data.repository.Repository`
- `CrudRepository` / `ListCrudRepository`
- `PagingAndSortingRepository` / `ListPagingAndSortingRepository`
- `org.springframework.data.jpa.repository.JpaRepository`

Derived query methods that follow Spring Data naming (including `Between`,
`OrderBy`, `Top`, `IgnoreCase`, `Pageable`/`Sort`/`Slice`/`Stream` where the
guide shows them). `@Query` JPQL (not native, not named). `@Modifying` on a
real `UPDATE`/`DELETE`/`INSERT`. Writes that `CrudRepository` already
provides (`save`, `delete`, `deleteById`, …) stay inherited — do not add a
bare `@Query` to silence derivation.

Fragments: extra methods live on a fragment interface + `*Impl` class, as
in the guide's "repository fragments" section.

## Unsupported (do not keep, do not fake)

From the same guide, currently unsupported:

- `QueryByExampleExecutor` methods (runtime exception if invoked)
- QueryDSL repositories
- `JpaSpecificationExecutor`
- customizing the global base repository (`SimpleJpaRepository` is unused)
- `java.util.concurrent.Future` (and subclasses) as repository return types
- native and named queries on `@Query`
- `EntityInformation` state-detection strategies
- `org.springframework.data.jpa.repository.Lock`

Also out of the supported subset in practice (build-time parser): stored
`@Procedure`, nested camel-case property paths the parser cannot split, and
methods with no `By` clause and no `@Query`. Those need an explicit JPQL
`@Query`, a fragment implementation, or an Operator ADR — not Panache, not a
bare `@Query` on a write.

## Batching (one transformation, then stop)

The platform names **one member per obligation**. Repairing only that member
returns the next sibling as a new card (pilot v7: `save` / `delete` /
`findById` / `findAll` each cost a full verify).

1. Inventory **this** repository: inherited methods, entity and ID types,
   signatures, `@Query` / `@Modifying`, callers in the write set, transaction
   attributes. The brief carries that inventory when the path is a
   `*Repository.java`.
2. Repair **all applicable methods in that one repository** in the same
   candidate, using one transformation (example: drop local `save`/`delete`
   and extend `CrudRepository<T,ID>`; or add JPQL `@Query` on finders the
   parser cannot derive).
3. Batch **across** repositories only when the same transformation and
   preconditions apply (same missing fragment, same write-inheritance gap).
   Keep separate candidates for custom queries, absence behavior (`Optional`
   vs throw vs null), ordering, and transaction differences.
4. Compile-only is not an exit. The acceptance pass must include successful
   augmentation (`quarkus:build` / package gate) and any source-derived
   persistence scenarios the cluster owns.
5. `previous_attempts` and any `VERIFICATION_PENDING` record stay in the
   brief: do not repeat a rejected strategy without new evidence.

## EntityManager / Panache

`@Inject EntityManager` is valid for custom JPQL the Spring Data subset
cannot express. Panache is **not** the default on this specimen. Do not
claim "Panache" unless Panache types appear in the diff. Do not add
`quarkus-spring-data-*` beyond what ADR-004 and the catalog already install.

## Agent text

Keep Spring Data repository interfaces. Stay inside the supported subset;
put unsupported methods on a fragment or an explicit JPQL `@Query`. Repair
every applicable method in this repository together. Do not add Panache to
clear `UnableToParseMethodException`. Version is the BOM. After the
diagnostic pass looks no worse, run the acceptance verifier — do not run
extra `mvn compile`/`verify` beside it.

# S04: Repository layer and circular dependency cluster

<!-- The brief is the self-contained work order for one modernization
     story. Bar: a competent developer or a fresh session starts the
     story from THIS FILE ALONE. Fill every section; delete none. -->

## Goal & position

Converts the 54 mutually-dependent repository classes in the circular dependency cluster to @ApplicationScoped CDI beans with constructor injection. This REDESIGN story modernizes all persistence strategies (JDBC, JPA, Spring Data JPA) to native Quarkus CDI while maintaining transactional consistency. As the repository layer, it unblocks the service layer modernization and completes the data access foundation.

## In scope

The exact legacy classes/files this story modernizes. For each, quote
the load-bearing legacy code (the lines being transformed — imports,
annotations, key methods), so the story never starts from a blank
read:

- `src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaOwnerRepositoryImpl.java` — JPA repository
  ```java
  package org.springframework.samples.petclinic.repository.jpa;
  
  import javax.persistence.EntityManager;
  import javax.persistence.PersistenceContext;
  import javax.persistence.Query;
  
  import org.springframework.stereotype.Repository;
  
  @Repository
  @Profile("jpa")
  public class JpaOwnerRepositoryImpl implements OwnerRepository {
      @PersistenceContext
      private EntityManager em;
  ```

- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcOwnerRepositoryImpl.java` — JDBC repository
  ```java
  package org.springframework.samples.petclinic.repository.jdbc;
  
  import org.springframework.beans.factory.annotation.Autowired;
  import org.springframework.jdbc.core.namedparam.BeanPropertySqlParameterSource;
  import org.springframework.stereotype.Repository;
  
  @Repository
  public class JdbcOwnerRepositoryImpl implements OwnerRepository {
      @Autowired
      private JdbcTemplate jdbcTemplate;
  ```

- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepository.java` — Spring Data interface
  ```java
  package org.springframework.samples.petclinic.repository.springdatajpa;
  
  import org.springframework.data.jpa.repository.JpaRepository;
  import org.springframework.data.jpa.repository.Query;
  import org.springframework.samples.petclinic.model.Pet;
  
  public interface SpringDataPetRepository extends JpaRepository<Pet, Integer> {
      @Query("SELECT p FROM Pet p WHERE p.name = :name")
      Collection<Pet> findByName(String name);
  ```

## Out of scope

Service layer implementations, REST controllers, and domain entities remain unchanged. This story only modernizes repository implementations and interfaces to use CDI instead of Spring's @Repository. Service layer integration happens in S05.

## Class roles & target contract (from architecture-profile §7)

All repository classes are REDESIGN - they modernize from Spring DI to Quarkus CDI while preserving data access contracts:

- **Repository implementations** — REDESIGN to @ApplicationScoped CDI with constructor injection
- **Transaction management** — @Transactional method annotations preserved
- **EntityManager injection** — @PersistenceContext → @Inject with proper lifecycle
- **JDBC template** — @Autowired → constructor injection

## Decided target shapes

Replace Spring DI annotations with Quarkus CDI equivalents:

**MAPPINGS transformations:**
- springboot-di-to-quarkus-00003: `@Autowired`, `@Component`, `@Service`, `@Repository` → `@Inject` constructor injection
- springboot-di-to-quarkus-00000: Remove `spring-boot-starter-data-jpa`, use native JPA
- springboot-jpa-to-quarkus-00000: Decide JPA strategy (Panache vs native JPA)
- transaction-to-quarkus-00003: `@Transactional` method annotations on EntityManager operations

## Contracts owned by this story

- **Findings**: springboot-jpa-to-quarkus-00000, springboot-di-to-quarkus-00000, springboot-di-to-quarkus-00003, transaction-to-quarkus-00003
- **seat-budget**: 5 — reimplement work from roadmap `kind × incident count`
- **Preserve**: N/A - no configuration surfaces in this scope
- **Behavioral pins**: All repository methods must maintain their data access contracts exactly
  - findById: returns null when entity not found (legacy behavior)
  - save: persist vs merge based on null ID (isNew() semantics)
  - findByLastName: exact same JPQL/SQL queries and result sets
- **Forbidden**: No behavioral changes to data access methods

## Done-criteria

Checkable, story-scoped:
- All repository classes converted to @ApplicationScoped CDI beans
- Constructor injection replaces @Autowired field injection
- EntityManager injection via @Inject with @PersistenceUnit
- All @Transactional method annotations preserved and functional
- `mvn clean compile` succeeds with CDI annotations
- Repository integration tests pass with new CDI lifecycle
- No Spring @Repository or @Autowired annotations remain

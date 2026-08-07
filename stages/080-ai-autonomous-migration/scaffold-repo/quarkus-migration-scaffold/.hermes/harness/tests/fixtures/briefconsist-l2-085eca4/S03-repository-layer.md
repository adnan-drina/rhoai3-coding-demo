]633;P;HasRichCommandDetection=True# S03: Repository layer

<!-- O-BRIEFFRESH sha256=637c417402bed08a -->
# O-M2COMPOSE brief stub — model fills JUDGMENT quotes / §7 contracts.

## Goal & position

This story modernizes the repository layer that provides data access for the entire application. It converts Spring @Autowired constructor injection to Quarkus CDI @Inject and fixes transaction handling for EntityManager remove operations. The repository layer serves as the bridge between the domain model and persistence storage across three different strategies (JDBC, JPA, Spring Data JPA). This story must complete before services can be safely modernized since services depend on repositories for data access. Owns the OPEN DESIGN findings for transaction management and JDBC configuration that require architecture decisions.

## In scope

The exact legacy classes/files this story modernizes. For each, quote the load-bearing legacy code (the lines being transformed — imports, annotations, key methods), so the story never starts from a blank read:

- **JdbcOwnerRepositoryImpl.java** — JDBC-based repository implementation
  ```java
  @Repository
  @Profile("jdbc")
  public class JdbcOwnerRepositoryImpl implements OwnerRepository {

      private NamedParameterJdbcTemplate namedParameterJdbcTemplate;

      private SimpleJdbcInsert insertOwner;

      @Autowired
      public JdbcOwnerRepositoryImpl(DataSource dataSource) {
          this.insertOwner = new SimpleJdbcInsert(dataSource)
              .withTableName("owners")
              .usingGeneratedKeyColumns("id");
          this.namedParameterJdbcTemplate = new NamedParameterJdbcTemplate(dataSource);
      }
  }
  ```

- **JpaOwnerRepositoryImpl.java** — JPA-based repository implementation
  ```java
  @Repository
  @Profile("jpa")
  public class JpaOwnerRepositoryImpl implements OwnerRepository {

      @PersistenceContext
      private EntityManager em;

      public Collection<Owner> findByLastName(String lastName) {
          Query query = this.em.createQuery("SELECT DISTINCT owner FROM Owner owner left join fetch owner.pets WHERE owner.lastName LIKE :lastName");
          query.setParameter("lastName", lastName + "%");
          return query.getResultList();
      }
  }
  ```

- **SpringDataOwnerRepository.java** — Spring Data JPA repository interface
  ```java
  @Profile("spring-data-jpa")
  public interface SpringDataOwnerRepository extends OwnerRepository, Repository<Owner, Integer> {

      @Override
      @Query("SELECT DISTINCT owner FROM Owner owner left join fetch owner.pets WHERE owner.lastName LIKE :lastName%")
      Collection<Owner> findByLastName(@Param("lastName") String lastName);
  }
  ```

### Scope inventory (O-BRIEFCOVER — do not drop paths)

- `src/main/java/org/springframework/samples/petclinic/repository/OwnerRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/PetRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/PetTypeRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/SpecialtyRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/UserRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/VetRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/VisitRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcOwnerRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPet.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetRowMapper.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetTypeRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetVisitExtractor.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcSpecialtyRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcUserRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVetRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVisitRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVisitRowMapper.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jdbc/package-info.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaOwnerRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetTypeRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaSpecialtyRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaUserRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVetRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVisitRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/jpa/package-info.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/PetRepositoryOverride.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/PetTypeRepositoryOverride.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpecialtyRepositoryOverride.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataOwnerRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetTypeRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetTypeRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataSpecialtyRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataSpecialtyRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataUserRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVetRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVisitRepository.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVisitRepositoryImpl.java`
- `src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/VisitRepositoryOverride.java`

## Out of scope

Service layer classes, REST controllers, and model entities are not modified. Repository interfaces remain unchanged - only implementations are modernized.

## Class roles & target contract (from architecture-profile §7)

All repository implementation classes are **REDESIGN** classes with target runtime contract:

- **JdbcOwnerRepositoryImpl** — REDESIGN: `@ApplicationScoped` with `@Inject` constructor; thread-safe DataSource access
- **JdbcPet** — REDESIGN: JDBC row mapping utility converted to CDI-managed component
- **JdbcPetRepositoryImpl** — REDESIGN: `@ApplicationScoped` with `@Inject` constructor; JDBC template injection
- **JdbcPetRowMapper** — REDESIGN: Row mapping converted to CDI lifecycle management
- **JdbcPetTypeRepositoryImpl** — REDESIGN: Type repository with CDI injection
- **JdbcPetVisitExtractor** — REDESIGN: Visit data extraction with CDI management
- **JdbcSpecialtyRepositoryImpl** — REDESIGN: Specialty repository with CDI injection
- **JdbcUserRepositoryImpl** — REDESIGN: User repository with CDI injection
- **JdbcVetRepositoryImpl** — REDESIGN: Veterinarian repository with CDI injection
- **JdbcVisitRepositoryImpl** — REDESIGN: Visit repository with CDI injection; fix `@Transactional` for remove operations
- **JdbcVisitRowMapper** — REDESIGN: Visit row mapping with CDI management
- **JpaOwnerRepositoryImpl** — REDESIGN: `@PersistenceContext` → `@Inject` EntityManager; add `@Transactional` for remove operations
- **JpaPetRepositoryImpl** — REDESIGN: JPA repository with CDI injection; fix `@Transactional` for remove operations
- **JpaPetTypeRepositoryImpl** — REDESIGN: JPA type repository with CDI injection
- **JpaSpecialtyRepositoryImpl** — REDESIGN: JPA specialty repository with CDI injection
- **JpaUserRepositoryImpl** — REDESIGN: JPA user repository with CDI injection
- **JpaVetRepositoryImpl** — REDESIGN: JPA vet repository with CDI injection
- **JpaVisitRepositoryImpl** — REDESIGN: JPA visit repository with CDI injection; fix `@Transactional` for remove operations
- **PetRepositoryOverride** — REDESIGN: Repository override with CDI management
- **PetTypeRepositoryOverride** — REDESIGN: Type override with CDI management
- **SpecialtyRepositoryOverride** — REDESIGN: Specialty override with CDI management
- **SpringDataOwnerRepository** — REDESIGN: Spring Data interface preserved; configuration updated for Quarkus
- **SpringDataPetRepository** — REDESIGN: Spring Data interface preserved; configuration updated for Quarkus
- **SpringDataPetRepositoryImpl** — REDESIGN: Custom implementation with CDI injection
- **SpringDataPetTypeRepository** — REDESIGN: Spring Data interface preserved; configuration updated for Quarkus
- **SpringDataPetTypeRepositoryImpl** — REDESIGN: Custom type implementation with CDI injection
- **SpringDataSpecialtyRepository** — REDESIGN: Spring Data interface preserved; configuration updated for Quarkus
- **SpringDataSpecialtyRepositoryImpl** — REDESIGN: Custom specialty implementation with CDI injection
- **SpringDataUserRepository** — REDESIGN: Spring Data interface preserved; configuration updated for Quarkus
- **SpringDataVetRepository** — REDESIGN: Spring Data interface preserved; configuration updated for Quarkus
- **SpringDataVisitRepository** — REDESIGN: Spring Data interface preserved; configuration updated for Quarkus
- **SpringDataVisitRepositoryImpl** — REDESIGN: Custom visit implementation with CDI injection; fix `@Transactional` for remove operations
- **VisitRepositoryOverride** — REDESIGN: Visit override with CDI management

## Decided target shapes

Repository modernization follows `.opencode/skills/quarkus-persistence-conventions`:

- **CDI Injection**: `@Autowired` constructor → `@Inject` constructor
- **EntityManager**: `@PersistenceContext` → `@Inject` (OPEN DESIGN finding)
- **Transaction Management**: Add `@Transactional` for remove operations requiring explicit transaction boundaries (OPEN DESIGN finding)
- **Spring Data JPA**: Configure Quarkus compatibility or migrate to Panache
- **JDBC Templates**: DataSource andJdbcTemplate injection via CDI

## Contracts owned by this story

- **seat-budget**: `105`

- **Findings**: springboot-di-to-quarkus-00003, transaction-to-quarkus-00003

- **seat-budget**: `105` — Expected OpenCode seats from roadmap `kind × incident count` (O-SEATBUDGET / ARCH A5). Same integer as roadmap `- seat-budget: N`. Supervisor escalates on overrun.

- **Preserve**: From migration.yaml - database connectivity patterns must be preserved across HSQLDB, MySQL, PostgreSQL

- **Behavioral pins**: All three persistence strategies (JDBC/JPA/Spring Data) must continue to function identically; repository interface contracts preserved; transaction semantics maintained

- **Forbidden**: Never use `quarkus-spring-data-jpa` extension - follows standards path to native Quarkus Panache

## Done-criteria

Checkable, story-scoped:
- All repository implementations use CDI `@Inject` constructor injection (no Spring `@Autowired`)
- EntityManager injection via `@Inject` instead of `@PersistenceContext`
- `@Transactional` annotations properly applied for remove operations across all JPA implementations
- All three persistence strategies (JDBC, JPA, Spring Data JPA) compile and basic CRUD operations function
- Repository tests pass for all persistence strategies
- Transaction boundaries work correctly for complex operations
- No regression in existing repository behavior or performance

### Per-class contracts (O-BRIEFCONTRACT — pasted from §7; do not drop)

- `SpringDataOwnerRepository` — REDESIGN: target: REDESIGN
- `SpringDataPetRepository` — REDESIGN: target: REDESIGN
- `SpringDataPetTypeRepository` — REDESIGN: target: REDESIGN
- `SpringDataSpecialtyRepository` — REDESIGN: target: REDESIGN
- `SpringDataUserRepository` — REDESIGN: target: REDESIGN
- `SpringDataVetRepository` — REDESIGN: target: REDESIGN
- `SpringDataVisitRepository` — REDESIGN: target: REDESIGN

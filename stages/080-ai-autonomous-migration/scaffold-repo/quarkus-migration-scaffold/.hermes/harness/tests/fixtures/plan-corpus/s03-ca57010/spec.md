# S03: Data Access Layer Specification

## Observed Legacy Behavior & API Contract

### Repository Interfaces (Preserved)
The repository layer exposes consistent CRUD interfaces across multiple persistence strategies:

**OwnerRepository Interface** (`src/main/java/org/springframework/samples/petclinic/repository/OwnerRepository.java:34-80`):
- `Collection<Owner> findByLastName(String lastName)` - returns owners whose last name starts with given value
- `Owner findById(int id)` - retrieves single owner by ID, returns null on not found
- `void save(Owner owner)` - inserts or updates owner based on BaseEntity.isNew()
- `Collection<Owner> findAll()` - returns all owners with their pets and visits loaded
- `void delete(Owner owner)` - cascades deletion of associated pets and visits

Similar interface patterns exist for `PetRepository`, `VisitRepository`, `VetRepository`, `SpecialtyRepository`, `PetTypeRepository`, and `UserRepository`.

### JDBC Implementations (Redesign Required)
**JdbcOwnerRepositoryImpl** (`src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcOwnerRepositoryImpl.java:54-71`):
- Uses `@Repository` and `@Profile("jdbc")` annotations
- Field injection via `@Autowired` for `NamedParameterJdbcTemplate` and `SimpleJdbcInsert`
- Constructor accepts `DataSource` but doesn't use constructor injection
- Loads pets and visits eagerly using `loadPetsAndVisits()` helper
- SQL operations: SELECT with LIKE pattern, INSERT with generated keys, UPDATE by ID, DELETE with cascade
- **Key Issue**: Line 62-71 shows mixed injection patterns - field `@Autowired` alongside constructor parameters

**Pattern across all JDBC implementations**:
- 22 incidents of Spring DI annotations (`springboot-di-to-quarkus-00003`)
- `@Autowired` field injection for `NamedParameterJdbcTemplate`
- Constructor with `DataSource` parameter but no `@Autowired` constructor
- Profile-based activation: `@Profile("jdbc")`

### JPA Implementations (Redesign Required)  
**JpaOwnerRepositoryImpl** (`src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaOwnerRepositoryImpl.java:40-45`):
- Uses `@Repository` and `@Profile("jpa")` annotations  
- `@PersistenceContext` for EntityManager injection (line 44)
- JPA queries use JOIN FETCH for eager loading (line 59, 68)
- Save method uses `persist()` for new entities, `merge()` for existing
- **Key Issue**: `@PersistenceContext` needs conversion to `@Inject EntityManager`

**Pattern across all JPA implementations**:
- 21 incidents of Spring DI annotations (`springboot-di-to-quarkus-00003`)
- `@PersistenceContext` EntityManager injection
- Profile-based activation: `@Profile("jpa")`
- JPQL queries with LEFT JOIN FETCH for relationship loading

### Spring Data JPA Implementations (Redesign Required)
**SpringDataOwnerRepository** (`src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataOwnerRepository.java:34-43`):
- Extends both `OwnerRepository` and Spring Data's `Repository<Owner, Integer>`
- Uses `@Query` annotations for custom JPQL (line 38-39, 42-43)
- **Design Decision Needed**: Consolidate to Panache or single JPA approach

## Data Access Patterns & Behavioral Contracts

### CRUD Operations Consistency
- **Find Operations**: All implementations load relationships eagerly (Owner→Pet→Visit)
- **Save Operations**: Insert vs update determined by `BaseEntity.isNew()` check
- **Delete Operations**: Cascading deletes implemented manually in JDBC, automatically via JPA
- **Query Patterns**: LIKE for text search, JOIN FETCH for relationship loading

### Profile-Based Repository Selection
- `application-jdbc.properties` activates `jdbc` profile → uses JDBC implementations
- `application-jpa.properties` activates `jpa` profile → uses JPA implementations  
- `application-spring-data-jpa.properties` activates `spring-data-jpa` profile → uses Spring Data

### Exception Handling
- All repository methods declare `throws DataAccessException`
- JDBC implementation throws `ObjectRetrievalFailureException` on not found
- JPA implementation returns null on not found (no exception)

## Evidence Files
- Repository interfaces: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/*.java`
- JDBC implementations: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jdbc/*.java`
- JPA implementations: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/*.java`
- Spring Data implementations: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/*.java`
- Findings: `springboot-di-to-quarkus-00003` (51 total incidents across repository layer)

## UI Surface Waiver
**Explicitly Waived**: This story (S03: Data Access Layer) has no user-facing UI surface. Repository interfaces and implementations provide data access services but no direct HTTP endpoints. UI surface coverage belongs to story S05 (REST Controllers) which exposes the `/api/*` endpoints.

**Evidence**: Repository layer contains only interfaces and data access implementations without any `@Controller`, `@RestController`, or JAX-RS `@Path` annotations. REST endpoints are defined in `/projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/` which belongs to S05.

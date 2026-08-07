# S03: Data Access Layer Tasks

## UI Surface Waiver
**Explicitly Waived**: This story (S03: Data Access Layer) has no user-facing UI surface. Repository interfaces and implementations provide data access services but no direct HTTP endpoints. UI surface coverage belongs to story S05 (REST Controllers) which exposes the `/api/*` endpoints.

**Evidence**: Repository layer contains only interfaces and data access implementations without any `@Controller`, `@RestController`, or JAX-RS `@Path` annotations. REST endpoints are defined in `/projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/` which belongs to S05.

#### T-001: Create package structure and harvest repository interfaces
**Class**: rewrite
**Shape**: structure
**Findings**: 
**Goal**: Create target package structure and preserve repository interface definitions with unchanged method signatures
**Target design**:
- Create directory structure: src/main/java/com/demo/repository/
- Create directory structure: src/main/java/com/demo/repository/jdbc/
- Create directory structure: src/main/java/com/demo/repository/jpa/
- Create directory structure: src/main/java/com/demo/repository/springdatajpa/
- Add .gitkeep files to ensure empty directories are committable
- src/main/java/org/springframework/samples/petclinic/repository/OwnerRepository.java → src/main/java/com/demo/repository/OwnerRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/PetRepository.java → src/main/java/com/demo/repository/PetRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/VisitRepository.java → src/main/java/com/demo/repository/VisitRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/VetRepository.java → src/main/java/com/demo/repository/VetRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/SpecialtyRepository.java → src/main/java/com/demo/repository/SpecialtyRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/PetTypeRepository.java → src/main/java/com/demo/repository/PetTypeRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/UserRepository.java → src/main/java/com/demo/repository/UserRepository.java
- Package rename: org.springframework.samples.petclinic → com.demo
- Preserve all method signatures: findByLastName, findById, save, delete, findAll
- Exception handling: Remove Spring DataAccessException throws, use jakarta.persistence.PersistenceException or omit throws
**Acceptance**: Package structure created; all repository interfaces compile with new package structure; method signatures preserved

#### T-002: Convert JDBC repository implementations to CDI
**Class**: infer
**Shape**: modify
**Findings**: springboot-di-to-quarkus-00003 (22)
**Goal**: Convert JDBC repository implementations from @Autowired to constructor injection with @ApplicationScoped. O-CHARORACLE: specimen has no legacy repository unit-test oracle — do NOT invent JdbcOwnerRepositoryImplTest / G-PLACE char suites; characterization deferred until real impls exist or later-story ClinicService*Tests.
**Target design**:
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcOwnerRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcPetRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVisitRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcVisitRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVetRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcVetRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcSpecialtyRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcSpecialtyRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetTypeRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcPetTypeRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcUserRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcUserRepositoryImpl.java
- Package rename: org.springframework.samples.petclinic → com.demo
- @Repository → @ApplicationScoped
- @Autowired → constructor injection with @Inject
- Preserve all JDBC SQL operations, parameter mapping, and eager loading behavior
**Acceptance**: All JDBC repository implementations compile with CDI annotations; tests pass; springboot-di-to-quarkus-00003 resolved for JDBC implementations

#### T-003: Convert JPA repository implementations to CDI  
**Class**: infer
**Shape**: modify
**Findings**: springboot-di-to-quarkus-00003 (21)
**Goal**: Convert JPA repository implementations from @PersistenceContext to @Inject EntityManager
**Target design**:
- src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaOwnerRepositoryImpl.java → src/main/java/com/demo/repository/jpa/JpaOwnerRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetRepositoryImpl.java → src/main/java/com/demo/repository/jpa/JpaPetRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVisitRepositoryImpl.java → src/main/java/com/demo/repository/jpa/JpaVisitRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVetRepositoryImpl.java → src/main/java/com/demo/repository/jpa/JpaVetRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaSpecialtyRepositoryImpl.java → src/main/java/com/demo/repository/jpa/JpaSpecialtyRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetTypeRepositoryImpl.java → src/main/java/com/demo/repository/jpa/JpaPetTypeRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaUserRepositoryImpl.java → src/main/java/com/demo/repository/jpa/JpaUserRepositoryImpl.java
- Package rename: org.springframework.samples.petclinic → com.demo
- @Repository → @ApplicationScoped
- @PersistenceContext → @Inject EntityManager
- Preserve JPQL queries with JOIN FETCH and persist/merge logic
**Acceptance**: All JPA repository implementations compile with CDI annotations; JPA queries preserved; tests pass; springboot-di-to-quarkus-00003 resolved for JPA implementations

#### T-004: Consolidate Spring Data repositories
**Class**: infer
**Shape**: structure
**Findings**: springboot-di-to-quarkus-00003 (8)
**Goal**: Consolidate Spring Data repository implementations to Panache repositories
**Target design**:
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataOwnerRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataPetRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVisitRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataVisitRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVetRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataVetRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataSpecialtyRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataSpecialtyRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetTypeRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataPetTypeRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataUserRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataUserRepository.java
- Package rename: org.springframework.samples.petclinic → com.demo
- Convert to Panache repositories extending JpaRepository
- Preserve @Query annotations and query method signatures
- Handle preserve requirements: petclinic.security.enable and server.servlet.context-path documented as out of scope for repository layer
**Acceptance**: Repository consolidation to Panache works; query methods preserved; tests pass; all springboot-di-to-quarkus-00003 violations resolved; preserve items documented

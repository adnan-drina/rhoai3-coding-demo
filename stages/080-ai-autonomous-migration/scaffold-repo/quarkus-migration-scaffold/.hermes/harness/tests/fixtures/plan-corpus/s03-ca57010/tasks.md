# S03: Data Access Layer Tasks

## UI Surface Waiver
**Explicitly Waived**: This story (S03: Data Access Layer) has no user-facing UI surface. Repository interfaces and implementations provide data access services but no direct HTTP endpoints. UI surface coverage belongs to story S05 (REST Controllers) which exposes the `/api/*` endpoints.

**Evidence**: Repository layer contains only interfaces and data access implementations without any `@Controller`, `@RestController`, or JAX-RS `@Path` annotations. REST endpoints are defined in `/projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/` which belongs to S05.

#### T-001: Create package structure and harvest repository interfaces
**Class**: rewrite
**Shape**: create
**Findings**: 
**Goal**: Create target package directories and harvest repository interface definitions with unchanged method signatures (O-STRUCTJAVA: Shape=create for .java Targets; .gitkeep alone is not the deliverable)
**Target design**:
- Ensure package dirs exist (gitkeep ok as scaffolding only): src/main/java/com/demo/repository/{,.jdbc/,.jpa/,.springdatajpa/}
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
**Goal**: Convert JDBC repository implementations and same-package JDBC helpers (JdbcPet + row mappers/extractors) from Spring JDBC/@Autowired to Agroal DataSource + constructor @Inject/@ApplicationScoped. O-COLLABOWN peers included in Target. O-CHARORACLE: specimen has no legacy repository unit-test oracle — do NOT invent JdbcOwnerRepositoryImplTest / G-PLACE char suites; characterization deferred until real impls exist or later-story ClinicService*Tests.
**Target design**:
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcOwnerRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcPetRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVisitRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcVisitRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVetRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcVetRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcSpecialtyRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcSpecialtyRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetTypeRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcPetTypeRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcUserRepositoryImpl.java → src/main/java/com/demo/repository/jdbc/JdbcUserRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPet.java → src/main/java/com/demo/repository/jdbc/JdbcPet.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetRowMapper.java → src/main/java/com/demo/repository/jdbc/JdbcPetRowMapper.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetVisitExtractor.java → src/main/java/com/demo/repository/jdbc/JdbcPetVisitExtractor.java
- src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVisitRowMapper.java → src/main/java/com/demo/repository/jdbc/JdbcVisitRowMapper.java
**Absorbs**: same-package JDBC helpers required for T-002 compile (O-COLLABOWN): JdbcPet, JdbcPetRowMapper, JdbcPetVisitExtractor, JdbcVisitRowMapper — convert with Agroal DataSource / java.sql alongside repository impls; do not stub-nuke (O-TREEFIXSTUB)
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

#### T-004: Consolidate Spring Data repositories to Panache
**Class**: infer
**Shape**: create
**Findings**: springboot-di-to-quarkus-00003 (8)
**Goal**: Convert/implement Spring Data JPA repositories as Quarkus Panache repositories (O-SDJPAHARVEST) — not package-structure. Keep domain-repo contracts, rewrite @Query to Panache find/list bodies, harvest Override *Impl delete bodies.
**Target design**:
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataOwnerRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataOwnerRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataPetRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVisitRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataVisitRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVetRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataVetRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataSpecialtyRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataSpecialtyRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetTypeRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataPetTypeRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataUserRepository.java → src/main/java/com/demo/repository/springdatajpa/SpringDataUserRepository.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepositoryImpl.java → src/main/java/com/demo/repository/springdatajpa/SpringDataPetRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetTypeRepositoryImpl.java → src/main/java/com/demo/repository/springdatajpa/SpringDataPetTypeRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataSpecialtyRepositoryImpl.java → src/main/java/com/demo/repository/springdatajpa/SpringDataSpecialtyRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVisitRepositoryImpl.java → src/main/java/com/demo/repository/springdatajpa/SpringDataVisitRepositoryImpl.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/PetRepositoryOverride.java → src/main/java/com/demo/repository/springdatajpa/PetRepositoryOverride.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/PetTypeRepositoryOverride.java → src/main/java/com/demo/repository/springdatajpa/PetTypeRepositoryOverride.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpecialtyRepositoryOverride.java → src/main/java/com/demo/repository/springdatajpa/SpecialtyRepositoryOverride.java
- src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/VisitRepositoryOverride.java → src/main/java/com/demo/repository/springdatajpa/VisitRepositoryOverride.java
**Owns**: all Target springdatajpa paths above
**Absorbs**: Override interfaces + SpringData*RepositoryImpl delete bodies required for consolidate (O-SDJPAHARVEST / O-COLLABOWN)
- Package rename: org.springframework.samples.petclinic → com.demo
- Convert Spring Data Repository/@Query → PanacheRepository or PanacheRepositoryBase plus keep staging domain-repo extends/implements (OwnerRepository/PetRepository/…)
- Rewrite staging method @Query JPQL to Panache find/list default or class methods — NEVER orphan @NamedQuery on the repository interface; no hollow finder declarations
- Harvest Override *RepositoryImpl with EntityManager/@Inject (CDI) delete bodies — iface-only empty Panache shells ≠ consolidate
- Add quarkus-hibernate-orm-panache if missing
- Preserve items petclinic.security.enable and server.servlet.context-path remain out of scope for repository layer
**Acceptance**: All SpringData* repos compile as Panache with domain-repo contracts; staging @Query methods have Panache bodies; Override Impls present; O-SDJPAHARVEST sensor GREEN; tests pass; springboot-di-to-quarkus-00003 resolved for springdatajpa; no org.springframework residue under springdatajpa

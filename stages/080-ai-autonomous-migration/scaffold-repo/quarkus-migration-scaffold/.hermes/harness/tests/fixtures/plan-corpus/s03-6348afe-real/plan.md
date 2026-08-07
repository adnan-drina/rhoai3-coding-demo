# S03: Data Access Layer Plan

## Quarkus Mapping Strategy

### Package Rename (Rewrite)
**Legacy package**: `org.springframework.samples.petclinic` → **Target package**: `com.demo`
- Repository interfaces: `org.springframework.samples.petclinic.repository.*` → `com.demo.repository.*`
- JDBC implementations: `org.springframework.samples.petclinic.repository.jdbc.*` → `com.demo.repository.jdbc.*`
- JPA implementations: `org.springframework.samples.petclinic.repository.jpa.*` → `com.demo.repository.jpa.*`
- Spring Data implementations: `org.springframework/samples/petclinic/repository/springdatajpa.*` → `com.demo.repository.springdatajpa.*`

### CDI Conversion (Infer Tasks)
Per MAPPINGS.md CDI conversion rules:

**JDBC Repositories** (springboot-di-to-quarkus-00003 - 22 incidents):
- `@Repository` → `@ApplicationScoped` 
- `@Autowired` field injection → constructor injection with `@Inject`
- Constructor accepts `DataSource` → convert to `@Inject` constructor
- Preserve all JDBC SQL operations and parameter mapping
- Preserve eager loading behavior via `loadPetsAndVisits()` helpers

**JPA Repositories** (springboot-di-to-quarkus-00003 - 21 incidents):
- `@Repository` → `@ApplicationScoped`
- `@PersistenceContext` → `@Inject EntityManager` 
- Preserve JPQL queries with JOIN FETCH
- Preserve `persist()`/`merge()` save logic
- Maintain profile-based selection (`@Profile("jpa")`)

**Spring Data Repositories** (springboot-di-to-quarkus-00003 - 8 incidents):
- **Design Decision**: Consolidate to single approach
  - Option A: Panache repositories (recommended for standards path)
  - Option B: Native JPA with CDI (if Spring Data patterns needed)
- Preserve query method signatures and `@Query` annotations

### Interface Preservation (Rewrite)
All repository interfaces remain unchanged:
- `OwnerRepository`, `PetRepository`, `VisitRepository`, `VetRepository`, `SpecialtyRepository`, `PetTypeRepository`, `UserRepository`
- Method signatures: `findByLastName`, `findById`, `save`, `delete`, `findAll`
- Exception handling: `throws DataAccessException`
- Spring Data naming conventions preserved

### Test Strategy (Infer)
**Repository Characterization Tests**:
- Port legacy repository tests from `src/test/java/org/springframework/samples/petclinic/repository/*`
- Test all three persistence strategies produce identical results
- Verify `findByLastName` returns sorted results by lastName
- Test CRUD operations: create, read, update, delete
- Verify EntityManager lifecycle and JDBC DataSource injection
- Test cascade delete behavior (Owner→Pet→Visit)

### Quality Gates
- All repository implementations compile with CDI annotations
- No `@Autowired`, `@Repository`, `@PersistenceContext` remaining (springboot-di-to-quarkus-00003 resolved)
- Repository interface method contracts preserved
- Profile-based repository selection maintained
- Multiple persistence strategies verified via tests

### Story Dependencies
- **Prerequisites**: S02 (domain models) - entities must be migrated to jakarta.persistence first
- **Dependents**: S04 (service layer), S05 (REST controllers) - repository interfaces unchanged but implementations modernized
- **No conflicts**: Repository layer modernization doesn't affect service/controller contracts

## Task Classification Summary

**Rewrite Tasks** (mechanical transforms):
- Package rename for all repository files
- Interface preservation (no changes needed)

**Infer Tasks** (judgment/design decisions):
- JDBC repository CDI conversion with constructor injection
- JPA repository @PersistenceContext → @Inject conversion
- Spring Data consolidation decision and implementation
- Repository characterization test porting

**Verify Tasks**:
- springboot-di-to-quarkus-00003 finding resolution confirmation
- Multi-strategy consistency verification

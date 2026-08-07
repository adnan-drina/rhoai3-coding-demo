# M1 Architecture Profile — Spring PetClinic REST

## 1. Purpose & domain

The Spring PetClinic REST application provides a comprehensive veterinary clinic management system that enables the management of **owners**, **pets**, **veterinarians**, **visits**, **specialties**, and **pet types** through a REST API (OwnerRestController.java:41). The application serves veterinary clinic staff who need to maintain owner records, track pets and their medical history, schedule and manage visits, and manage veterinarian information and their specializations.

The core domain model centers on the **Owner** entity (business customer) who owns **Pets** (animals under care) (Owner.java:52-53). **Visits** represent medical appointments for pets with **Veterinarians** who have **Specialties** (areas of expertise). **PetTypes** classify different animal categories. The system supports CRUD operations for all entities with role-based access control, primarily targeting clinic administrators with OWNER_ADMIN privileges (OwnerRestController.java:52).

The behavioral contract is defined by extensive integration tests in `AbstractClinicServiceTests` (src/test/java/org/springframework/samples/petclinic/service/clinicService/AbstractClinicServiceTests.java:57-474) which validate:
- Owner search by last name returns exactly 2 "Davis" records (AbstractClinicServiceTests.java:58-59)
- Owner #1 has exactly 1 pet named with type "cat" (AbstractClinicServiceTests.java:67-71)  
- Pet #7 named "Samantha" belongs to owner "Jean" (AbstractClinicServiceTests.java:109-113)
- CRUD operations maintain referential integrity across owner-pet relationships (AbstractClinicServiceTests.java:128-146)

## 2. Components & relationships

The application follows a layered architecture with clear separation of concerns (PetClinicApplication.java:7):

```
┌─────────────────────────────────────────────────────────────┐
│ REST Controllers (8 endpoints)                              │
│ • OwnerRestController • PetRestController • VisitRest...   │
└─────────────────┬───────────────────────────────────────────┘
                  │ depends on
┌─────────────────▼───────────────────────────────────────────┐
│ Service Layer (2 services)                                  │
│ • ClinicService (facade for all domain operations)          │
│ • UserService (authentication/authorization)                │
└─────────────────┬───────────────────────────────────────────┘
                  │ orchestrates
┌─────────────────▼───────────────────────────────────────────┐
│ Repository Layer (3 persistence strategies)                 │
│ • JDBC implementations (Jdbc*RepositoryImpl)               │
│ • JPA implementations (Jpa*RepositoryImpl)                 │
│ • Spring Data JPA (SpringData*Repository)                  │
└─────────────────┬───────────────────────────────────────────┘
                  │ persists
┌─────────────────▼───────────────────────────────────────────┐
│ Model Layer (11 entities + DTOs + Mappers)                 │
│ • Domain entities (Owner, Pet, Visit, etc.)                │
│ • DTOs (OwnerDto, PetDto, VisitDto)                       │
│ • MapStruct mappers (OwnerMapper, PetMapper, etc.)        │
└─────────────────────────────────────────────────────────────┘
```

**God nodes** (highest fan-in per dependency-order.md:8-14):
- **PetType**: referenced by 18 classes (dependency-order.md:8) including src/main/java/org/springframework/samples/petclinic/model/Visit.java:41-50, src/main/java/org/springframework/samples/petclinic/model/Pet.java:41-50, and their mappers/repositories
- **Visit**: referenced by 18 classes (dependency-order.md:9) including src/main/java/org/springframework/samples/petclinic/model/Pet.java:49-50, src/main/java/org/springframework/samples/petclinic/model/Visit.java (entire file), repositories and mappers
- **Pet**: referenced by 17 classes (dependency-order.md:10) including src/main/java/org/springframework/samples/petclinic/model/Owner.java:52-53, src/main/java/org/springframework/samples/petclinic/model/Pet.java:34-100, repositories, mappers
- **Specialty**: referenced by 13 classes (dependency-order.md:11) including src/main/java/org/springframework/samples/petclinic/model/Vet.java (entire file), repositories, mappers
- **Owner**: referenced by 11 classes (dependency-order.md:12) including src/main/java/org/springframework/samples/petclinic/model/Owner.java:36-149, src/main/java/org/springframework/samples/petclinic/model/Pet.java:45-47, repositories, mappers

These god nodes represent the core domain concepts that any modernization must preserve carefully, as changes cascade through multiple layers. PetType and Visit form the critical path for any schema or API modifications.

**Circular dependency group** (dependency-order.md:42-104): 54 classes in a mutually-dependent cluster covering the entire domain model, mappers, repositories, and services. This monolithic coupling requires coordinated conversion in a single task to avoid compilation breaks.

## 3. Integration surfaces

**REST API endpoints** (src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:41, src/main/java/org/springframework/samples/petclinic/rest/PetRestController.java:42):
- Base path: `/api/owners`, `/api/pets`, `/api/vets`, `/api/visits`, `/api/specialties`, `/api/pettypes`, `/api/users`
- Operations: GET collection, GET by ID, POST create, PUT update, DELETE by ID
- Security: `@PreAuthorize("hasRole(@roles.OWNER_ADMIN)")` on all operations (src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:52, 65, 75, 86, 104)
- Content-Type: `application/json` with DTO-based payloads via MapStruct mappers (src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:62, 72)

**Database persistence** (src/main/resources/application-hsqldb.properties:7-9, src/main/resources/application-mysql.properties:8-11, src/main/resources/application-postgresql.properties:8-11):
- Multiple profile-based configurations (hsqldb, mysql, postgresql) via Spring profiles
- Three persistence strategies: JDBC (src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcOwnerRepositoryImpl.java:54), JPA (src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaOwnerRepositoryImpl.java:40), and Spring Data JPA (src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepositoryImpl.java:19)
- Schema: owners, pets, visits, vets, specialties, pet_types, roles, users tables
- Transaction management via Spring's `@Transactional` (src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:131, findings-inventory.md:170-172)

**Security integration** (src/main/java/org/springframework/samples/petclinic/security/BasicAuthenticationConfig.java:17, 22, 40):
- Spring Security with HTTP Basic Authentication
- Role-based access control via `Roles` component (src/main/java/org/springframework/samples/petclinic/security/Roles.java:5)
- Configurable security enable/disable via `DisableSecurityConfig` (src/main/java/org/springframework/samples/petclinic/security/DisableSecurityConfig.java:12)

**Monitoring** (src/main/java/org/springframework/samples/petclinic/util/CallMonitoringAspect.java:37, 47, 52, 57, 63, 68):
- JMX-based call monitoring via Spring AOP
- Metrics collection on service method invocations
- Actuator integration for health/metrics endpoints (pom.xml:40)

## 4. Behavioral contract sources

The **primary behavioral contract** lives in the test suite:

**Service layer contract** (src/test/java/org/springframework/samples/petclinic/service/clinicService/AbstractClinicServiceTests.java:56-474):
- `shouldFindOwnersByLastName()`: "Davis" returns exactly 2 results (src/test/java/org/springframework/samples/petclinic/service/clinicService/AbstractClinicServiceTests.java:58-59)
- `shouldFindSingleOwnerWithPet()`: Owner #1 has last name "Franklin", 1 pet, pet type "cat" (src/test/java/org/springframework/samples/petclinic/service/clinicService/AbstractClinicServiceTests.java:67-71)
- `shouldInsertOwner()`: New owner gets auto-generated ID, becomes findable by last name (src/test/java/org/springframework/samples/petclinic/service/clinicService/AbstractClinicServiceTests.java:76-90)
- `shouldUpdateOwner()`: Owner last name modification persists (src/test/java/org/springframework/samples/petclinic/service/clinicService/AbstractClinicServiceTests.java:94-105)
- `shouldFindPetWithCorrectId()`: Pet #7 named "Samantha" belongs to "Jean" (src/test/java/org/springframework/samples/petclinic/service/clinicService/AbstractClinicServiceTests.java:109-113)
- `shouldInsertPetIntoDatabaseAndGenerateId()`: Pet creation increments owner's pet count, generates ID (src/test/java/org/springframework/samples/petclinic/service/clinicService/AbstractClinicServiceTests.java:128-146)

**Behavioral contract** (src/test/java/org/springframework/samples/petclinic/rest/OwnerRestControllerTests.java:75-341):
- GET `/api/owners/{id}` returns 404 for non-existent owners (src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:77-83)
- POST `/api/owners` validates business rules, returns 400 for validation errors (src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:88-101)
- PUT `/api/owners/{id}` validates ID consistency, returns 400 for mismatched IDs (src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:105-126)
- DELETE `/api/owners/{id}` returns 404 for non-existent owners, 204 on success (src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:131-138)

**Contract gaps**: 
- Error response formats are not comprehensively specified beyond HTTP status codes
- Input validation rules (@NotEmpty, @Digits constraints) are not documented in API contracts
- No specification of concurrent modification handling or optimistic locking
- Edge cases for cascade delete operations are not tested

## 5. Modernization surface

**Mandatory changes** (findings-inventory.md:319-335):

**Jakarta EE migration** (javax-to-jakarta-import-00001):
- 56 files require javax→jakarta package migration across entities, repositories, REST controllers, and generated mappers (findings-inventory.md:9-61)

**Spring-to-Quarkus conversion**:
- POM transformation: Spring Boot parent → Quarkus BOM, spring-boot-starter → quarkus extensions (springboot-parent-pom-to-quarkus-00000)
- REST migration: Spring `@RestController` → JAX-RS `@Path` with native CDI (springboot-web-to-quarkus-00000)
- DI migration: Spring `@Service`/`@Component` → Quarkus CDI `@ApplicationScoped` (springboot-di-to-quarkus-00003)
- Properties migration: Spring Boot properties → Quarkus configuration (springboot-properties-to-quarkus-00002, 00003)
- Actuator replacement: Spring Boot Actuator → Quarkus SmallRye Health (`/q/health`) (springboot-actuator-to-quarkus-0100)

**Optional changes**:
- Cache abstraction: Spring Cache → Quarkus cache extension (springboot-cache-to-quarkus-00000)
- JPA strategy: Spring Data JPA vs Quarkus Panache migration (springboot-jpa-to-quarkus-00000)
- Security: Spring Security → Quarkus security configuration (springboot-security-to-quarkus-00000)

**Platform contract rules**:
- Configuration: environment-driven config in `application.properties` (preserve: datasource URLs)
- State management: in-memory collection caching requires thread-safe replacement
- Validation: Bean Validation constraints (@NotEmpty, @Digits) must persist

## 6. Domain boundaries

**Cohesive bounded context**: The application functions as a single bounded context covering the complete veterinary clinic operational domain (src/main/java/org/springframework/samples/petclinic/service/ClinicService.java:35-70, dependency-order.md:42-104). All entities (Owner, Pet, Visit, Vet, Specialty, PetType) are tightly coupled through:

- **Referential integrity**: Owner→Pets→Visits→Vets relationships (src/main/java/org/springframework/samples/petclinic/model/Owner.java:52-53, src/main/java/org/springframework/samples/petclinic/model/Pet.java:41-50)
- **Shared DTO/mapper layer**: Uniform transformation patterns across all entities (src/main/java/org/springframework/samples/petclinic/mapper/OwnerMapper.java, src/main/java/org/springframework/samples/petclinic/mapper/PetMapper.java)
- **Unified service facade**: ClinicService orchestrates all domain operations (src/main/java/org/springframework/samples/petclinic/service/ClinicService.java:35-70)
- **Circular dependency cluster**: 54 mutually-dependent classes (dependency-order.md:42-104)

**Circular dependency justification** (src/main/java/org/springframework/samples/petclinic/model/Owner.java:52-53, src/main/java/org/springframework/samples/petclinic/model/Pet.java:41-50, src/main/java/org/springframework/samples/petclinic/model/Visit.java:entire file):
- Owner-Pet-Visit triad requires transactional consistency for medical records (src/main/java/org/springframework/samples/petclinic/model/Owner.java:52-53, src/main/java/org/springframework/samples/petclinic/model/Pet.java:49-50)
- Veterinarian scheduling depends on pet type specializations (src/main/java/org/springframework/samples/petclinic/model/Vet.java:entire file, src/main/java/org/springframework/samples/petclinic/model/Specialty.java:entire file)
- All operations enforce uniform security and validation policies (src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:52)

This coupling indicates modernization should proceed as a **single story** to maintain transactional integrity and avoid breaking the circular dependency cluster during incremental migration.

## 7. Class roles & target contract

### HARVEST — data/DTO/value-object classes (preserve faithfully)

**Domain entities** (jakarta.persistence + validation constraints):
- `BaseEntity` — abstract ID carrier with `isNew()` semantics (src/main/java/org/springframework/samples/petclinic/model/BaseEntity.java:31-48)
- `NamedEntity` — name field abstraction (src/main/java/org/springframework/samples/petclinic/model/NamedEntity.java)
- `Person` — firstName/lastName fields (src/main/java/org/springframework/samples/petclinic/model/Person.java)
- `Owner` — address, city, telephone, pets collection (src/main/java/org/springframework/samples/petclinic/model/Owner.java:36-149)
- `Pet` — birthDate, type, owner, visits (src/main/java/org/springframework/samples/petclinic/model/Pet.java:34-100)
- `Visit` — date, description, pet, vet (src/main/java/org/springframework/samples/petclinic/model/Visit.java)
- `PetType` — name classification (src/main/java/org/springframework/samples/petclinic/model/PetType.java)
- `Specialty` — vet expertise area (src/main/java/org/springframework/samples/petclinic/model/Specialty.java)
- `Vet` — firstName/lastName, specialties (src/main/java/org/springframework/samples/petclinic/model/Vet.java)
- `Role` — security role definition (src/main/java/org/springframework/samples/petclinic/model/Role.java)
- `User` — authentication credentials (src/main/java/org/springframework/samples/petclinic/model/User.java)

**DTOs** (OpenAPI-generated):
- `OwnerDto`, `PetDto`, `VisitDto`, `PetTypeDto`, `SpecialtyDto`, `VetDto`, `RoleDto`, `UserDto`
- Generated from OpenAPI spec, map 1:1 to domain with validation annotations

**Pure utilities**:
- `EntityUtils` — collection manipulation helpers (dependency-order.md:34)
- `BindingErrorsResponse` — validation error formatting

### REDESIGN — service/endpoint/config classes (modernize runtime behavior)

**Services** (src/main/java/org/springframework/samples/petclinic/service/ClinicService.java:35-70):
- `ClinicService` — **removed** — facade subsumed by individual resource endpoints
- `ClinicServiceImpl` → **@ApplicationScoped** CDI bean with constructor injection (findings-inventory.md:86)
- `UserService` — **removed** — authentication subsumed by Quarkus Security
- `UserServiceImpl` → **@ApplicationScoped** CDI bean (findings-inventory.md:87)

**REST endpoints** (src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:39-141):
- `OwnerRestController` → **@Path("/api/owners")** JAX-RS resource with **400 (problem-detail)** for validation errors, **404** for missing resources, **503** via **ExceptionMapper** for downstream failures
- `PetRestController` → **@Path("api/pets")** JAX-RS resource with same error handling contract
- `VisitRestController`, `VetRestController`, `SpecialtyRestController`, `PetTypeRestController`, `UserRestController` → JAX-RS migration with uniform error mapping
- `RootRestController` → **@Path("/api")** root resource

**Configuration**:
- `PetClinicApplication` → **removed** — main class subsumed by Quarkus bootstrap (findings-inventory.md:244)
- `ApplicationSwaggerConfig` → **removed** — Swagger integration subsumed by Quarkus OpenAPI
- `BasicAuthenticationConfig` → **removed** — security subsumed by Quarkus Security
- `DisableSecurityConfig` → **removed** — conditional security via Quarkus profile configuration
- `Roles` → **removed** — role definitions via Quarkus Security config

**Repository implementations** (findings-inventory.md:68-95):
- All `JdbcOwnerRepositoryImpl`, `JdbcPetRepositoryImpl`, `JdbcPetTypeRepositoryImpl`, `JdbcSpecialtyRepositoryImpl`, `JdbcUserRepositoryImpl`, `JdbcVetRepositoryImpl`, `JdbcVisitRepositoryImpl` → **@ApplicationScoped** CDI beans with **constructor injection** and **@Transactional** method annotations
- All `JpaOwnerRepositoryImpl`, `JpaPetRepositoryImpl`, `JpaPetTypeRepositoryImpl`, `JpaSpecialtyRepositoryImpl`, `JpaUserRepositoryImpl`, `JpaVetRepositoryImpl`, `JpaVisitRepositoryImpl` → **@ApplicationScoped** CDI beans with **constructor injection** and **@Transactional** method annotations
- All `SpringDataOwnerRepository`, `SpringDataPetRepository`, `SpringDataPetTypeRepository`, `SpringDataSpecialtyRepository`, `SpringDataUserRepository`, `SpringDataVetRepository`, `SpringDataVisitRepository` → **@ApplicationScoped** CDI beans with **constructor injection**
- `PetRepositoryOverride`, `PetTypeRepositoryOverride`, `SpecialtyRepositoryOverride`, `VisitRepositoryOverride` → **@ApplicationScoped** CDI beans

**Mappers** (OpenAPI-generated MapStruct implementations):
- `OwnerMapperImpl`, `PetMapperImpl`, `PetTypeMapperImpl`, `SpecialtyMapperImpl`, `UserMapperImpl`, `VetMapperImpl`, `VisitMapperImpl` → **@Generated MapStruct implementations** - **removed** - subsumed by static mapping methods in Quarkus

**Aspects**:
- `CallMonitoringAspect` → **removed** - observability subsumed by Micrometer/MicroProfile Metrics

**Target runtime contracts** (platform idioms from MAPPINGS + migration.yaml targetContract):

**API contract (behavior-changing)** (migration.yaml:18-24):
- GET operations never mutate state — **404** on missing resources (migration.yaml:getIdempotent=true)
- POST/PUT operations validate inputs — **400** with problem-detail JSON for @NotEmpty/@Digits violations (migration.yaml:validateInput=true)
- Repository failures propagate as **503** via JAX-RS **ExceptionMapper** (migration.yaml:mapErrors=true)
- DELETE operations return **404** for missing resources, **204** on success

**Concurrency**: 
- Service layer maintains shared mutable state in collections — **no thread-safety required** (migration.yaml:threadSafeState=false)
- Repository layer delegates to container-managed transactions

**Resource management**:
- Repository beans hold no external resource caches — container-managed lifecycle
- Service layer maintains no in-memory state beyond transaction scope
- **Cache refresh policy** — **no clear-on-miss refresh guard** (migration.yaml:cacheRefreshGuard=true) — bounded refresh required

Every REST controller annotated with `@RestController` (OwnerRestController.java:39, PetRestController.java:40, etc.) is classified **REDESIGN** — the rubric cross-checks this mechanically against Jakarta EE annotations.
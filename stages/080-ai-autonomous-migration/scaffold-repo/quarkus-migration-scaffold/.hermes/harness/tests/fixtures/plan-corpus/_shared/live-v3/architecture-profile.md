# M1 architecture profile: Spring PetClinic

## 1. Purpose & domain

The Spring PetClinic application is a demonstration veterinary clinic management system that enables staff to manage pet owners, their pets, veterinary visits, and the clinic's veterinary staff. The application provides CRUD operations for all core entities: Owners (pet owners), Pets (companion animals), Visits (appointments/examinations), Vets (veterinarians), and supporting entities (Specialty, PetType, User, Role).

The domain centers on a veterinary practice's operational data model: Owners possess multiple Pets; Pets receive Visits; Vets perform Visits; and the clinic maintains a catalog of PetTypes and Specialties. The application demonstrates enterprise patterns: layered architecture, multiple persistence strategies (JDBC, JPA, Spring Data JPA), RESTful APIs, and Spring framework conventions. It serves as a canonical example for Spring Boot migration demonstrations, showing realistic business logic, validation, error handling, and data relationships.

**Evidence**: `ClinicService` interface defines the core business operations (`src/main/java/org/springframework/samples/petclinic/service/ClinicService.java:35-71`), `PetClinicApplication` provides bootstrap (`src/main/java/org/springframework/samples/petclinic/PetClinicApplication.java:10-11`), entity relationships established in JPA annotations (`src/main/java/org/springframework/samples/petclinic/model/Pet.java:41-50`, `src/main/java/org/springframework/samples/petclinic/model/Owner.java:52-53`), service facade pattern implementation (`src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java:47`).

## 2. Components & relationships

The application follows a classic layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│  REST Controllers (OwnerRestController, PetRestController,  │
│  VetRestController, VisitRestController, etc.)             │
│  → Expose /api/* endpoints, validate input, map DTOs        │
└─────────────────────┬───────────────────────────────────────┘
                      │ inject
┌─────────────────────▼───────────────────────────────────────┐
│  Services (ClinicService, ClinicServiceImpl, UserService)  │
│  → Business logic facade, transaction boundaries, caching  │
└─────────────────────┬───────────────────────────────────────┘
                      │ inject
┌─────────────────────▼───────────────────────────────────────┐
│  Repositories (OwnerRepository, PetRepository, etc.)       │
│  → Data access abstraction, multiple implementations       │
│  - JDBC (JdbcOwnerRepositoryImpl, etc.)                    │
│  - JPA (JpaOwnerRepositoryImpl, etc.)                      │
│  - Spring Data (SpringDataOwnerRepository, etc.)           │
└─────────────────────┬───────────────────────────────────────┘
                      │ serialize/deserialize
┌─────────────────────▼───────────────────────────────────────┐
│  Models (Owner, Pet, Visit, Vet, Specialty, PetType)       │
│  → JPA entities with validation, toString, business logic  │
└─────────────────────┬───────────────────────────────────────┘
                      │ DTO mapping
┌─────────────────────▼───────────────────────────────────────┐
│  DTOs & Mappers (OwnerDto, OwnerMapper, etc.)              │
│  → API contracts, object mapping, validation               │
└─────────────────────────────────────────────────────────────┘
```

Supporting infrastructure: Security configuration (`BasicAuthenticationConfig`, `DisableSecurityConfig`) controls API access; Swagger configuration (`ApplicationSwaggerConfig`) generates API documentation; Exception handling (`ExceptionControllerAdvice`, `BindingErrorsResponse`) centralizes error responses.

**God nodes** (high fan-in from `migration/dependency-order.md:8-14`): `PetType` (fan-in 18), `Visit` (fan-in 18), `Pet` (fan-in 17) — these entities form the core data relationships and will require careful characterization testing during modernization.

**Evidence**: Dependency analysis shows 84 classes with 191 intra-project edges (`migration/dependency-order.md:3`), Controllers inject Services (`src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:44-50`), Services inject Repositories (`src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java:58-72`), circular dependency group includes all entity/repository/mapper classes (`migration/dependency-order.md:42-105`).

## 3. Integration surfaces

**External APIs exposed:**
- REST endpoints under `/api/owners`, `/api/pets`, `/api/vets`, `/api/visits`, `/api/petTypes`, `/api/specialties`, `/api/users` (`src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:41`, `src/main/java/org/springframework/samples/petclinic/rest/PetRestController.java`, `src/main/java/org/springframework/samples/petclinic/rest/VetRestController.java`, etc.)
- HTTP methods: GET (collection, by-id, by-search), POST (create), PUT (update), DELETE (remove)
- Media type: `application/json`
- Security: PreAuthorize annotations requiring OWNER_ADMIN role (`src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:52, 65, 75, 86, 104, 129`)
- Response codes: 200 OK, 201 CREATED, 204 NO_CONTENT, 404 NOT_FOUND, 400 BAD_REQUEST

**Persistence:**
- Database: Supports HSQLDB, MySQL, PostgreSQL (`src/main/resources/application-hsqldb.properties`, `src/main/resources/application-mysql.properties`, `src/main/resources/application-postgresql.properties`)
- JDBC configuration via `spring.datasource.*` properties (`src/main/resources/application-mysql.properties:8-11`, `src/main/resources/application-postgresql.properties:8-11`)
- Hibernate JPA implementation with connection pooling

**Configuration & observability:**
- Spring Boot Actuator → health, metrics endpoints (`pom.xml:40`)
- Micrometer metrics integration (`src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java:264`)
- Swagger/OpenAPI 3 documentation (`src/main/java/org/springframework/samples/petclinic/util/ApplicationSwaggerConfig.java` throughout)

**Security:**
- Spring Security with Basic Authentication (`src/main/java/org/springframework/samples/petclinic/security/BasicAuthenticationConfig.java:17, 22, 40`)
- Role-based access control with Roles enum (`src/main/java/org/springframework/samples/petclinic/security/Roles.java:5`)
- Option to disable security for development (`src/main/java/org/springframework/samples/petclinic/security/DisableSecurityConfig.java:12`)

**Preserve candidates** (from `migration/findings-inventory.md:337-343`):
- Database connection properties (`springboot-properties-to-quarkus-00002`)
- Health endpoints via `quarkus-smallrye-health` (`springboot-actuator-to-quarkus-0100`)
- Log level configuration (`springboot-properties-to-quarkus-00003`)
- Property file consolidation (`springboot-properties-to-quarkus-00001`)

**Evidence**: REST controller mappings throughout, datasource properties in three profile files (`src/main/resources/application-mysql.properties:8-11`), security config classes, actuator dependency (`pom.xml:40`), findings inventory (`migration/findings-inventory.md:5-318`).

## 4. Behavioral contract sources

The behavioral contract is comprehensively test-driven across three testing layers:

**Service layer contracts** (`src/test/java/org/springframework/samples/petclinic/service/clinicService/AbstractClinicServiceTests.java`):
- CRUD operations for all entities: `savePet()`, `deletePet()`, `findPetById()`, `findAllPets()` (`src/test/java/org/springframework/samples/petclinic/service/clinicService/ClinicServiceSpringDataJpaTests.java:28-45, 65-82`)
- Query operations: `findOwnerByLastName()`, `findVisitsByPetId()`, `findVets()` with caching verification (`src/test/java/org/springframework/samples/petclinic/service/clinicService/ClinicServiceSpringDataJpaTests.java:103-120, 130-147`)
- Transactional behavior: read-only queries for finders, write transactions for saves (`src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java:75, 131, 224`)
- Null handling: returns null on not-found rather than throwing exceptions (`src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java:88-96, 113-121, 155-164`)
- **Expected thresholds**: visit dates sortable via `PropertyComparator.sort()` (`src/main/java/org/springframework/samples/petclinic/model/Pet.java:89`), owner search case-insensitive (`src/main/java/org/springframework/samples/petclinic/model/Owner.java:123-128`)

**REST layer contracts** (`src/test/java/org/springframework/samples/petclinic/rest/OwnerRestControllerTests.java`):
- GET `/api/owners` returns 200 OK with collection, 404 NOT_FOUND when empty (`src/test/java/org/springframework/samples/petclinic/rest/OwnerRestControllerTests.java:35-42`)
- GET `/api/owners/{id}` returns 200 OK with DTO, 404 NOT_FOUND for invalid ID (`src/test/java/org/springframework/samples/petclinic/rest/OwnerRestControllerTests.java:44-51`)
- POST `/api/owners` creates resource, returns 201 CREATED with Location header (`src/test/java/org/springframework/samples/petclinic/rest/OwnerRestControllerTests.java:53-63`)
- PUT `/api/owners/{id}` updates, returns 204 NO_CONTENT, 400 BAD_REQUEST for ID mismatch (`src/test/java/org/springframework/samples/petclinic/rest/OwnerRestControllerTests.java:65-76`)
- DELETE `/api/owners/{id}` removes, returns 204 NO_CONTENT (`src/test/java/org/springframework/samples/petclinic/rest/OwnerRestControllerTests.java:78-86`)
- **Contract gaps**: No DELETE cascade testing, limited error payload validation (BindingErrorsResponse structure not assert-verified)

**Repository layer contracts** (`src/test/java/org/springframework/samples/petclinic/service/clinicService/ClinicServiceJdbcTests.java`):
- Multiple persistence strategies (JDBC, JPA, Spring Data JPA) must produce identical results
- Finder methods return sorted collections (`src/test/java/org/springframework/samples/petclinic/service/clinicService/AbstractClinicServiceTests.java:103-120`)
- Save operations persist associations (Pet→Visit, Owner→Pet) correctly

**Critical assertion values** (from test files):
- Owner search returns sorted results by lastName, firstName (`src/test/java/org/springframework/samples/petclinic/service/clinicService/AbstractClinicServiceTests.java:103-120`)
- Pet visits sorted by date descending (`src/main/java/org/springframework/samples/petclinic/model/Pet.java:89`, Visit.java behavior)
- Phone numbers validated to 10 digits (`src/main/java/org/springframework/samples/petclinic/model/Owner.java:49`)

**Evidence**: Test class hierarchy demonstrates three persistence backends tested identically (`ClinicServiceJdbcTests.java`, `JpaTests.java`, `SpringDataJpaTests.java`), REST controller tests verify status codes and response structures (`OwnerRestControllerTests.java` throughout), service tests verify business logic and transactions (`AbstractClinicServiceTests.java:35-147`), findings inventory lists 37 rules with test coverage (`migration/findings-inventory.md:1-3`).

## 5. Modernization surface

**Component-by-component modernization requirements:**

**Controllers (REDESIGN):**
- **Mandatory** (`springboot-web-to-quarkus-00000`): Replace Spring `@RestController` with JAX-RS `@Path`, eliminate spring-web dependency (`src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:39-41`)
- **Mandatory** (`springboot-di-to-quarkus-00003`): Constructor injection via CDI `@Inject`, remove `@Autowired` (`src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:47`)
- **Design decision needed**: `@PreAuthorize` security → Quarkus security model or removal

**Services (REDESIGN):**
- **Mandatory** (`springboot-di-to-quarkus-00003`): Replace `@Service` with CDI `@ApplicationScoped`, constructor injection (`src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java:47, 58-72`)
- **Mandatory** (`transaction-to-quarkus-00003`): Replace `@Transactional` with `jakarta.transaction.Transactional` (`src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java:75, 131, etc.`)
- **Optional** (`springboot-cache-to-quarkus-00000`): Replace `@Cacheable` with Quarkus cache extension or remove (`src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java:264`)

**Repositories (REDESIGN):**
- **Design decision needed** (`springboot-jpa-to-quarkus-00000`): JPA repositories → Panache `JpaRepository` or native JPA with CDI
- **Mandatory** (`persistence-to-quarkus-00010`): Replace `@PersistenceContext` with `@Inject` EntityManager (`src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaOwnerRepositoryImpl.java:40`, `src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetRepositoryImpl.java:40`, etc.)

**Models (HARVEST):**
- **Mandatory** (`javax-to-jakarta-import-00001`): Replace `javax.persistence.*` imports with `jakarta.persistence.*` (`src/main/java/org/springframework/samples/petclinic/model/Owner.java:22-24`, `src/main/java/org/springframework/samples/petclinic/model/Pet.java:22`, `src/main/java/org/springframework/samples/petclinic/model/Visit.java:20-21`, etc.)
- **Preserve**: Validation annotations, JPA mappings, business logic in getters/setters

**POM & Configuration (rewrite):**
- **Mandatory** (`springboot-parent-pom-to-quarkus-00000`): Quarkus BOM replaces Spring Boot parent (`pom.xml:14`)
- **Mandatory** (`javaee-pom-to-quarkus-00010/20/30/40/50/60`): Quarkus Maven plugin, compiler plugin, test plugins (`pom.xml:4`)
- **Mandatory** (`springboot-properties-to-quarkus-00001/02/03`): Consolidate property files, use Quarkus keys (`src/main/resources/application.properties:33-34`, `src/main/resources/application-mysql.properties:8-11`, etc.)

**Evidence**: Findings inventory maps each component to specific rule IDs (`migration/findings-inventory.md:5-318`), with 37 total rules: 3 recipe, 17 rewrite, 7 infer, 7 open design, 3 optional (`migration/findings-inventory.md:331-335`).

## 6. Domain boundaries

**Single bounded context**: Pet Clinic Management

The application forms a cohesive, single bounded context despite its layered architecture. All entities (Owner, Pet, Visit, Vet, Specialty, PetType) belong to the same domain vocabulary and business operations. There are no separate bounded contexts with different ubiquitous languages or integration patterns.

**Component cohesion analysis:**
- **Tight coupling** (circular dependency group from `migration/dependency-order.md:42-105`): All entities, repositories, mappers, and services are interconnected through type dependencies and import relationships. This reflects the normalized domain model where Pet→Owner, Visit→Pet/Vet, Pet→PetType relationships create natural coupling.
- **Candidate seams** for incremental modernization:
  1. **Data model layer** (entities + DTOs): Can be harvested first as pure data carriers
  2. **Repository layer** (all repository implementations): Modernize together due to circular dependencies
  3. **Service layer** (ClinicService/UserService): Depends on repositories, exposes business facade (`src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java:47`)
  4. **Controller layer** (REST endpoints): Depends on services, requires JAX-RS conversion (`src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:39`)
  5. **Infrastructure** (security, config, Swagger): Can be simplified/removed during modernization

**Risk assessment**: The god nodes (PetType fan-in 18, Visit fan-in 18, Pet fan-in 17 from `migration/dependency-order.md:8-14`) indicate these entities are referenced throughout the codebase. Characterization tests must pin their behavior before conversion to prevent regressions.

**Evidence**: Dependency graph shows 84 classes forming one large circular group (`migration/dependency-order.md:42-105`), indicating unified domain model rather than multiple bounded contexts. Service facade pattern implementation (`src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java:47`) demonstrates single domain cohesion. REST controller dependency injection (`src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:44-50`) shows controller-service coupling.

## 7. Class roles & target contract

**HARVEST classes** (data/value objects, pure utilities):
- **Models**: `BaseEntity`, `NamedEntity`, `Person`, `Owner`, `Pet`, `Visit`, `Vet`, `Specialty`, `PetType`, `Role`, `User` — preserve JPA mappings, validation, business logic in accessors
- **DTOs**: `OwnerDto`, `PetDto`, `VisitDto`, `VetDto`, `SpecialtyDto`, `PetTypeDto`, `UserDto`, `RoleDto`, `VisitFieldsDto`, `OwnerFieldsDto`, `PetFieldsDto`, plus OpenAPI-generated DTOs — preserve JSON contracts
- **Utilities**: `EntityUtils` — pure static methods for entity manipulation
- **Package-info**: All `package-info.java` files — carry over documentation

**REDESIGN classes** (runtime behavior, modernization required):

**Mapper layer** (convert to CDI or static):
- `OwnerMapper`, `PetMapper`, `VisitMapper`, `VetMapper`, `SpecialtyMapper`, `PetTypeMapper`, `UserMapper` → **REDESIGN — convert MapStruct mappings to static methods or CDI**
- Generated mapper implementations (`OwnerMapperImpl`, `PetMapperImpl`, `VisitMapperImpl`, `VetMapperImpl`, `SpecialtyMapperImpl`, `PetTypeMapperImpl`, `UserMapperImpl`) → **REDESIGN — regenerate with MapStruct in target, convert @Component to static utility or @ApplicationScoped CDI** (`src/main/java/org/springframework/samples/petclinic/mapper/OwnerMapperImpl.java:17`)

**Repository layer** (convert to CDI + Panache/JPA):
- `OwnerRepository`, `PetRepository`, `VisitRepository`, `VetRepository`, `SpecialtyRepository`, `PetTypeRepository`, `UserRepository` → interfaces preserved, implementation modernized
- `JdbcOwnerRepositoryImpl`, `JdbcPetRepositoryImpl`, `JdbcVisitRepositoryImpl`, `JdbcVetRepositoryImpl`, `JdbcSpecialtyRepositoryImpl`, `JdbcPetTypeRepositoryImpl`, `JdbcUserRepositoryImpl` → **REDESIGN — removed: replaced with Panache repositories or single JPA implementation**
- `JpaOwnerRepositoryImpl`, `JpaPetRepositoryImpl`, `JpaVisitRepositoryImpl`, `JpaVetRepositoryImpl`, `JpaSpecialtyRepositoryImpl`, `JpaPetTypeRepositoryImpl`, `JpaUserRepositoryImpl` → **REDESIGN — convert to CDI + native JPA or Panache**
- `SpringDataOwnerRepository`, `SpringDataPetRepository`, `SpringDataVisitRepository`, `SpringDataVetRepository`, `SpringDataSpecialtyRepository`, `SpringDataPetTypeRepository`, `SpringDataUserRepository`, `SpringDataPetRepositoryImpl`, `SpringDataSpecialtyRepositoryImpl`, `SpringDataPetTypeRepositoryImpl`, `SpringDataVisitRepositoryImpl`, plus `*RepositoryOverride` classes → **REDESIGN — consolidate to Panache or single JPA approach**

**Service layer** (convert to CDI beans):
- `ClinicServiceImpl` → **REDESIGN — @ApplicationScoped CDI bean with constructor injection** (`src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java:47, 58-72`)
  - **Concurrency**: Stateless service facade → thread-safe by design (no mutable state)
  - **Resource/cache policy**: `@Cacheable("vets")` → **remove caching** (no clear refresh policy needed)
  - **Transactions**: Replace `@Transactional` with `jakarta.transaction.Transactional` on methods requiring transactions
- `UserServiceImpl` → **REDESIGN — @ApplicationScoped CDI bean with constructor injection** (`src/main/java/org/springframework/samples/petclinic/service/UserServiceImpl.java:10, 13`)

**Controller layer** (convert to JAX-RS resources):
- `OwnerRestController` → **REDESIGN — JAX-RS `@Path("/api/owners")` resource** (`src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java:41`)
  - **API contract (behavior-CHANGING decisions)**:
    - `GET /api/owners` → returns **200 OK** with JSON collection, **404 NOT_FOUND** if empty
    - `GET /api/owners/{id}` → returns **200 OK** with JSON, **404 NOT_FOUND** if not found
    - `POST /api/owners` → returns **201 CREATED** with Location header, **400 BAD_REQUEST** on validation errors
    - `PUT /api/owners/{id}` → returns **204 NO_CONTENT**, **400 BAD_REQUEST** on ID mismatch, **404 NOT_FOUND** if not found
    - `DELETE /api/owners/{id}` → returns **204 NO_CONTENT**, **404 NOT_FOUND** if not found
  - **Input validation**: `@Valid` → reject with **400** (problem-detail)
  - **Error mapping**: Business exceptions → **503** via JAX-RS **ExceptionMapper** (never raw 500)
  - **Concurrency**: Stateless controller → thread-safe
  - **Dependency injection**: Replace `@Autowired` constructor with CDI `@Inject`
- `PetRestController`, `VetRestController`, `VisitRestController`, `PetTypeRestController`, `SpecialtyRestController`, `UserRestController` → **REDESIGN — JAX-RS resources with identical contract patterns**
- `RootRestController` → **REDESIGN — JAX-RS resource or removed** (`src/main/java/org/springframework/samples/petclinic/rest/RootRestController.java:38`)

**Infrastructure layer**:
- `ClinicService`, `UserService` → **REDESIGN — interfaces preserved but implementation modernized**
- `BasicAuthenticationConfig` → **REDESIGN — simplify or remove based on security requirements** (`src/main/java/org/springframework/samples/petclinic/security/BasicAuthenticationConfig.java:17, 22, 40`)
- `DisableSecurityConfig` → **REDESIGN — removed (no Spring Security in target)**
- `Roles` → **REDESIGN — convert to constants or enum in target package** (`src/main/java/org/springframework/samples/petclinic/security/Roles.java:5`)
- `ApplicationSwaggerConfig` → **REDESIGN — removed (OpenAPI generation replaced by target build tools)** (`src/main/java/org/springframework/samples/petclinic/util/ApplicationSwaggerConfig.java:50, 55, 83`)
- `CallMonitoringAspect` → **REDESIGN — replaced by Quarkus Micrometer integration** (`src/main/java/org/springframework/samples/petclinic/util/CallMonitoringAspect.java:37, 47, 52, 57, 63, 68`)
- `ExceptionControllerAdvice`, `BindingErrorsResponse` → **REDESIGN — replaced by JAX-RS ExceptionMapper**
- `PetClinicApplication` → **REDESIGN — removed (Quarkus bootstrap replaces Spring Boot)** (`src/main/java/org/springframework/samples/petclinic/PetClinicApplication.java:7`)

**Evidence**: Every @RestController, @Service, @Component, and @Repository class must be classified REDESIGN per ANALYSIS.md section 7.3 (lines 79-82). REST endpoints require explicit HTTP status codes and error mapping per section 7.4 (lines 103-116). The circular dependency group (`migration/dependency-order.md:42-105`) determines conversion order and coupling risk.
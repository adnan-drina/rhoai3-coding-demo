# Tasks: PetClinic REST to Quarkus Migration

**Input**: Design documents from `/specs/001-petclinic-quarkus-migration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Tests**: Included — Constitution Article IV requires tests with the code (≥80% coverage).

**Organization**: Tasks follow SDD ordering (build → security → schema → API contracts → test infra → feature work → surfaces).

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Build Foundations

**Purpose**: POM/BOM, project structure, Quarkus extensions, Maven configuration

- [ ] T001 Author `pom.xml` with Red Hat Quarkus BOM 3.27.3.SP1, Java 21 compiler, and Maven plugins per `reference-rh-quarkus-pom` skill
- [ ] T002 Add Quarkus extensions: `quarkus-resteasy-jackson`, `quarkus-hibernate-orm-panache`, `quarkus-hibernate-orm`, `quarkus-jdbc-h2`, `quarkus-smallrye-health`, `quarkus-arc` via `manage-quarkus-extensions` skill
- [ ] T003 [P] Create `src/main/java/com/demo/PetClinicApplication.java` — minimal Quarkus main class
- [ ] T004 [P] Create `src/test/java/com/demo/PetClinicApplicationTests.java` — base `@QuarkusTest` that proves the app boots
- [ ] T005 Create `src/main/resources/application.properties` with default H2 profile, HTTP port 8080, and `%dev`/`%test`/`%native` profile sections

**Checkpoint**: `mvn clean compile` succeeds; `mvn test` runs the boot test and passes

---

## Phase 2: Security Foundations

**Purpose**: Authentication/authorization configuration before exposing APIs

- [ ] T006 Create `src/main/java/com/demo/config/SecurityConfig.java` — basic auth via Quarkus Elytron Security (maps legacy `BasicAuthenticationConfig`)
- [ ] T007 [P] Create `src/main/java/com/demo/config/SecurityDisabledConfig.java` — profile-based security disable (maps legacy `DisableSecurityConfig`, active in `%test` profile)
- [ ] T007b [P] Create `src/test/java/com/demo/config/SecurityConfigTest.java` — `@QuarkusTest` proving default profile auth and `%test` security disable
- [ ] T008 Add security extensions to `pom.xml`: `quarkus-elytron-security-properties-file`, `quarkus-security`

**Checkpoint**: Application boots with security enabled in default profile and disabled in `%test`

---

## Phase 3: Data / Schema (Persistence)

**Purpose**: JPA entities, relationships, and seed data

- [ ] T009 [P] Create `src/main/java/com/demo/model/BaseEntity.java` — `@MappedSuperclass` with `@Id` Integer field
- [ ] T010 [P] Create `src/main/java/com/demo/model/NamedEntity.java` — `@MappedSuperclass` extending `BaseEntity` with `name` field
- [ ] T011 [P] Create `src/main/java/com/demo/model/Person.java` — `@MappedSuperclass` extending `BaseEntity` with `firstName`, `lastName`
- [ ] T012 [P] Create `src/main/java/com/demo/model/PetType.java` — JPA entity extending `NamedEntity`
- [ ] T013 [P] Create `src/main/java/com/demo/model/Specialty.java` — JPA entity extending `BaseEntity` with `name` field
- [ ] T014 Create `src/main/java/com/demo/model/Owner.java` — JPA entity extending `Person` with `address`, `city`, `telephone`, and `Set<Pet>` (one-to-many cascade)
- [ ] T015 Create `src/main/java/com/demo/model/Pet.java` — JPA entity extending `NamedEntity` with `birthDate`, `owner` (many-to-one), `type` (many-to-one PetType), `Set<Visit>` (one-to-many cascade)
- [ ] T016 Create `src/main/java/com/demo/model/Vet.java` — JPA entity extending `Person` with `Set<Specialty>` (many-to-many via `VET_SPECIALTY`)
- [ ] T017 Create `src/main/java/com/demo/model/Visit.java` — JPA entity extending `BaseEntity` with `date`, `description`, `pet` (many-to-one)
- [ ] T018 Create `src/main/java/com/demo/model/User.java` — standalone JPA entity with `username`, `password`, `enabled`, `role`
- [ ] T019 Create `src/main/resources/import.sql` — seed data derived from legacy `populateDB.sql` (HSQLDB-compatible)
- [ ] T020 Configure `application.properties` JPA settings: `quarkus.hibernate-orm.database.generation=drop-and-create`, `quarkus.hibernate-orm.sql-load-script=import.sql`

**Checkpoint**: All entities compile; `mvn test` with a basic entity persistence test passes

---

## Phase 4: Repository Interfaces (API Contracts)

**Purpose**: JPA repository interfaces that services depend on

- [ ] T021 [P] Create `src/main/java/com/demo/repository/OwnerRepository.java` — Panache repository interface with `findByLastName`, `findAll`, `findById`, `deleteById`
- [ ] T022 [P] Create `src/main/java/com/demo/repository/PetRepository.java` — Panache repository with `findByOwner`, `findById`, `findAll`
- [ ] T023 [P] Create `src/main/java/com/demo/repository/VisitRepository.java` — Panache repository with `findByPet`, `findById`, `findAll`
- [ ] T024 [P] Create `src/main/java/com/demo/repository/VetRepository.java` — Panache repository with `findAll`, `findById`
- [ ] T025 [P] Create `src/main/java/com/demo/repository/PetTypeRepository.java` — Panache repository with `findAll`, `findById`
- [ ] T026 [P] Create `src/main/java/com/demo/repository/SpecialtyRepository.java` — Panache repository with `findAll`, `findById`

**Checkpoint**: Repository interfaces compile; service layer can inject them

---

## Phase 5: Service Layer (API Contracts)

**Purpose**: CDI service interfaces and implementations

- [ ] T027 Create `src/main/java/com/demo/service/ClinicService.java` — CDI interface declaring owner/pet/visit/vet/petType/specialty operations
- [ ] T028 Create `src/main/java/com/demo/service/ClinicServiceImpl.java` — `@ApplicationScoped` implementation with constructor-injected repositories
- [ ] T029 [P] Create `src/main/java/com/demo/service/UserService.java` — CDI interface for user operations
- [ ] T030 [P] Create `src/main/java/com/demo/service/UserServiceImpl.java` — `@ApplicationScoped` implementation
- [ ] T030b [P] Create `src/test/java/com/demo/service/ClinicServiceTest.java` — `@QuarkusTest` covering ClinicService operations

**Checkpoint**: Services compile and are injectable

---

## Phase 6: Test Infrastructure

**Purpose**: Test fixtures, base classes, and shared test utilities

- [ ] T031 Create `src/test/java/com/demo/AbstractClinicServiceTest.java` — `@QuarkusTest` base class with `@BeforeEach` seed-data setup (maps legacy `AbstractClinicServiceTests`)
- [ ] T032 [P] Create `src/test/resources/application.properties` — test profile with security disabled and H2 in-memory DB

**Checkpoint**: Test infrastructure compiles; base test class runs

---

## Phase 7: User Story 1 — Browse Pet Clinic Resources (P1) 🎯 MVP

**Goal**: All GET endpoints return correct JSON matching legacy output

**Independent Test**: `GET /api/vets`, `GET /api/owners`, `GET /api/pets`, `GET /api/visits`, `GET /api/pettypes`, `GET /api/specialties` all return correct JSON

### Implementation for User Story 1

- [ ] T033 Create `src/main/java/com/demo/dto/VetDto.java` — response DTO with `id`, `firstName`, `lastName`, `specialties` (list of specialty names)
- [ ] T034 [P] Create `src/main/java/com/demo/rest/RootResource.java` — `@Path("/")` redirect to Swagger/API docs (maps legacy `RootRestController`)
- [ ] T035 Create `src/main/java/com/demo/rest/VetResource.java` — `@Path("/api/vets")` with `GET /` (all vets as VetDto) and `GET /{vetId}`
- [ ] T036 [P] Create `src/main/java/com/demo/rest/PetTypeResource.java` — `@Path("/api/pettypes")` with `GET /` and `GET /{petTypeId}`
- [ ] T037 [P] Create `src/main/java/com/demo/rest/SpecialtyResource.java` — `@Path("/api/specialties")` with `GET /` and `GET /{specialtyId}`
- [ ] T038 Create `src/main/java/com/demo/rest/OwnerResource.java` — `@Path("/api/owners")` with `GET /` (all owners), `GET /{ownerId}`, `GET /*/lastname/{lastName}`
- [ ] T039 [P] Create `src/main/java/com/demo/rest/PetResource.java` — `@Path("/api/pets")` with `GET /` (all pets), `GET /{petId}`, `GET /pettypes`
- [ ] T040 [P] Create `src/main/java/com/demo/rest/VisitResource.java` — `@Path("/api/visits")` with `GET /` (all visits), `GET /{visitId}`
- [ ] T041 Create `src/main/java/com/demo/config/ErrorHandling.java` — global exception handler (maps legacy `ExceptionControllerAdvice`) with proper HTTP status codes
- [ ] T042 [P] [US1] Create `src/test/java/com/demo/rest/VetResourceTest.java` — `@QuarkusTest` verifying GET /api/vets returns correct VetDto array
- [ ] T043 [P] [US1] Create `src/test/java/com/demo/rest/OwnerResourceTest.java` — `@QuarkusTest` verifying GET /api/owners and lastname search
- [ ] T044 [P] [US1] Create `src/test/java/com/demo/rest/PetResourceTest.java` — `@QuarkusTest` verifying GET /api/pets
- [ ] T045 [P] [US1] Create `src/test/java/com/demo/rest/VisitResourceTest.java` — `@QuarkusTest` verifying GET /api/visits

**Checkpoint**: All 14 GET endpoints return correct JSON; acceptance probe (`GET /api/vets`) passes

---

## Phase 8: User Story 2 — Manage Owners, Pets, and Visits (P1)

**Goal**: Full CRUD for Owner, Pet, and Visit entities

**Independent Test**: Create → Read → Update → Delete cycle for each entity type succeeds with correct persistence

### Implementation for User Story 2

- [ ] T046 [US2] Add POST, PUT, DELETE to `src/main/java/com/demo/rest/OwnerResource.java` — create owner, update owner, delete owner (cascade to pets/visits)
- [ ] T047 [US2] Add POST, PUT, DELETE to `src/main/java/com/demo/rest/PetResource.java` — create pet, update pet, delete pet
- [ ] T048 [US2] Add POST, PUT, DELETE to `src/main/java/com/demo/rest/VisitResource.java` — create visit, update visit, delete visit
- [ ] T049 Create `src/main/java/com/demo/dto/BindingErrorsResponse.java` — validation error response DTO (maps legacy `BindingErrorsResponse`)
- [ ] T050 [P] [US2] Create `src/test/java/com/demo/rest/OwnerResourceTest.java` — add POST/PUT/DELETE tests (extend existing file)
- [ ] T051 [P] [US2] Create `src/test/java/com/demo/rest/PetResourceTest.java` — add POST/PUT/DELETE tests (extend existing file)
- [ ] T052 [P] [US2] Create `src/test/java/com/demo/rest/VisitResourceTest.java` — add POST/PUT/DELETE tests (extend existing file)

**Checkpoint**: All Owner/Pet/Visit CRUD operations work with correct HTTP status codes (201, 204, 404)

---

## Phase 9: User Story 3 — Manage Vets, Pet Types, and Specialties (P2)

**Goal**: Full CRUD for Vet, PetType, and Specialty reference data

**Independent Test**: Create → Read → Update → Delete cycle for each reference entity succeeds

### Implementation for User Story 3

- [ ] T053 [US3] Add POST, PUT, DELETE to `src/main/java/com/demo/rest/VetResource.java` — create vet with specialties, update vet, delete vet
- [ ] T054 [P] [US3] Add POST, PUT, DELETE to `src/main/java/com/demo/rest/PetTypeResource.java` — CRUD for pet types
- [ ] T055 [P] [US3] Add POST, PUT, DELETE to `src/main/java/com/demo/rest/SpecialtyResource.java` — CRUD for specialties
- [ ] T056 [P] [US3] Create `src/test/java/com/demo/rest/VetResourceTest.java` — add POST/PUT/DELETE tests
- [ ] T057 [P] [US3] Create `src/test/java/com/demo/rest/PetTypeResourceTest.java` — `@QuarkusTest` for pet type CRUD
- [ ] T058 [P] [US3] Create `src/test/java/com/demo/rest/SpecialtyResourceTest.java` — `@QuarkusTest` for specialty CRUD

**Checkpoint**: All reference data CRUD operations work; vet specialties many-to-many relationship persists correctly

---

## Phase 10: User Story 4 — User Management and Root Redirect (P2)

**Goal**: User endpoint and root redirect functional

**Independent Test**: POST /api/users creates a user; GET / redirects correctly

### Implementation for User Story 4

- [ ] T059 [US4] Create `src/main/java/com/demo/rest/UserResource.java` — `@Path("/api/users")` with POST to create user (maps legacy `UserRestController`)
- [ ] T060 [P] [US4] Create `src/test/java/com/demo/rest/UserResourceTest.java` — `@QuarkusTest` for user creation
- [ ] T061 [P] [US4] Create `src/test/java/com/demo/rest/RootResourceTest.java` — verify root redirect

**Checkpoint**: User endpoint and root redirect work

---

## Phase 11: Service Layer Tests

**Purpose**: Complete service-level test coverage

- [ ] T062 Create `src/test/java/com/demo/service/ClinicServiceTest.java` — `@QuarkusTest` covering all ClinicService operations (maps legacy `ClinicServiceSpringDataJpaTests`)
- [ ] T063 [P] Create `src/test/java/com/demo/service/UserServiceTest.java` — `@QuarkusTest` covering UserService operations

**Checkpoint**: Service tests pass with ≥80% line coverage on service classes

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, error handling, and quality gates

- [ ] T064 Add `@Path("/petclinic/api/vets")` alias to `VetResource.java` — acceptance probe path from `migration.yaml`
- [ ] T064b [P] Extend `src/test/java/com/demo/rest/VetResourceTest.java` for the alias path
- [ ] T065 [P] Verify `mvn clean verify` passes with zero failures and ≥80% coverage
- [ ] T066 [P] Run quickstart.md validation scenarios end-to-end
- [ ] T067 Final integration test: verify all 34 endpoints respond correctly against seeded data

**Checkpoint**: `mvn clean verify` green; all 34 endpoints verified; coverage ≥80%

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Build)**: No dependencies — start immediately
- **Phase 2 (Security)**: Depends on Phase 1
- **Phase 3 (Data/Schema)**: Depends on Phase 1 (entities need compiled project)
- **Phase 4 (Repositories)**: Depends on Phase 3 (repositories need entities)
- **Phase 5 (Services)**: Depends on Phase 4 (services need repositories)
- **Phase 6 (Test Infra)**: Depends on Phase 1 (test base needs compiled project)
- **Phase 7 (US1 — Browse)**: Depends on Phases 2-6 (needs entities, repos, services, test infra)
- **Phase 8 (US2 — CRUD Owners/Pets/Visits)**: Depends on Phase 7
- **Phase 9 (US3 — CRUD Reference Data)**: Depends on Phase 7
- **Phase 10 (US4 — Users)**: Depends on Phase 7
- **Phase 11 (Service Tests)**: Depends on Phase 7
- **Phase 12 (Polish)**: Depends on all phases

### Parallel Opportunities

- Phase 3: All entity models (T009-T018) are [P] — different files
- Phase 4: All repository interfaces (T021-T026) are [P]
- Phase 7: DTO, RootResource, PetTypeResource, SpecialtyResource, PetResource, VisitResource are [P]
- Phase 8: POST/PUT/DELETE additions to OwnerResource, PetResource, VisitResource are independent
- Phase 9: Vet, PetType, Specialty CRUD additions are [P]

### MVP Scope

**MVP = Phases 1-7** (Build → Security → Data → Repos → Services → Test Infra → Browse endpoints)

After MVP:
1. Complete Phases 1-7
2. Validate: all 14 GET endpoints return correct JSON
3. Acceptance probe: `GET /api/vets` passes
4. Continue with Phases 8-12 for full CRUD coverage

---

## Notes

- SDD ordering followed: build → security → schema → API contracts → test infra → feature work → surfaces
- Each user story phase is independently testable via `@QuarkusTest`
- No `quarkus-spring-*` extensions used anywhere (Constitution Article III)
- Package root is `com.demo` (Constitution Article III)
- All tests use `@QuarkusTest` — no `curl` or script-based exits (T-8 / SR-13)

## Non-Goals

- This task list does NOT include native GraalVM compilation tasks
- Performance benchmarking tasks are NOT included
- Swagger/OpenAPI UI enhancement tasks are NOT included
- Database migration tooling tasks are NOT included

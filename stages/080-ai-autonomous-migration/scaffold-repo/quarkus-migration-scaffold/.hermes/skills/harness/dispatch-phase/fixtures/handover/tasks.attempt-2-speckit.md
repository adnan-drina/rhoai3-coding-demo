# Tasks: Spring Petclinic REST to Quarkus Migration

**Input**: Design documents from `/specs/001-petclinic-rest-migration/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic Quarkus scaffold

- [ ] T001 Create Maven project structure with `pom.xml` using Red Hat Quarkus BOM 3.27.3.SP1 per `reference-rh-quarkus-pom` skill
- [ ] T002 Configure Quarkus Maven plugin, compiler plugin (Java 21), Surefire, and Failsafe in `pom.xml`
- [ ] T003 [P] Add Quarkus extensions: `quarkus-resteasy-reactive-jackson`, `quarkus-hibernate-orm-panache`, `quarkus-hibernate-validator`, `quarkus-smallrye-health` to `pom.xml`
- [ ] T004 [P] Create base package structure: `src/main/java/com/demo/{resource,service,repository,entity,dto}` and `src/test/java/com/demo/{resource,service,repository}`
- [ ] T005 Create `src/main/resources/application.properties` with H2 in-memory datasource config, HTTP port 8080, and Hibernate DDL auto=create-drop
- [ ] T006 [P] Create MySQL and PostgreSQL profile configurations in `application.properties` using `%mysql.` and `%postgresql.` prefixes

**Checkpoint**: Project compiles with `mvn clean compile` and a basic `@QuarkusTest` passes

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core entities, shared infrastructure, and database seeding that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T007 [P] Create `Owner` JPA entity in `src/main/java/com/demo/entity/Owner.java` with fields: id, firstName, lastName, address, city, telephone, pets (List<Pet>)
- [ ] T008 [P] Create `Pet` JPA entity in `src/main/java/com/demo/entity/Pet.java` with fields: id, name, birthDate, owner, type, visits (List<Visit>)
- [ ] T009 [P] Create `PetType` JPA entity in `src/main/java/com/demo/entity/PetType.java` with fields: id, name
- [ ] T010 [P] Create `Visit` JPA entity in `src/main/java/com/demo/entity/Visit.java` with fields: id, date, description, pet
- [ ] T011 [P] Create `Vet` JPA entity in `src/main/java/com/demo/entity/Vet.java` with fields: id, firstName, lastName, specialties (Set<Specialty>)
- [ ] T012 [P] Create `Specialty` JPA entity in `src/main/java/com/demo/entity/Specialty.java` with fields: id, name
- [ ] T013 Configure bidirectional JPA relationships with `@JsonIgnore` on back-references to prevent JSON cycles
- [ ] T014 [P] Create `OwnerDto` in `src/main/java/com/demo/dto/OwnerDto.java` matching legacy JSON shape
- [ ] T015 [P] Create `PetDto` in `src/main/java/com/demo/dto/PetDto.java` matching legacy JSON shape
- [ ] T016 [P] Create `PetTypeDto` in `src/main/java/com/demo/dto/PetTypeDto.java` matching legacy JSON shape
- [ ] T017 [P] Create `VisitDto` in `src/main/java/com/demo/dto/VisitDto.java` matching legacy JSON shape
- [ ] T018 [P] Create `VetDto` in `src/main/java/com/demo/dto/VetDto.java` matching legacy JSON shape (includes specialties list)
- [ ] T019 [P] Create `SpecialtyDto` in `src/main/java/com/demo/dto/SpecialtyDto.java` matching legacy JSON shape
- [ ] T020 Create `OwnerRepository` in `src/main/java/com/demo/repository/OwnerRepository.java` with `@ApplicationScoped`, `@Inject EntityManager`, and JPQL queries: findAll, findById, findByLastName, save, delete
- [ ] T021 Create `PetRepository` in `src/main/java/com/demo/repository/PetRepository.java` with JPQL queries: findAll, findById, save, delete
- [ ] T022 Create `PetTypeRepository` in `src/main/java/com/demo/repository/PetTypeRepository.java` with JPQL queries: findAll, findById, save, delete
- [ ] T023 Create `VisitRepository` in `src/main/java/com/demo/repository/VisitRepository.java` with JPQL queries: findAll, findById, save, delete
- [ ] T024 Create `VetRepository` in `src/main/java/com/demo/repository/VetRepository.java` with JPQL queries: findAll, findById, save, delete (with JOIN FETCH for specialties)
- [ ] T025 Create `SpecialtyRepository` in `src/main/java/com/demo/repository/SpecialtyRepository.java` with JPQL queries: findAll, findById, save, delete
- [ ] T026 Create `src/main/resources/import.sql` with seed data from legacy application (owners, pets, visits, vets, specialties)
- [ ] T027 Create health check indicator in `src/main/java/com/demo/HealthCheck.java` (or verify Quarkus default `/q/health` works)

**Checkpoint**: All entities compile, repositories resolve, and `mvn clean test` passes with basic entity tests

---

## Phase 3: User Story 1 - Owner CRUD Operations (Priority: P1) MVP

**Goal**: Full CRUD for owners including search by last name, with nested pets and visits in responses

**Independent Test**: `@QuarkusTest` in `OwnerResourceTest.java` verifying all 6 owner endpoints return correct HTTP status codes and JSON payloads against H2

### Implementation for User Story 1

- [ ] T028 [US1] Create `OwnerService` in `src/main/java/com/demo/service/OwnerService.java` with `@ApplicationScoped`, constructor-injected `OwnerRepository`, and methods: findAll, findById, findByLastName, create, update, delete (with entity-to-DTO mapping)
- [ ] T029 [US1] Create `OwnerResource` in `src/main/java/com/demo/resource/OwnerResource.java` with JAX-RS `@Path("/owners")` and endpoints: GET `/`, GET `/{ownerId}`, GET `/*/lastname/{lastName}`, POST `/`, PUT `/{ownerId}`, DELETE `/{ownerId}`
- [ ] T030 [US1] Implement entity-to-DTO mapping in `OwnerService` (Owner→OwnerDto with nested PetDto and VisitDto lists)
- [ ] T031 [US1] Add input validation to `OwnerResource` POST/PUT endpoints using `@Valid` and Bean Validation annotations on DTOs
- [ ] T032 [US1] Create `OwnerResourceTest` in `src/test/java/com/demo/resource/OwnerResourceTest.java` with `@QuarkusTest` covering all 6 endpoints, 404 for missing owners, and 400 for invalid input

**Checkpoint**: All 6 owner endpoints functional and tested independently

---

## Phase 4: User Story 2 - Pet Management (Priority: P1)

**Goal**: Full CRUD for pets with type and owner relationships, plus pet type listing

**Independent Test**: `@QuarkusTest` in `PetResourceTest.java` verifying all 6 pet endpoints against H2

### Implementation for User Story 2

- [ ] T033 [US2] Create `PetService` in `src/main/java/com/demo/service/PetService.java` with `@ApplicationScoped`, constructor-injected `PetRepository`, and methods: findAll, findById, create, update, delete (with entity-to-DTO mapping)
- [ ] T034 [US2] Create `PetResource` in `src/main/java/com/demo/resource/PetResource.java` with JAX-RS `@Path("/pets")` and endpoints: GET `/`, GET `/{petId}`, POST `/`, PUT `/{petId}`, DELETE `/{petId}`, GET `/pettypes`
- [ ] T035 [US2] Implement entity-to-DTO mapping in `PetService` (Pet→PetDto with nested PetTypeDto)
- [ ] T036 [US2] Add input validation to `PetResource` POST/PUT endpoints
- [ ] T037 [US2] Create `PetResourceTest` in `src/test/java/com/demo/resource/PetResourceTest.java` with `@QuarkusTest` covering all pet endpoints including pet types listing

**Checkpoint**: All pet endpoints functional and tested independently

---

## Phase 5: User Story 3 - Pet Types Management (Priority: P2)

**Goal**: Full CRUD for pet types (reference data)

**Independent Test**: `@QuarkusTest` in `PetTypeResourceTest.java` verifying all 6 pet type endpoints

### Implementation for User Story 3

- [ ] T038 [P] [US3] Create `PetTypeService` in `src/main/java/com/demo/service/PetTypeService.java` with `@ApplicationScoped`, constructor-injected `PetTypeRepository`, and methods: findAll, findById, create, update, delete
- [ ] T039 [US3] Create `PetTypeResource` in `src/main/java/com/demo/resource/PetTypeResource.java` with JAX-RS `@Path("/pettypes")` and endpoints: GET `/`, GET `/{petTypeId}`, POST `/`, PUT `/{petTypeId}`, DELETE `/{petTypeId}`
- [ ] T040 [US3] Add input validation to `PetTypeResource` POST/PUT endpoints (unique name constraint)
- [ ] T041 [US3] Create `PetTypeResourceTest` in `src/test/java/com/demo/resource/PetTypeResourceTest.java` with `@QuarkusTest` covering all pet type endpoints

**Checkpoint**: All pet type endpoints functional and tested independently

---

## Phase 6: User Story 4 - Visit Tracking (Priority: P2)

**Goal**: Full CRUD for veterinary visits linked to pets

**Independent Test**: `@QuarkusTest` in `VisitResourceTest.java` verifying all 5 visit endpoints

### Implementation for User Story 4

- [ ] T042 [P] [US4] Create `VisitService` in `src/main/java/com/demo/service/VisitService.java` with `@ApplicationScoped`, constructor-injected `VisitRepository`, and methods: findAll, findById, create, update, delete
- [ ] T043 [US4] Create `VisitResource` in `src/main/java/com/demo/resource/VisitResource.java` with JAX-RS `@Path("/visits")` and endpoints: GET `/`, GET `/{visitId}`, POST `/`, PUT `/{visitId}`, DELETE `/{visitId}`
- [ ] T044 [US4] Add input validation to `VisitResource` POST/PUT endpoints (pet reference required)
- [ ] T045 [US4] Create `VisitResourceTest` in `src/test/java/com/demo/resource/VisitResourceTest.java` with `@QuarkusTest` covering all visit endpoints

**Checkpoint**: All visit endpoints functional and tested independently

---

## Phase 7: User Story 5 - Vet and Specialty Management (Priority: P2)

**Goal**: Full CRUD for veterinarians and their specialties (many-to-many relationship)

**Independent Test**: `@QuarkusTest` in `VetResourceTest.java` and `SpecialtyResourceTest.java`

### Implementation for User Story 5

- [ ] T046 [P] [US5] Create `VetService` in `src/main/java/com/demo/service/VetService.java` with `@ApplicationScoped`, constructor-injected `VetRepository`, and methods: findAll, findById, create, update, delete (with specialties JOIN FETCH)
- [ ] T047 [P] [US5] Create `SpecialtyService` in `src/main/java/com/demo/service/SpecialtyService.java` with `@ApplicationScoped`, constructor-injected `SpecialtyRepository`, and methods: findAll, findById, create, update, delete
- [ ] T048 [US5] Create `VetResource` in `src/main/java/com/demo/resource/VetResource.java` with JAX-RS `@Path("/vets")` and endpoints: GET `/`, GET `/{vetId}`, POST `/`, PUT `/{vetId}`, DELETE `/{vetId}`
- [ ] T049 [US5] Create `SpecialtyResource` in `src/main/java/com/demo/resource/SpecialtyResource.java` with JAX-RS `@Path("/specialties")` and endpoints: GET `/`, GET `/{specialtyId}`, POST `/`, PUT `/{specialtyId}`, DELETE `/{specialtyId}`
- [ ] T050 [US5] Implement entity-to-DTO mapping for Vet→VetDto (includes specialties list) and Specialty→SpecialtyDto
- [ ] T051 [US5] Create `VetResourceTest` in `src/test/java/com/demo/resource/VetResourceTest.java` with `@QuarkusTest` covering all vet endpoints
- [ ] T052 [US5] Create `SpecialtyResourceTest` in `src/test/java/com/demo/resource/SpecialtyResourceTest.java` with `@QuarkusTest` covering all specialty endpoints

**Checkpoint**: All vet and specialty endpoints functional and tested independently

---

## Phase 8: User Story 6 - User Management and Root Endpoint (Priority: P2)

**Goal**: User account endpoint (`/api/users`) and root redirect endpoint

**Independent Test**: `@QuarkusTest` covering user POST endpoint and root redirect

### Implementation for User Story 6

- [ ] T053 [US6] Create `UserService` in `src/main/java/com/demo/service/UserService.java` with `@ApplicationScoped` and method: createOwnerAsUser (maps legacy UserRestController#addOwner behavior)
- [ ] T054 [US6] Create `UserResource` in `src/main/java/com/demo/resource/UserResource.java` with JAX-RS `@Path("/users")` and POST `/` endpoint
- [ ] T055 [US6] Create `RootResource` in `src/main/java/com/demo/resource/RootResource.java` with `@Path("/")` redirecting to Swagger or appropriate landing page
- [ ] T056 [US6] Create `UserResourceTest` in `src/test/java/com/demo/resource/UserResourceTest.java` with `@QuarkusTest`

**Checkpoint**: User and root endpoints functional

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Integration tests, error handling, and final validation

- [ ] T057 Create global exception mapper in `src/main/java/com/demo/ExceptionMapper.java` for consistent 400/404/409 error responses across all resources
- [ ] T058 [P] Create cross-entity integration test in `src/test/java/com/demo/PetclinicIntegrationTest.java` verifying Owner→Pet→Visit creation flow end-to-end
- [ ] T059 Verify all 34 endpoints are covered by running the full test suite: `mvn clean test`
- [ ] T060 Validate quickstart.md scenarios manually or via script
- [ ] T061 Run `mvn clean verify` to confirm full build passes with quality gates

**Checkpoint**: All 34 endpoints tested, full build passes, ready for M3 dispatch

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Foundational phase completion
  - US1 (Phase 3) and US2 (Phase 4) are P1 and should be completed first
  - US3-US6 (Phases 5-8) are P2 and can proceed after P1 stories
  - User stories can proceed in parallel if capacity allows
- **Polish (Phase 9)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 - Owner CRUD (P1)**: Depends on Phase 2 only. No dependencies on other stories.
- **US2 - Pet Management (P1)**: Depends on Phase 2 only. References Owner and PetType entities but no story coupling.
- **US3 - Pet Types (P2)**: Depends on Phase 2 only. Independent of other stories.
- **US4 - Visits (P2)**: Depends on Phase 2 only. References Pet entity but no story coupling.
- **US5 - Vets/Specialties (P2)**: Depends on Phase 2 only. Independent of other stories.
- **US6 - Users/Root (P2)**: Depends on Phase 2 only. Independent of other stories.

### Within Each User Story

- Service before resource (resource depends on service)
- DTOs and entities before service (service maps them)
- Core implementation before tests
- Story complete before moving to next priority

### Parallel Opportunities

- All Phase 1 tasks marked [P] can run in parallel
- All entity creations (T007-T012) can run in parallel
- All DTO creations (T014-T019) can run in parallel
- All repository creations (T020-T025) can run in parallel
- Once Phase 2 completes, US1 and US2 can start in parallel (both P1)
- US3-US6 can proceed in parallel after their respective blockers clear
- Within each story, service and resource can be written in parallel if DTOs are ready

---

## Parallel Example: User Story 1

```bash
# Launch all DTO/entity work in parallel:
Task: "Create OwnerDto in src/main/java/com/demo/dto/OwnerDto.java"
Task: "Create PetDto in src/main/java/com/demo/dto/PetDto.java"
Task: "Create VisitDto in src/main/java/com/demo/dto/VisitDto.java"

# Then service + resource in parallel:
Task: "Implement OwnerService in src/main/java/com/demo/service/OwnerService.java"
Task: "Implement OwnerResource in src/main/java/com/demo/resource/OwnerResource.java"
```

---

## Implementation Strategy

### MVP First (US1 + Foundation)

1. Complete Phase 1: Setup (T001-T006)
2. Complete Phase 2: Foundational (T007-T027)
3. Complete Phase 3: US1 - Owner CRUD (T028-T032)
4. **STOP and VALIDATE**: Test Owner endpoints independently
5. MVP demonstrates core migration pattern: entity → repository → service → resource → test

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Owners) → Test independently → First working endpoints
3. Add US2 (Pets) → Test independently → Owner+Pet flow works
4. Add US3 (Pet Types) → Test independently
5. Add US4 (Visits) → Test independently → Full Owner→Pet→Visit chain
6. Add US5 (Vets/Specialties) → Test independently
7. Add US6 (Users/Root) → Test independently
8. Polish → Full validation → Ready for M3

### Story-to-M3 Mapping

Each user story phase (Phases 3-8) maps to one M3 Kanban card:
- **M3-1**: US1 Owner CRUD (T028-T032) — P1, MVP
- **M3-2**: US2 Pet Management (T033-T037) — P1
- **M3-3**: US3 Pet Types (T038-T041) — P2
- **M3-4**: US4 Visits (T042-T045) — P2
- **M3-5**: US5 Vets/Specialties (T046-T052) — P2
- **M3-6**: US6 Users/Root (T053-T056) — P2

Phase 1+2 map to a bootstrap M3 card (foundation). Phase 9 maps to a polish/integration card.

---

## Notes

- Total tasks: 61 (T001-T061)
- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Constitution Check: All tasks use native Quarkus patterns (no Spring compat extensions)
- Package root: `com.demo` per Constitution Article III

## Non-Goals

- **NG-001**: Implementation of any task — this file is planning only, executed by M3 implementers
- **NG-002**: Writing `partition.json` — handover-mint writes the receipt after tasks.md exists
- **NG-003**: Creating M3 Kanban cards — the wave-holder session follows `mint-m3-hermes.md` after M2 Done

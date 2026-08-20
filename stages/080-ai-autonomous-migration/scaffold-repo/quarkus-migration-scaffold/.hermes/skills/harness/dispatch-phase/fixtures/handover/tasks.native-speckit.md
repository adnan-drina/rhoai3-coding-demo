# Tasks: Migrate Spring PetClinic REST to Quarkus

**Input**: Design documents from `specs/001-migrate-petclinic-quarkus/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included — spec requires tests shipped with code at ≥80% coverage (Constitution Article IV).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single Maven module: `src/main/java/com/demo/`, `src/test/java/com/demo/`, `src/main/resources/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization — POM, Quarkus extensions, directory structure, base configuration

- [ ] T001 Author `pom.xml` with Red Hat Quarkus BOM 3.27.3.SP1, Java 21 compiler, and extensions: hibernate-orm, hibernate-orm-panache, resteasy-jackson, smallrye-health, h2, spring-boot-properties, spring-web, spring-data-jpa, spring-di
- [ ] T002 Create project directory structure: `src/main/java/com/demo/{resource,entity,repository,service,dto,exception}`, `src/test/java/com/demo/{resource,repository,service}`, `src/main/resources/`
- [ ] T003 [P] Create `src/main/resources/application.properties` with Quarkus config: HTTP port 8080, H2 datasource, Hibernate ORM settings, profile-based overrides for `%dev` and `%test`
- [ ] T004 [P] Create `src/main/resources/import.sql` with seed data migrated from legacy `data.sql` (owners, pets, visits, vets, pet types, specialties)
- [ ] T005 Create `PetClinicApplication.java` main class in `src/main/java/com/demo/PetClinicApplication.java`

**Checkpoint**: Project builds (`mvn -q clean compile`) and Quarkus dev mode starts (`mvn quarkus:dev`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure — entities, repositories, error handling, and shared DTOs that all stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 [P] Create JPA entity `Owner` in `src/main/java/com/demo/entity/Owner.java` (id, firstName, lastName, address, city, telephone, pets collection; @Entity, @Table, @Id, @GeneratedValue, @OneToMany cascade)
- [ ] T007 [P] Create JPA entity `Pet` in `src/main/java/com/demo/entity/Pet.java` (id, name, birthDate, type, owner, visits; @Entity, @ManyToOne for owner/type, @OneToMany cascade for visits)
- [ ] T008 [P] Create JPA entity `Visit` in `src/main/java/com/demo/entity/Visit.java` (id, date, description, pet; @Entity, @ManyToOne for pet)
- [ ] T009 [P] Create JPA entity `Vet` in `src/main/java/com/demo/entity/Vet.java` (id, firstName, lastName, specialties; @Entity, @ManyToMany for specialties)
- [ ] T010 [P] Create JPA entity `PetType` in `src/main/java/com/demo/entity/PetType.java` (id, name; @Entity, unique constraint on name)
- [ ] T011 [P] Create JPA entity `Specialty` in `src/main/java/com/demo/entity/Specialty.java` (id, name; @Entity, unique constraint on name)
- [ ] T012 [P] Create JPA entity `User` in `src/main/java/com/demo/entity/User.java` (username PK, password, roles; @Entity)
- [ ] T013 [P] Create repository `OwnerRepository` in `src/main/java/com/demo/repository/OwnerRepository.java` (@ApplicationScoped, injected EntityManager, findAll/findById JPQL queries)
- [ ] T014 [P] Create repository `PetRepository` in `src/main/java/com/demo/repository/PetRepository.java` (@ApplicationScoped, injected EntityManager, findAll/findById JPQL queries)
- [ ] T015 [P] Create repository `VisitRepository` in `src/main/java/com/demo/repository/VisitRepository.java` (@ApplicationScoped, injected EntityManager, findAll/findById JPQL queries)
- [ ] T016 [P] Create repository `VetRepository` in `src/main/java/com/demo/repository/VetRepository.java` (@ApplicationScoped, injected EntityManager, findAll/findById JPQL queries with JOIN FETCH for specialties)
- [ ] T017 [P] Create repository `PetTypeRepository` in `src/main/java/com/demo/repository/PetTypeRepository.java` (@ApplicationScoped, injected EntityManager, findAll/findById JPQL queries)
- [ ] T018 [P] Create repository `SpecialtyRepository` in `src/main/java/com/demo/repository/SpecialtyRepository.java` (@ApplicationScoped, injected EntityManager, findAll/findById JPQL queries)
- [ ] T019 [P] Create repository `UserRepository` in `src/main/java/com/demo/repository/UserRepository.java` (@ApplicationScoped, injected EntityManager, findAll/findById JPQL queries)
- [ ] T020 [P] Create DTO `OwnerDto` in `src/main/java/com/demo/dto/OwnerDto.java` matching legacy JSON schema (id, firstName, lastName, address, city, telephone, pets list; Jackson @JsonProperty annotations)
- [ ] T021 [P] Create DTO `PetDto` in `src/main/java/com/demo/dto/PetDto.java` matching legacy JSON schema (id, name, birthDate, type, owner; Jackson annotations)
- [ ] T022 [P] Create DTO `VisitDto` in `src/main/java/com/demo/dto/VisitDto.java` matching legacy JSON schema (id, date, description, pet; Jackson annotations)
- [ ] T023 [P] Create DTO `VetDto` in `src/main/java/com/demo/dto/VetDto.java` matching legacy JSON schema (id, firstName, lastName, specialties; Jackson annotations)
- [ ] T024 [P] Create DTO `PetTypeDto` in `src/main/java/com/demo/dto/PetTypeDto.java` matching legacy JSON schema (id, name; Jackson annotations)
- [ ] T025 [P] Create DTO `SpecialtyDto` in `src/main/java/com/demo/dto/SpecialtyDto.java` matching legacy JSON schema (id, name; Jackson annotations)
- [ ] T026 [P] Create DTO `VisitRequest` in `src/main/java/com/demo/dto/VisitRequest.java` (petId, date, description; Jackson annotations)
- [ ] T027 Create global error handler `ErrorHandler` in `src/main/java/com/demo/exception/ErrorHandler.java` (JAX-RS ExceptionMapper for EntityNotFoundException → 404, IllegalArgumentException → 400, generic Exception → 500; JSON error body)

**Checkpoint**: Foundation ready — all entities, repositories, DTOs, and error handling in place. `mvn -q clean compile` succeeds. User story implementation can now begin.

---

## Phase 3: User Story 1 - Browse veterinary clinic data (Priority: P1) 🎯 MVP

**Goal**: All GET endpoints return valid JSON matching the legacy API schema. Read operations for owners, pets, visits, vets, pet types, and specialties.

**Independent Test**: Each GET endpoint returns HTTP 200 with valid JSON; non-existent IDs return 404; health endpoint at `/q/health` returns UP.

### Tests for User Story 1 ⚠️

- [ ] T028 [P] [US1] Create `OwnerResourceTest` in `src/test/java/com/demo/resource/OwnerResourceTest.java` (@QuarkusTest, REST Assured: GET /api/owners returns 200 with array, GET /api/owners/{id} returns 200 for existing, 404 for missing)
- [ ] T029 [P] [US1] Create `PetResourceTest` in `src/test/java/com/demo/resource/PetResourceTest.java` (@QuarkusTest, REST Assured: GET /api/pets returns 200, GET /api/pets/{id} returns 200/404, GET /api/petTypes returns 200)
- [ ] T030 [P] [US1] Create `VisitResourceTest` in `src/test/java/com/demo/resource/VisitResourceTest.java` (@QuarkusTest, REST Assured: GET /api/visits returns 200, GET /api/visits/{id} returns 200/404)
- [ ] T031 [P] [US1] Create `VetResourceTest` in `src/test/java/com/demo/resource/VetResourceTest.java` (@QuarkusTest, REST Assured: GET /api/vets returns 200 with specialties, GET /api/vets/{id} returns 200/404)
- [ ] T032 [P] [US1] Create `PetTypeResourceTest` in `src/test/java/com/demo/resource/PetTypeResourceTest.java` (@QuarkusTest, REST Assured: GET /api/petTypes returns 200, GET /api/petTypes/{id} returns 200/404)
- [ ] T033 [P] [US1] Create `SpecialtyResourceTest` in `src/test/java/com/demo/resource/SpecialtyResourceTest.java` (@QuarkusTest, REST Assured: GET /api/specialties returns 200, GET /api/specialties/{id} returns 200/404)

### Implementation for User Story 1

- [ ] T034 [US1] Implement `OwnerService` in `src/main/java/com/demo/service/OwnerService.java` (@ApplicationScoped, constructor-injected OwnerRepository, findAll/findById with entity-to-DTO mapping, 404 on not found)
- [ ] T035 [US1] Implement `PetService` in `src/main/java/com/demo/service/PetService.java` (@ApplicationScoped, constructor-injected PetRepository/PetTypeRepository, findAll/findById with entity-to-DTO mapping)
- [ ] T036 [US1] Implement `VisitService` in `src/main/java/com/demo/service/VisitService.java` (@ApplicationScoped, constructor-injected VisitRepository, findAll/findById with entity-to-DTO mapping)
- [ ] T037 [US1] Implement `VetService` in `src/main/java/com/demo/service/VetService.java` (@ApplicationScoped, constructor-injected VetRepository, findAll/findById with JOIN FETCH for specialties)
- [ ] T038 [US1] Implement `PetTypeService` in `src/main/java/com/demo/service/PetTypeService.java` (@ApplicationScoped, constructor-injected PetTypeRepository, findAll/findById)
- [ ] T039 [US1] Implement `SpecialtyService` in `src/main/java/com/demo/service/SpecialtyService.java` (@ApplicationScoped, constructor-injected SpecialtyRepository, findAll/findById)
- [ ] T040 [US1] Implement `OwnerResource` in `src/main/java/com/demo/resource/OwnerResource.java` (JAX-RS @Path("/api/owners"), @GET all and by id, constructor-injected OwnerService, Jackson JSON responses)
- [ ] T041 [US1] Implement `PetResource` in `src/main/java/com/demo/resource/PetResource.java` (JAX-RS @Path("/api/pets"), @GET all pets and by id, @GET /api/petTypes, constructor-injected services)
- [ ] T042 [US1] Implement `VisitResource` in `src/main/java/com/demo/resource/VisitResource.java` (JAX-RS @Path("/api/visits"), @GET all and by id, constructor-injected VisitService)
- [ ] T043 [US1] Implement `VetResource` in `src/main/java/com/demo/resource/VetResource.java` (JAX-RS @Path("/api/vets"), @GET all and by id, constructor-injected VetService)
- [ ] T044 [US1] Implement `PetTypeResource` in `src/main/java/com/demo/resource/PetTypeResource.java` (JAX-RS @Path("/api/petTypes"), @GET all and by id, constructor-injected PetTypeService)
- [ ] T045 [US1] Implement `SpecialtyResource` in `src/main/java/com/demo/resource/SpecialtyResource.java` (JAX-RS @Path("/api/specialties"), @GET all and by id, constructor-injected SpecialtyService)
- [ ] T046 [US1] Add SmallRye Health check in `src/main/java/com/demo/HealthCheck.java` (LivenessHealthCheck + ReadinessHealthCheck with database connectivity verification)

**Checkpoint**: All 34 GET endpoints functional. `mvn -q clean test` passes. Application boots with health UP at `/q/health`. MVP readable.

---

## Phase 4: User Story 2 - Manage clinic entities (Priority: P1)

**Goal**: Full CRUD operations — create (POST), update (PUT), and delete (DELETE) for all entity types with input validation and proper HTTP status codes.

**Independent Test**: POST creates entities (201), PUT updates (200), DELETE removes (200). Invalid input returns 400. Non-existent IDs return 404. Cascade delete works (Owner → Pet → Visit).

### Tests for User Story 2 ⚠️

- [ ] T047 [P] [US2] Extend `OwnerResourceTest` with POST/PUT/DELETE tests: create owner (201), update owner (200), delete owner (200 + cascade), invalid input (400), not found (404)
- [ ] T048 [P] [US2] Extend `PetResourceTest` with POST/PUT/DELETE tests: create pet (201), update pet (200), delete pet (200 + cascade to visits), validation (400)
- [ ] T049 [P] [US2] Extend `VisitResourceTest` with POST/PUT/DELETE tests: create visit (201), update visit (200), delete visit (200), validation (400)
- [ ] T050 [P] [US2] Extend `VetResourceTest` with POST/PUT/DELETE tests: create vet with specialties (201), update vet (200), delete vet (200)
- [ ] T051 [P] [US2] Extend `PetTypeResourceTest` with POST/PUT/DELETE tests: create pet type (201), update (200), delete (200)
- [ ] T052 [P] [US2] Extend `SpecialtyResourceTest` with POST/PUT/DELETE tests: create specialty (201), update (200), delete (200)

### Implementation for User Story 2

- [ ] T053 [US2] Add create/update/delete to `OwnerService` with DTO-to-entity mapping, validation (required fields, max lengths), and cascade delete handling
- [ ] T054 [US2] Add create/update/delete to `PetService` with DTO-to-entity mapping, validation, and cascade delete to visits
- [ ] T055 [US2] Add create/update/delete to `VisitService` with DTO-to-entity mapping, validation (date required)
- [ ] T056 [US2] Add create/update/delete to `VetService` with DTO-to-entity mapping, specialties handling (many-to-many)
- [ ] T057 [US2] Add create/update/delete to `PetTypeService` with DTO-to-entity mapping, unique name validation
- [ ] T058 [US2] Add create/update/delete to `SpecialtyService` with DTO-to-entity mapping, unique name validation
- [ ] T059 [US2] Add POST/PUT/DELETE to `OwnerResource` (@POST returns 201, @PUT returns 200, @DELETE returns 200; @Transactional for mutations)
- [ ] T060 [US2] Add POST/PUT/DELETE to `PetResource` (@POST returns 201, @PUT returns 200, @DELETE returns 200; @Transactional for mutations)
- [ ] T061 [US2] Add POST/PUT/DELETE to `VisitResource` (@POST returns 201, @PUT returns 200, @DELETE returns 200; @Transactional for mutations)
- [ ] T062 [US2] Add POST/PUT/DELETE to `VetResource` (@POST returns 201, @PUT returns 200, @DELETE returns 200; @Transactional for mutations)
- [ ] T063 [US2] Add POST/PUT/DELETE to `PetTypeResource` (@POST returns 201, @PUT returns 200, @DELETE returns 200; @Transactional for mutations)
- [ ] T064 [US2] Add POST/PUT/DELETE to `SpecialtyResource` (@POST returns 201, @PUT returns 200, @DELETE returns 200; @Transactional for mutations)
- [ ] T065 [US2] Implement `UserResource` in `src/main/java/com/demo/resource/UserResource.java` (@Path("/api/users"), POST to create owner via user endpoint per legacy `UserRestController#addOwner`)
- [ ] T065b [US2] Create `UserResourceTest` in `src/test/java/com/demo/resource/UserResourceTest.java` (@QuarkusTest, POST /api/users)

**Checkpoint**: All 34 endpoints fully functional (GET + POST/PUT/DELETE). `mvn -q clean test` passes with ≥80% coverage. Cascade deletes verified.

---

## Phase 5: User Story 3 - Application health and configuration (Priority: P2)

**Goal**: Health checks, configuration profiles, and operational readiness for deployment.

**Independent Test**: `/q/health` returns UP with database connectivity. Application starts on port 8080. Test profile uses in-memory H2.

### Implementation for User Story 3

- [ ] T066 [P] [US3] Verify `application.properties` has `%test` profile with in-memory H2 and `hibernate.hbm2ddl.auto=create-drop`
- [ ] T067 [P] [US3] Verify `application.properties` has `%dev` profile with Dev Services enabled for H2
- [ ] T068 [US3] Create `PetClinicApplicationTest` in `src/test/java/com/demo/PetClinicApplicationTest.java` (@QuarkusTest, verify health endpoint returns UP, verify application boots)

**Checkpoint**: Health checks pass. Configuration profiles verified. Application operational.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, coverage, and quality gate preparation

- [ ] T069 Verify `mvn -q clean verify` passes (full build with integration tests)
- [ ] T070 [P] Verify code coverage ≥80% (JaCoCo report from `mvn -q clean verify`)
- [ ] T071 Run quickstart.md validation scenarios end-to-end
- [ ] T072 [P] Final review: ensure all 34 endpoints match legacy JSON schema (field names, types, nesting)
- [ ] T073 Verify zero new Sonar violations and ≤3% duplicated new lines

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — GET endpoints (MVP)
- **User Story 2 (Phase 4)**: Depends on Foundational — POST/PUT/DELETE (can start after Phase 2, but tests reference Phase 3 resources)
- **User Story 3 (Phase 5)**: Depends on Setup — health/config (independent of US1/US2)
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational — no dependencies on other stories
- **US2 (P1)**: Can start after Foundational — extends resources created in US1 phase
- **US3 (P2)**: Can start after Setup — independent of US1/US2

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Services before resources (resources depend on services)
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Phase 1 tasks marked [P] can run in parallel
- All entity tasks (T006-T012) can run in parallel
- All repository tasks (T013-T019) can run in parallel
- All DTO tasks (T020-T026) can run in parallel
- All test tasks within a story marked [P] can run in parallel
- All service tasks within a story marked [P] can run in parallel
- All resource tasks within a story marked [P] can run in parallel
- US1 and US3 can proceed in parallel after Foundational

---

## Parallel Example: User Story 1

```bash
# Launch all entity models together:
Task: "Create JPA entity Owner in src/main/java/com/demo/entity/Owner.java"
Task: "Create JPA entity Pet in src/main/java/com/demo/entity/Pet.java"
Task: "Create JPA entity Visit in src/main/java/com/demo/entity/Visit.java"
Task: "Create JPA entity Vet in src/main/java/com/demo/entity/Vet.java"
Task: "Create JPA entity PetType in src/main/java/com/demo/entity/PetType.java"
Task: "Create JPA entity Specialty in src/main/java/com/demo/entity/Specialty.java"
Task: "Create JPA entity User in src/main/java/com/demo/entity/User.java"

# Launch all test files together:
Task: "Create OwnerResourceTest in src/test/java/com/demo/resource/OwnerResourceTest.java"
Task: "Create PetResourceTest in src/test/java/com/demo/resource/PetResourceTest.java"
Task: "Create VetResourceTest in src/test/java/com/demo/resource/VetResourceTest.java"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (POM, structure, config)
2. Complete Phase 2: Foundational (entities, repos, DTOs, error handling)
3. Complete Phase 3: User Story 1 (GET endpoints + tests)
4. **STOP and VALIDATE**: Test US1 independently — all read endpoints return correct JSON
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 (GET) → Test independently → MVP readable
3. Add User Story 2 (POST/PUT/DELETE) → Test independently → Full CRUD
4. Add User Story 3 (Health/Config) → Test independently → Operational
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (GET endpoints)
   - Developer B: User Story 2 (mutations)
   - Developer C: User Story 3 (health/config)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- **Total tasks**: 73 (T001–T073)
- **Tasks per story**: US1=19, US2=22, US3=3, Setup=5, Foundational=23, Polish=5

# Tasks: A-8 JAX-RS class @Path (native Spec Kit; no GET /api/… token)

**Input**: Design documents from `/specs/001-migrate/`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure per implementation plan
- [ ] T002 Initialize the project with pom.xml
- [ ] T003 [P] Add src/main/resources/application.properties

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Add src/main/resources/application-prod.properties (also lists pom.xml; unique pom owner strips it)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Owner CRUD (Priority: P1) 🎯 MVP

**Goal**: Full CRUD for owners

**Independent Test**: `@QuarkusTest` in OwnerResourceTest covering owner endpoints

### Implementation for User Story 1

- [ ] T010 [US1] Create `src/main/java/app/OwnerResource.java` with JAX-RS `@Path("/owners")` and endpoints: GET `/`, GET `/{ownerId}`, POST `/`, PUT `/{ownerId}`, DELETE `/{ownerId}`
- [ ] T011 [US1] Add `src/test/java/app/OwnerResourceTest.java`

**Checkpoint**: User Story 1 is independently testable

---

## Phase 4: User Story 2 - Pet CRUD (Priority: P2)

**Goal**: Pets listed and mutated over HTTP

**Independent Test**: `@QuarkusTest` in PetResourceTest covering pet endpoints

### Implementation for User Story 2

- [ ] T020 [US2] Create `src/main/java/app/PetResource.java` with JAX-RS `@Path("/pets")` and endpoints: GET `/`, GET `/{petId}`, POST `/`, PUT `/{petId}`, DELETE `/{petId}`
- [ ] T021 [US2] Add `src/test/java/app/PetResourceTest.java`

**Checkpoint**: User Stories 1 AND 2 both work independently

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable

# Tasks: A-8 transcribed routes (legacy inventory files ≠ dest write-set)

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

## Phase 3: User Story 1 - List owners (Priority: P1) 🎯 MVP

**Goal**: Owners can be listed over HTTP

**Independent Test**: src/test/java/app/OwnerResourceTest.java GET /api/owners returns the owner list

### Implementation for User Story 1

- [ ] T010 [P] [US1] Create src/main/java/app/OwnerResource.java
- [ ] T011 [US1] Add src/test/java/app/OwnerResourceTest.java

**Checkpoint**: User Story 1 is independently testable

---

## Phase 4: User Story 2 - List pets (Priority: P2)

**Goal**: Pets can be listed over HTTP

**Independent Test**: src/test/java/app/PetResourceTest.java GET /api/pets returns the pet list

### Implementation for User Story 2

- [ ] T020 [P] [US2] Create src/main/java/app/PetResource.java
- [ ] T021 [US2] Add src/test/java/app/PetResourceTest.java

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

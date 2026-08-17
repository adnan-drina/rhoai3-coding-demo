---

description: "Task list template for feature implementation"
---

# Tasks: [FEATURE NAME]

**Input**: Design documents from `/specs/[###-feature-name]/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The examples below include test tasks. Tests are OPTIONAL - only include them if explicitly requested in the feature specification.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `src/test/` at repository root (Java / Maven)
- Paths shown below assume this migration dest — adjust only if plan.md says otherwise
- Destination REST is JAX-RS (`*Resource.java`), not Spring `*RestController.java`

## Unique dest-path ownership (mandatory)

**one creator phase per dest path.** Each destination file has exactly one
creator phase. That is path-agnostic (not a `pom.xml`-only rule and not an
`application.properties` special case).

- **Create / Author / Configure** a dest path in **one** phase only — the phase
  that first brings the file into existence.
- Later phases that touch the same path use **Add** or **Verify** only.
  Example: Setup **Author** `pom.xml`; a later story **Add** an extension to
  `pom.xml`. Setup **Configure** `src/main/resources/application.properties`;
  Foundational must **not** **Configure** that same file; a later story may
  **Add** profile keys or **Verify** profile switching.
- Two **Configure** / **Author** / **Create** lines for the same dest path is a
  planning defect. Do not emit it. Sequential **Add** of a creator-owned path
  is legitimate under serial (Architect `E-20260817T131858Z`); mint does not
  refuse that as `FILE_OVERLAP`.
- **Verify** lines that name a dest path are not a second owner.

## Inventory (HTTP)

Cover every HTTP row in `evidence/entry-point-inventory.json` (including
`http_path: /`). Read inventory paths; do not invent a RestController-to-Resource
filename mapper.

<!--
  ============================================================================
  IMPORTANT: The tasks below are SAMPLE TASKS for illustration purposes only.

  The /speckit.tasks command MUST replace these with actual tasks based on:
  - User stories from spec.md (with their priorities P1, P2, P3...)
  - Feature requirements from plan.md
  - Entities from data-model.md
  - Endpoints from contracts/
  - HTTP rows from evidence/entry-point-inventory.json

  Tasks MUST be organized by user story so each story can be:
  - Implemented independently
  - Tested independently
  - Delivered as an MVP increment

  DO NOT keep these sample tasks in the generated tasks.md file.
  ============================================================================
-->

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization — POM, directories, first config file

- [ ] T001 Author pom.xml with Red Hat Quarkus Platform BOM and Java 21 toolchain in pom.xml
- [ ] T002 Create source directory structure in src/main/java/com/demo/ and src/test/java/com/demo/
- [ ] T003 [P] Configure src/main/resources/application.properties with datasource, Hibernate, and HTTP port

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

Do **not** Configure `pom.xml` or `src/main/resources/application.properties` here
— Setup already created them. Add/Verify only if a later story owns that amend.

- [ ] T004 [P] Create Owner entity with JPA annotations in src/main/java/com/demo/entity/Owner.java
- [ ] T005 [P] Create Pet entity with JPA annotations in src/main/java/com/demo/entity/Pet.java
- [ ] T006 [P] Create OwnerRepository in src/main/java/com/demo/repository/OwnerRepository.java
- [ ] T007 Create DTOs matching legacy API contracts in src/main/java/com/demo/dto/

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - [Title] (Priority: P1) 🎯 MVP

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 1 (OPTIONAL - only if tests requested) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T010 [P] [US1] Contract test for [endpoint] in src/test/java/com/demo/resource/[Name]ResourceTest.java
- [ ] T011 [P] [US1] Integration test for [user journey] in src/test/java/com/demo/integration/[Name]IT.java

### Implementation for User Story 1

- [ ] T012 [US1] Create OwnerResource JAX-RS class in src/main/java/com/demo/rest/OwnerResource.java
- [ ] T013 [US1] Verify pom.xml compiles: run `mvn clean compile`

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - [Title] (Priority: P2)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Tests for User Story 2 (OPTIONAL - only if tests requested) ⚠️

- [ ] T018 [P] [US2] Contract test for [endpoint] in src/test/java/com/demo/resource/[Name]ResourceTest.java

### Implementation for User Story 2

- [ ] T020 [US2] Create PetResource JAX-RS class in src/main/java/com/demo/rest/PetResource.java
- [ ] T021 [US2] Add POST, PUT, DELETE to src/main/java/com/demo/rest/OwnerResource.java
- [ ] T022 [US2] Add profile-specific overrides in src/main/resources/application.properties

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - [Title] (Priority: P3)

**Goal**: [Brief description of what this story delivers]

**Independent Test**: [How to verify this story works on its own]

### Implementation for User Story 3

- [ ] T026 [US3] Create VetResource JAX-RS class in src/main/java/com/demo/rest/VetResource.java

**Checkpoint**: All user stories should now be independently functional

---

[Add more user story phases as needed, following the same pattern]

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] TXXX [P] Documentation updates in README.md
- [ ] TXXX Verify quality gate via `mvn clean verify` in pom.xml

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Avoid: two Create/Author/Configure lines for the same dest path; vague tasks; RestController→Resource filename mapping

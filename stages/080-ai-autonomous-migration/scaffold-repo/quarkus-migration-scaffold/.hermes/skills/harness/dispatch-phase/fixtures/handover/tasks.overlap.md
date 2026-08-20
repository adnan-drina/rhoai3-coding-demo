# Tasks: Overlapping write-sets (negative)

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Initialize the project with pom.xml

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T004 Configure src/main/java/app/OwnerEntity.java

## Phase 3: User Story 1 - List owners (Priority: P1)

**Independent Test**: src/test/java/app/OwnerResourceTest.java

- [ ] T010 [US1] Create src/main/java/app/OwnerResource.java
- [ ] T011 [US1] Add src/test/java/app/OwnerResourceTest.java

## Phase 4: User Story 2 - Extend owners (Priority: P2)

**Independent Test**: src/test/java/app/CompanionResourceTest.java

- [ ] T020 [US2] Edit src/main/java/app/OwnerResource.java
- [ ] T021 [US2] Add src/test/java/app/CompanionResourceTest.java

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion

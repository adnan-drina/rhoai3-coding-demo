# Tasks: scratch-assemble ownership strips polish Create pom.xml to Setup
# Operator 203811Z: unique-owner assigns pom.xml to Setup; polish keeps HealthTest.

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Author pom.xml with Red Hat Quarkus Platform BOM in pom.xml

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T002 Create FooEntity in src/main/java/com/demo/FooEntity.java

## Phase 3: User Story 1 - Foo (Priority: P1)

**Independent Test**: GET /api/foo returns 200; `@QuarkusTest` in `src/test/java/com/demo/resource/FooResourceTest.java`

- [ ] T003 [US1] Create FooResource JAX-RS class with @Path("/api/foo") in src/main/java/com/demo/resource/FooResource.java
- [ ] T003b [US1] Create FooResourceTest in src/test/java/com/demo/resource/FooResourceTest.java

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T046 Create extra BOM pins in pom.xml
- [ ] T047 [P] Create HealthTest (@QuarkusTest, GET /q/health returns UP) in src/test/java/com/demo/HealthTest.java

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

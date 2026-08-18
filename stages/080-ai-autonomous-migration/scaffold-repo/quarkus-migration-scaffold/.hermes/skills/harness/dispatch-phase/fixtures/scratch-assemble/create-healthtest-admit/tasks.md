# Tasks: scratch-assemble I-17 admit Create HealthTest.java

## Phase 1: Setup (Shared Infrastructure)

- [ ] T001 Author pom.xml with Red Hat Quarkus Platform BOM in pom.xml

## Phase 2: Foundational (Blocking Prerequisites)

- [ ] T002 Create Foo in src/main/java/com/demo/Foo.java

## Phase 3: User Story 1 - Foo (Priority: P1)

**Independent Test**: GET /api/foo returns 200

- [ ] T003 [US1] Create FooResource JAX-RS class with @Path("/api/foo") in src/main/java/com/demo/resource/FooResource.java

## Phase 4: Polish & Cross-Cutting Concerns

- [ ] T046 Create README.md with destination build and run instructions
- [ ] T047 [P] Create HealthTest (@QuarkusTest, GET /q/health returns UP) in src/test/java/com/demo/HealthTest.java

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

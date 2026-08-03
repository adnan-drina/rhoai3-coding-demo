# S05: Service layer modernization

<!-- The brief is the self-contained work order for one modernization
     story. Bar: a competent developer or a fresh session starts the
     story from THIS FILE ALONE. Fill every section; delete none. -->

## Goal & position

Modernizes the service layer from Spring @Service beans to @ApplicationScoped CDI beans with constructor injection. This REDESIGN story converts ClinicService and UserService implementations to eliminate the facade pattern and implement native Quarkus CDI. Following S04's repository modernization, it completes the business logic layer and unblocks the REST endpoint modernization.

## In scope

The exact legacy classes/files this story modernizes. For each, quote
the load-bearing legacy code (the lines being transformed — imports,
annotations, key methods), so the story never starts from a blank
read:

- `src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java` — main service facade
  ```java
  package org.springframework.samples.petclinic.service;
  
  import org.springframework.beans.factory.annotation.Autowired;
  import org.springframework.cache.annotation.Cacheable;
  import org.springframework.stereotype.Service;
  import org.springframework.transaction.annotation.Transactional;
  
  @Service
  public class ClinicServiceImpl implements ClinicService {
      private PetRepository petRepository;
      private VetRepository vetRepository;
      private OwnerRepository ownerRepository;
  
      @Autowired
      public ClinicServiceImpl(
              PetRepository petRepository,
              VetRepository vetRepository,
              OwnerRepository ownerRepository) {
          this.petRepository = petRepository;
          this.vetRepository = vetRepository;
          this.ownerRepository = ownerRepository;
      }
  ```

- `src/main/java/org/springframework/samples/petclinic/service/UserServiceImpl.java` — user management service
  ```java
  package org.springframework.samples.petclinic.service;
  
  import org.springframework.beans.factory.annotation.Autowired;
  import org.springframework.samples.petclinic.model.User;
  import org.springframework.samples.petclinic.repository.UserRepository;
  import org.springframework.stereotype.Service;
  import org.springframework.transaction.annotation.Transactional;
  
  @Service
  public class UserServiceImpl implements UserService {
      @Autowired
      private UserRepository userRepository;
  
      @Override
      @Transactional
      public void saveUser(User user) throws Exception {
          userRepository.save(user);
      }
  ```

## Out of scope

Repository implementations, REST controllers, and domain entities remain unchanged. This story only modernizes service implementations to use CDI instead of Spring's @Service. REST endpoint modernization happens in S06.

## Class roles & target contract (from architecture-profile §7)

Service classes are REDESIGN - they modernize from Spring DI to Quarkus CDI while preserving business logic contracts:

- **ClinicServiceImpl** — REDESIGN to @ApplicationScoped CDI, facade removed, individual endpoints call repositories directly
- **UserServiceImpl** — REDESIGN to @ApplicationScoped CDI with constructor injection
- **Transaction management** — @Transactional method annotations preserved
- **Business logic** — All repository orchestration and validation logic preserved

## Decided target shapes

Replace Spring @Service DI with Quarkus @ApplicationScoped CDI and remove the facade pattern:

**MAPPINGS transformations:**
- springboot-di-to-quarkus-00003: `@Service` → `@ApplicationScoped` with constructor injection

**Architecture changes:**
- ClinicService facade removed - endpoints call repositories directly
- UserService preserved as separate @ApplicationScoped CDI bean
- Constructor injection replaces @Autowired field injection

## Contracts owned by this story

- **Findings**: N/A - service modernization only
- **seat-budget**: 5 — reimplement work from roadmap `kind × incident count`
- **Preserve**: N/A - no configuration surfaces in this scope
- **Behavioral pins**: All service methods must maintain their business logic exactly
  - saveUser: User validation and role prefixing preserved
  - All clinic service methods: repository call delegation preserved
- **Forbidden**: No changes to business logic or validation rules

## Done-criteria

Checkable, story-scoped:
- Service classes converted to @ApplicationScoped CDI beans
- Constructor injection replaces @Autowired field injection
- @Transactional method annotations preserved and functional
- ClinicService facade removed from REST endpoints (direct repository calls)
- `mvn clean compile` succeeds with CDI annotations
- Service integration tests pass with new CDI lifecycle
- No Spring @Service or @Autowired annotations remain

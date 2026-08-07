# S02: Package rename and recipe-executed transformations

<!-- The brief is the self-contained work order for one modernization
     story. Bar: a competent developer or a fresh session starts the
     story from THIS FILE ALONE. Fill every section; delete none. -->

## Goal & position

Harvests recipe-executed transformations and performs package rename from `org.springframework.samples.petclinic` to `com.demo`. This story follows S01's platform setup and prepares the codebase for layer-by-layer modernization. The package rename unblocks all downstream stories by establishing the correct namespace for the target Quarkus application.

## In scope

The exact legacy classes/files this story modernizes. For each, quote
the load-bearing legacy code (the lines being transformed — imports,
annotations, key methods), so the story never starts from a blank
read:

- `src/main/java/org/springframework/samples/petclinic/model/BaseEntity.java` — entity package
  ```java
  package org.springframework.samples.petclinic.model;
  
  import javax.persistence.GeneratedValue;
  import javax.persistence.GenerationType;
  import javax.persistence.Id;
  import javax.persistence.MappedSuperclass;
  
  @MappedSuperclass
  public class BaseEntity {
      @Id
      @GeneratedValue(strategy = GenerationType.IDENTITY)
      protected Integer id;
  ```

- `src/main/java/org/springframework/samples/petclinic/model/Owner.java` — domain entity with relationships
  ```java
  package org.springframework.samples.petclinic.model;
  
  import javax.persistence.*;
  import javax.validation.constraints.Digits;
  import javax.validation.constraints.NotEmpty;
  
  @Entity
  @Table(name = "owners")
  public class Owner extends Person {
      @Column(name = "address")
      @NotEmpty
      private String address;
  ```

- `src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaOwnerRepositoryImpl.java` — JPA repository
  ```java
  package org.springframework.samples.petclinic.repository.jpa;
  
  import org.springframework.samples.petclinic.model.Owner;
  import org.springframework.stereotype.Repository;
  
  @Repository
  @Transactional
  public class JpaOwnerRepositoryImpl implements OwnerRepository {
  ```

- `src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java` — REST controller
  ```java
  package org.springframework.samples.petclinic.rest;
  
  import org.springframework.web.bind.annotation.*;
  import org.springframework.validation.BindingResult;
  import org.springframework.http.ResponseEntity;
  
  @RestController
  @RequestMapping("/api/owners")
  public class OwnerRestController {
  ```

## Out of scope

All service layer implementations, configuration classes, and utility classes remain unchanged. This story only harvests package-level transformations from `migration/staging/` and applies the package rename to already-transformed files. Service and REST endpoint modernization happens in later stories (S04, S05, S06).

## Class roles & target contract (from architecture-profile §7)

Package rename only - no class role changes. All classes maintain their existing HARVEST/REDESIGN classification established in architecture-profile §7.

- `BaseEntity`, `Owner`, `Pet`, `Visit` and all model classes — HARVEST (preserve data contracts)
- Repository implementations — REDESIGN (modernized in S04)
- REST controllers — REDESIGN (modernized in S06)

## Decided target shapes

Package rename from `org.springframework.samples.petclinic` to `com.demo` across all Java files. Import statements transformed from `javax.*` to `jakarta.*` packages as recipe-executed.

**MAPPINGS transformations:**
- javax-to-jakarta-import-00001: All `javax.persistence.*`, `javax.validation.*` imports → `jakarta.*`
- removed-javaee-modules-00020: JEE module dependencies resolved
- springboot-annotations-to-quarkus-00000: `@SpringBootApplication` bootstrap removed
- springboot-annotations-to-quarkus-00002: Component scan annotations removed

## Contracts owned by this story

- **Findings**: javax-to-jakarta-import-00001, removed-javaee-modules-00020, springboot-annotations-to-quarkus-00000, springboot-annotations-to-quarkus-00002
- **seat-budget**: 1 — rename-only work from roadmap `kind × incident count`
- **Preserve**: N/A - no configuration surfaces in this scope
- **Behavioral pins**: N/A - package rename preserves all legacy behavior exactly
- **Forbidden**: N/A

## Done-criteria

Checkable, story-scoped:
- All files successfully renamed from `org.springframework.samples.petclinic` to `com.demo` package structure
- javax→jakarta import conversions complete and verified
- `@SpringBootApplication` and component scan annotations removed
- `mvn clean compile` succeeds with new package structure
- No references to old package structure remain in source files

# S03: Domain model and entity foundation

<!-- The brief is the self-contained work order for one modernization
     story. Bar: a competent developer or a fresh session starts the
     story from THIS FILE ALONE. Fill every section; delete none. -->

## Goal & position

Preserves the domain model entities with jakarta.persistence annotations while maintaining all validation constraints and data contracts. This story establishes the foundational layer for all downstream components, converting HARVEST classes from javax to jakarta packages. As a HARVEST story (architecture-profile §7), it preserves behavioral contracts exactly while modernizing the persistence layer.

## In scope

The exact legacy classes/files this story modernizes. For each, quote
the load-bearing legacy code (the lines being transformed — imports,
annotations, key methods), so the story never starts from a blank
read:

- `src/main/java/org/springframework/samples/petclinic/model/BaseEntity.java` — abstract entity base
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
      
      public boolean isNew() {
          return this.id == null;
      }
  ```

- `src/main/java/org/springframework/samples/petclinic/model/NamedEntity.java` — named entity abstraction
  ```java
  package org.springframework.samples.petclinic.model;
  
  import javax.persistence.Column;
  import javax.persistence.MappedSuperclass;
  import javax.validation.constraints.NotEmpty;
  
  @MappedSuperclass
  public class NamedEntity extends BaseEntity {
      @Column(name = "name")
      @NotEmpty
      private String name;
  ```

- `src/main/java/org/springframework/samples/petclinic/model/Person.java` — person entity
  ```java
  package org.springframework.samples.petclinic.model;
  
  import javax.persistence.Column;
  import javax.persistence.MappedSuperclass;
  import javax.validation.constraints.NotEmpty;
  
  @MappedSuperclass
  public class Person extends BaseEntity {
      @Column(name = "first_name")
      @NotEmpty
      protected String firstName;
      
      @Column(name = "last_name")
      @NotEmpty
      protected String lastName;
  ```

- `src/main/java/org/springframework/samples/petclinic/model/Owner.java` — business customer
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
      
      @Column(name = "city")
      @NotEmpty
      private String city;
      
      @Column(name = "telephone")
      @NotEmpty
      @Digits(fraction = 0, integer = 10)
      private String telephone;
  ```

- `src/main/java/org/springframework/samples/petclinic/model/PetType.java` — pet classification
  ```java
  package org.springframework.samples.petclinic.model;
  
  import javax.persistence.Entity;
  import javax.persistence.Table;
  
  @Entity
  @Table(name = "types")
  public class PetType extends NamedEntity {
  ```

- `src/main/java/org/springframework/samples/petclinic/model/Vet.java` — veterinarian
  ```java
  package org.springframework.samples.petclinic.model;
  
  import javax.persistence.*;
  
  @Entity
  @Table(name = "vets")
  public class Vet extends Person {
      @ManyToMany(fetch = FetchType.EAGER)
      @JoinTable(name = "vet_specialties", joinColumns = @JoinColumn(name = "vet_id"),
          inverseJoinColumns = @JoinColumn(name = "specialty_id"))
      private Set<Specialty> specialties;
  ```

## Out of scope

Repository implementations, service layer, and REST controllers remain unchanged. This story only modernizes the domain model entities and their JPA/validation annotations. All relationship mappings, cascade settings, and fetch strategies remain exactly as defined in legacy.

## Class roles & target contract (from architecture-profile §7)

All classes are HARVEST - they preserve their data contracts exactly while modernizing from javax to jakarta packages:

- `BaseEntity` — HARVEST: abstract ID carrier with `isNew()` semantics preserved
- `NamedEntity` — HARVEST: name field abstraction preserved
- `Person` — HARVEST: firstName/lastName fields preserved  
- `Owner` — HARVEST: address, city, telephone, pets collection preserved
- `PetType` — HARVEST: name classification preserved
- `Vet` — HARVEST: firstName/lastName, specialties relationships preserved
- `Pet`, `Visit`, `Specialty`, `Role`, `User` — HARVEST: all fields and relationships preserved

## Decided target shapes

Replace javax.persistence.* and javax.validation.* imports with jakarta.* equivalents while preserving all annotation attributes, validation constraints, and JPA metadata exactly:

**MAPPINGS transformations:**
- javax-to-jakarta-import-00001: `javax.persistence.*` → `jakarta.persistence.*`
- javax-to-jakarta-import-00001: `javax.validation.constraints.*` → `jakarta.validation.constraints.*`

## Contracts owned by this story

- **Findings**: N/A - HARVEST story, no mandatory findings
- **seat-budget**: 1 — rename-only work from roadmap `kind × incident count`
- **Preserve**: N/A - no configuration surfaces in this scope
- **Behavioral pins**: All domain entity validation constraints and JPA metadata must remain exactly as legacy
  - BaseEntity: `isNew()` returns true when `id == null`
  - Owner: @NotEmpty constraints on address, city, telephone; @Digits constraint on telephone
  - Person: @NotEmpty constraints on firstName, lastName
  - All entity relationships, cascade settings, and fetch strategies preserved
- **Forbidden**: N/A

## Done-criteria

Checkable, story-scoped:
- All entity classes compile with jakarta.persistence and jakarta.validation imports
- All validation constraints (@NotEmpty, @Digits) remain functionally equivalent
- All JPA annotations (@Entity, @Table, @Id, @GeneratedValue, etc.) work identically
- `mvn clean compile` succeeds with jakarta imports
- No behavioral changes to entity validations or persistence semantics

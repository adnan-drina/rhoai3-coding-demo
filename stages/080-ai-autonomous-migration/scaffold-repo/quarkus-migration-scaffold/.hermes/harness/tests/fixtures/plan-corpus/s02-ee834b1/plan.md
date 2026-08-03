# S02 Domain Models - Migration Plan

## Migration Strategy: HARVEST
All domain model classes are HARVEST classes that preserve their JPA mappings, validation annotations, and business logic exactly. Only the import statements change from `javax.persistence.*` to `jakarta.persistence.*`.

## Jakarta Migration (MAPPINGS.md)
**Recipe-executed in M1:** `javax-to-jakarta-import-00001`
- `javax.persistence.*` → `jakarta.persistence.*` 
- `javax.validation.*` → `jakarta.validation.*`
- All JPA annotations preserved exactly as-is
- All validation constraints maintained

## Conversion Order (dependency-order.md)
Following M1 dependency order for compilation:
1. **Package structure** - create target directory and package-info
2. **Base entity hierarchy** - BaseEntity, NamedEntity, Person
3. **Independent entities** - PetType, Specialty, Role, User
4. **Core entities with relationships** - Owner, Pet, Visit, Vet
5. **Characterization tests** - entity behavior verification

## Package Rename
**Full prefix replacement:**
`org.springframework.samples.petclinic.model` → `com.demo.model`

**Evidence:** migration.yaml specifies `targetPackage: com.demo`

## Target File Structure
```
src/main/java/com/demo/model/
├── package-info.java
├── BaseEntity.java
├── NamedEntity.java  
├── Person.java
├── Owner.java
├── Pet.java
├── Visit.java
├── Vet.java
├── PetType.java
├── Specialty.java
├── Role.java
└── User.java
```

## Class-by-Class Targets

### T-001: Package Structure and Documentation
**Class:** rewrite  
**Shape:** structure
- Create `src/main/java/com/demo/model/` directory
- Copy package-info.java with updated package declaration
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/package-info.java`
- **Target:** `src/main/java/com/demo/model/package-info.java`

### T-002: BaseEntity Migration
**Class:** rewrite  
**Shape:** modify
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/BaseEntity.java`
- **Target:** `src/main/java/com/demo/model/BaseEntity.java`
- **Changes:** 
  - Package: `org.springframework.samples.petclinic.model` → `com.demo.model`
  - Imports: `javax.persistence.*` → `jakarta.persistence.*`
- **Preserves:** @MappedSuperclass, @Id, @GeneratedValue, isNew() business logic

### T-003: NamedEntity Migration  
**Class:** rewrite
**Shape:** modify
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/NamedEntity.java`
- **Target:** `src/main/java/com/demo/model/NamedEntity.java`
- **Changes:** javax → jakarta imports, package rename
- **Preserves:** @MappedSuperclass, @Column, @NotEmpty, name field

### T-004: Person Migration
**Class:** rewrite
**Shape:** modify  
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Person.java`
- **Target:** `src/main/java/com/demo/model/Person.java`
- **Changes:** javax → jakarta imports, package rename
- **Preserves:** @MappedSuperclass, @Column, @NotEmpty, firstName/lastName fields

### T-005: PetType Migration (God Node)
**Class:** rewrite
**Shape:** modify
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/PetType.java`
- **Target:** `src/main/java/com/demo/model/PetType.java`
- **Changes:** javax → jakarta imports, package rename
- **Preserves:** @Entity, @Table, extends NamedEntity

### T-006: Specialty Migration
**Class:** rewrite
**Shape:** modify
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Specialty.java`
- **Target:** `src/main/java/com/demo/model/Specialty.java`
- **Changes:** javax → jakarta imports, package rename
- **Preserves:** @Entity, @Table, extends NamedEntity

### T-007: Role Migration
**Class:** rewrite
**Shape:** modify
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Role.java`
- **Target:** `src/main/java/com/demo/model/Role.java`
- **Changes:** javax → jakarta imports, package rename
- **Preserves:** @Entity, @Table, JPA mappings

### T-008: User Migration
**Class:** rewrite
**Shape:** modify
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/User.java`
- **Target:** `src/main/java/com/demo/model/User.java`
- **Changes:** javax → jakarta imports, package rename
- **Preserves:** @Entity, @Table, validation constraints

### T-009: Owner Migration
**Class:** rewrite
**Shape:** modify
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Owner.java`
- **Target:** `src/main/java/com/demo/model/Owner.java`
- **Changes:** javax → jakarta imports, package rename
- **Preserves:** @Entity, @Table, @OneToMany, @NotEmpty, @Digits validation, address/city/telephone fields, business logic in getPets()

### T-010: Pet Migration (God Node)
**Class:** rewrite
**Shape:** modify
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Pet.java`
- **Target:** `src/main/java/com/demo/model/Pet.java`
- **Changes:** javax → jakarta imports, package rename
- **Preserves:** @Entity, @Table, @ManyToOne, @OneToMany, relationships, visits collection

### T-011: Visit Migration (God Node)
**Class:** rewrite
**Shape:** modify
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Visit.java`
- **Target:** `src/main/java/com/demo/model/Visit.java`
- **Changes:** javax → jakarta imports, package rename
- **Preserves:** @Entity, @Table, @Column, @ManyToOne, date/description fields

### T-012: Vet Migration
**Class:** rewrite
**Shape:** modify
- **Source:** `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Vet.java`
- **Target:** `src/main/java/com/demo/model/Vet.java`
- **Changes:** javax → jakarta imports, package rename
- **Preserves:** @Entity, @Table, @ManyToMany relationships with specialties

### T-013: Entity Characterization Tests
**Class:** infer
**Shape:** verify
- **Purpose:** Verify JPA mappings, validation constraints, and business logic
- **Tests:**
  - Owner.getPets() returns sorted pets by name
  - Pet.getVisits() returns visits sorted by date descending
  - Owner phone validation: 10 digits only
  - isNew() behavior: returns true when id == null
  - Entity relationships: Owner-Pet, Pet-Visit, Vet-Specialty
- **God node focus:** PetType, Visit, Pet relationship integrity
- **Coverage:** All migrated entities validated

## Findings Resolution
- **javax-to-jakarta-import-00001:** All model classes migrated
- **All mandatory entity findings resolved**
- **No Spring Boot parent/BOM conversions needed** (already Quarkus in S01)

## Dependencies
- **Prerequisites:** S01 (platform foundation) - Quarkus dependencies established
- **Dependents:** S03 (repositories), S04 (services), S05 (REST controllers)

## Deploy Status
**deploy=false** - This story establishes the data foundation only. No REST endpoints or acceptance tests required.

## Quality Gate Targets
- All entities compile with jakarta imports (no javax imports remain)
- Entity relationship tests pass
- Validation constraints work correctly
- God node behavior preserved (PetType, Visit, Pet)
- JPA mapping validation successful
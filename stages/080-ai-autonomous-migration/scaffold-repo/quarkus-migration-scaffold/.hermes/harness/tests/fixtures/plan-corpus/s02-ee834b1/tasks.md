# S02 Domain Models - Task Plan

## Story Overview
Migrates core domain model from javax.persistence to jakarta.persistence, establishing the data foundation. All entities are HARVEST classes preserving JPA mappings, validation annotations, and business logic.

## Package Mapping
- Source: `org.springframework.samples.petclinic.model`
- Target: `com.demo.model`

## Task List

#### T-001: Create package structure and package-info
**Class**: rewrite  
**Shape**: structure  
**Scope**: Package preparation
- **Owns**: `src/main/java/com/demo/model/package-info.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/package-info.java`
- Create `src/main/java/com/demo/model/` directory structure
- Copy package-info.java with updated package declaration

#### T-002: Harvest BaseEntity with jakarta.persistence migration
**Class**: rewrite  
**Shape**: modify  
**Scope**: Base entity class
- **Owns**: `src/main/java/com/demo/model/BaseEntity.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/BaseEntity.java`
- **Changes**: javax.persistence → jakarta.persistence imports
- **Preserves**: @MappedSuperclass, @Id, @GeneratedValue, isNew() business logic

#### T-003: Harvest NamedEntity with jakarta.persistence migration
**Class**: rewrite  
**Shape**: modify  
**Scope**: Named entity class
- **Owns**: `src/main/java/com/demo/model/NamedEntity.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/NamedEntity.java`
- **Changes**: javax.persistence → jakarta.persistence imports
- **Preserves**: @MappedSuperclass, @Column, @NotEmpty validation, name field

#### T-004: Harvest Person with jakarta.persistence migration
**Class**: rewrite  
**Shape**: modify  
**Scope**: Person entity class
- **Owns**: `src/main/java/com/demo/model/Person.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Person.java`
- **Changes**: javax.persistence → jakarta.persistence imports
- **Preserves**: @MappedSuperclass, @Column, @NotEmpty validation, firstName/lastName fields

#### T-005: Harvest PetType (god node) with jakarta.persistence migration
**Class**: rewrite  
**Shape**: modify  
**Scope**: PetType entity class
- **Owns**: `src/main/java/com/demo/model/PetType.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/PetType.java`
- **Changes**: javax.persistence → jakarta.persistence imports
- **Preserves**: @Entity, @Table, JPA mappings

#### T-006: Harvest Specialty with jakarta.persistence migration
**Class**: rewrite  
**Shape**: modify  
**Scope**: Specialty entity class
- **Owns**: `src/main/java/com/demo/model/Specialty.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Specialty.java`
- **Changes**: javax.persistence → jakarta.persistence imports
- **Preserves**: @Entity, @Table, JPA mappings

#### T-007: Harvest Role with jakarta.persistence migration
**Class**: rewrite  
**Shape**: modify  
**Scope**: Role entity class
- **Owns**: `src/main/java/com/demo/model/Role.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Role.java`
- **Changes**: javax.persistence → jakarta.persistence imports
- **Preserves**: @Entity, @Table, JPA mappings

#### T-008: Harvest User with jakarta.persistence migration
**Class**: rewrite  
**Shape**: modify  
**Scope**: User entity class
- **Owns**: `src/main/java/com/demo/model/User.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/User.java`
- **Changes**: javax.persistence → jakarta.persistence imports
- **Preserves**: @Entity, @Table, JPA mappings, validation constraints

#### T-009: Harvest Owner with jakarta.persistence migration
**Class**: rewrite  
**Shape**: modify  
**Scope**: Owner entity class
- **Owns**: `src/main/java/com/demo/model/Owner.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Owner.java`
- **Changes**: javax.persistence → jakarta.persistence imports
- **Preserves**: @Entity, @Table, @Column, @NotEmpty, @Digits validation, address/city/telephone fields, @OneToMany relationship

#### T-010: Harvest Pet (god node) with jakarta.persistence migration
**Class**: rewrite  
**Shape**: modify  
**Scope**: Pet entity class
- **Owns**: `src/main/java/com/demo/model/Pet.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Pet.java`
- **Changes**: javax.persistence → jakarta.persistence imports
- **Preserves**: @Entity, @Table, @ManyToOne, @OneToMany relationships, visits collection

#### T-011: Harvest Visit (god node) with jakarta.persistence migration
**Class**: rewrite  
**Shape**: modify  
**Scope**: Visit entity class
- **Owns**: `src/main/java/com/demo/model/Visit.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Visit.java`
- **Changes**: javax.persistence → jakarta.persistence imports
- **Preserves**: @Entity, @Table, @Column, @ManyToOne relationships, date/description fields

#### T-012: Harvest Vet with jakarta.persistence migration
**Class**: rewrite  
**Shape**: modify  
**Scope**: Vet entity class
- **Owns**: `src/main/java/com/demo/model/Vet.java`
- **Source**: `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Vet.java`
- **Changes**: javax.persistence → jakarta.persistence imports
- **Preserves**: @Entity, @Table, @ManyToMany relationships with specialties

#### T-013: Characterize entity relationships and validation
**Class**: infer  
**Shape**: verify  
**Target design**: 
- **Files**: `src/main/java/com/demo/model/Owner.java`, `src/main/java/com/demo/model/Pet.java`, `src/main/java/com/demo/model/Visit.java`
- **Test files**: `src/test/java/com/demo/model/OwnerTest.java`, `src/test/java/com/demo/model/PetTest.java`, `src/test/java/com/demo/model/VisitTest.java`
- **Design**: Verify JPA mappings, validation constraints, and business logic preservation
- **God node focus**: PetType, Visit, Pet relationship integrity
- **Tests**: Owner.getPets() sorted by name, Pet.getVisits() sorted by date descending, Owner phone validation (10 digits), isNew() behavior
**Acceptance**: Entity relationship tests pass, validation constraints verified

## Findings Coverage
- **javax-to-jakarta-import-00001**: All model classes migrated from javax to jakarta imports
- All mandatory findings for entity classes resolved
- God nodes (PetType, Visit, Pet) characterized with relationship tests

## Story Dependencies
- **Prerequisites**: S01 (platform foundation)
- **Dependents**: S03 (repositories), S04 (services), S05 (REST controllers)

## Deploy Status
**deploy=false** - No REST endpoints or acceptance tests required for this story

## Legacy UI Surface
**Waived**: Domain model classes have no direct UI surface. UI presentation handled by DTOs and REST controllers in later stories (S05).

## Preserved Integration Mapping
- **petclinic.security.enable**: Deferred to S05 (REST controllers + security configuration)
- **server.servlet.context-path**: Deferred to S05 (REST endpoint paths)
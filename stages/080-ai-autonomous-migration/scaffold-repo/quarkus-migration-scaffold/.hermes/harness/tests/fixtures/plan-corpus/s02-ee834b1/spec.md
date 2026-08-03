# S02 Domain Models - Specification

## Story Scope
Migrates core domain model from javax.persistence to jakarta.persistence, establishing the data foundation for all higher layers. All model classes are HARVEST classes that preserve their JPA mappings, validation annotations, and business logic exactly.

## In-Scope Classes
**Target package:** `com.demo.model`

### Base Entity Hierarchy
- `BaseEntity.java` — Base entity with id and isNew() method
- `NamedEntity.java` — Named entity with name field and @NotEmpty validation  
- `Person.java` — Person with firstName/lastName fields and validation

### Core Domain Entities
- `Owner.java` — Pet owner with address, city, telephone fields and @Digits/@NotEmpty validation
- `Pet.java` — Pet entity with relationships to Owner, PetType, and Visit
- `Visit.java` — Visit entity linking Pet and Vet with date/description
- `Vet.java` — Veterinarian with many-to-many relationship to Specialty
- `PetType.java` — Pet type enumeration (god node, high fan-in)
- `Specialty.java` — Veterinarian specialty classification

### Supporting Entities  
- `Role.java` — User role for security
- `User.java` — User entity with credentials

### Package Documentation
- `package-info.java` — Package-level documentation

## Legacy API Evidence

### BaseEntity.java
```java
package org.springframework.samples.petclinic.model;

import javax.persistence.*;  // → jakarta.persistence.*
import com.fasterxml.jackson.annotation.JsonIgnore;

@MappedSuperclass
public class BaseEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    protected Integer id;
    
    @JsonIgnore
    public boolean isNew() {
        return this.id == null;
    }
}
```
**Key behaviors:**
- ID generation strategy: IDENTITY
- isNew() returns true when id == null
- JSON serialization excludes isNew() property

### Owner.java  
```java
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
    
    @OneToMany(cascade = CascadeType.ALL, mappedBy = "owner", fetch = FetchType.EAGER)
    private Set<Pet> pets;
}
```
**Key behaviors:**
- Phone validation: exactly 10 digits
- Owner search sorted by lastName, firstName
- Pet collection sorted by name with PropertyComparator
- Bidirectional relationship with Pet (owner ← pet)

### Pet.java
```java
@Entity
@Table(name = "pets")  
public class Pet extends NamedEntity {
    @ManyToOne
    @JoinColumn(name = "type_id")
    private PetType type;
    
    @ManyToOne
    @JoinColumn(name = "owner_id")
    private Owner owner;
    
    @OneToMany(mappedBy = "pet", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    private Set<Visit> visits = new LinkedHashSet<>();
}
```
**Key behaviors:**
- Visits collection sorted by date descending
- LinkedHashSet preserves insertion order
- Relationships to Owner, PetType, Visit

### Visit.java
```java
@Entity
@Table(name = "visits")
public class Visit extends BaseEntity {
    @Column(name = "visit_date")
    private LocalDate date;
    
    @Column(name = "description")
    private String description;
    
    @ManyToOne
    private Pet pet;
    
    @ManyToOne
    private Vet vet;
}
```
**Key behaviors:**
- Date-based sorting for visits
- Links to Pet and Vet entities

## JPA Relationship Mapping
- **Owner → Pet:** @OneToMany (EAGER fetch)
- **Pet → Owner:** @ManyToOne  
- **Pet → PetType:** @ManyToOne
- **Pet → Visit:** @OneToMany (LAZY fetch)
- **Visit → Pet:** @ManyToOne
- **Visit → Vet:** @ManyToOne
- **Vet → Specialty:** @ManyToMany

## Validation Constraints
- @NotEmpty: name, firstName, lastName, address, city, telephone
- @Digits: telephone (10 digits exactly)
- Field-level annotations preserved exactly

## God Nodes (High Fan-in)
**Characterization required for:**
- `PetType` (fan-in 18) — referenced by Pet and Visit queries
- `Visit` (fan-in 18) — central to business operations  
- `Pet` (fan-in 17) — core entity connecting Owner, Visit, PetType

## Package Rename
**Full prefix replacement:** `org.springframework.samples.petclinic.model` → `com.demo.model`

## Legacy File Paths (Evidence)
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/BaseEntity.java`
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/NamedEntity.java`
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Person.java`
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Owner.java`
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Pet.java`
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Visit.java`
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Vet.java`
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Specialty.java`
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/PetType.java`
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Role.java`
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/User.java`
- `/projects/legacy/src/main/java/org/springframework/samples/petclinic/model/package-info.java`
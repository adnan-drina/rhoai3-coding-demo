# S02: Domain model foundation

## Goal & position

This story modernizes the domain layer by migrating all entities and DTOs from javax to jakarta packages. This is the first code-level story and follows the platform foundation work in S01. The domain entities are HARVEST classes per architecture-profile §7, meaning they preserve their semantic behavior with only package-level changes. All 11 domain entities plus generated DTOs are covered by the single `removed-javaee-modules-00020` finding.

## In scope

### BaseEntity.java - Abstract ID carrier with isNew() semantics
```java
package org.springframework.samples.petclinic.model;

import javax.persistence.GeneratedValue;
import javax.persistence.GenerationType;
import javax.persistence.Id;
import javax.persistence.MappedSuperclass;

import com.fasterxml.jackson.annotation.JsonIgnore;

/**
 * Simple JavaBean domain object with an id property. Used as a base class for objects needing this property.
 *
 * @author Ken Krebs
 * @author Juergen Hoeller
 */
@MappedSuperclass
public class BaseEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    protected Integer id;

    public Integer getId() {
        return id;
    }

    public void setId(Integer id) {
        this.id = id;
    }
    @JsonIgnore
    public boolean isNew() {
        return this.id == null;
    }

}
```

### NamedEntity.java - Abstract name field abstraction
```java
package org.springframework.samples.petclinic.model;

import javax.persistence.Column;
import javax.persistence.MappedSuperclass;

import javax.validation.constraints.NotEmpty;

/**
 * Simple JavaBean domain object adds a name property to <code>BaseEntity</code>. Used as a base class for objects
 * needing these properties.
 *
 * @author Ken Krebs
 * @author Juergen Hoeller
 */
@MappedSuperclass
public class NamedEntity extends BaseEntity {

    @Column(name = "name")
    @NotEmpty
    private String name;

    public String getName() {
        return this.name;
    }

    public void setName(String name) {
        this.name = name;
    }

    @Override
    public String toString() {
        return this.getName();
    }

}
```

### Person.java - Abstract firstName/lastName fields
```java
package org.springframework.samples.petclinic.model;

import javax.persistence.Column;
import javax.persistence.MappedSuperclass;

import javax.validation.constraints.NotEmpty;

/**
 * Simple JavaBean domain object representing an person.
 *
 * @author Ken Krebs
 */
@MappedSuperclass
public class Person extends BaseEntity {

    @Column(name = "first_name")
    @NotEmpty
    protected String firstName;

    @Column(name = "last_name")
    @NotEmpty
    protected String lastName;

    public String getFirstName() {
        return this.firstName;
    }

    public void setFirstName(String firstName) {
        this.firstName = firstName;
    }

    public String getLastName() {
        return this.lastName;
    }

    public void setLastName(String lastName) {
        this.lastName = lastName;
    }


}
```

### Owner.java - Business customer with pets collection
```java
package org.springframework.samples.petclinic.model;

import org.springframework.beans.support.MutableSortDefinition;
import org.springframework.beans.support.PropertyComparator;
import org.springframework.core.style.ToStringCreator;

import javax.persistence.*;
import javax.validation.constraints.Digits;
import javax.validation.constraints.NotEmpty;
import java.util.*;

/**
 * Simple JavaBean domain object representing an owner.
 *
 * @author Ken Krebs
 * @author Juergen Hoeller
 * @author Sam Brannen
 * @author Michael Isvy
 */
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

    // ... getters/setters and business methods ...
    public String getAddress() {
        return this.address;
    }

    public void setAddress(String address) {
        this.address = address;
    }

    public String getCity() {
        return this.city;
    }

    public void setCity(String city) {
        this.city = city;
    }

    public String getTelephone() {
        return this.telephone;
    }

    public void setTelephone(String telephone) {
        this.telephone = telephone;
    }

    protected Set<Pet> getPetsInternal() {
        if (this.pets == null) {
            this.pets = new HashSet<>();
        }
        return this.pets;
    }

    protected void setPetsInternal(Set<Pet> pets) {
        this.pets = pets;
    }

    public List<Pet> getPets() {
        List<Pet> sortedPets = new ArrayList<>(getPetsInternal());
        PropertyComparator.sort(sortedPets, new MutableSortDefinition("name", true, true));
        return Collections.unmodifiableList(sortedPets);
    }

    public void setPets(List<Pet> pets) {
        this.pets = new HashSet<>(pets);
    }

    public void addPet(Pet pet) {
        getPetsInternal().add(pet);
        pet.setOwner(this);
    }

    /**
     * Return the Pet with the given name, or null if none found for this Owner.
     *
     * @param name to test
     * @return true if pet name is already in use
     */
    public Pet getPet(String name) {
        return getPet(name, false);
    }

    /**
     * Return the Pet with the given name, or null if none found for this Owner.
     *
     * @param name to test
     * @return true if pet name is already in use
     */
    public Pet getPet(String name, boolean ignoreNew) {
        name = name.toLowerCase();
        for (Pet pet : getPetsInternal()) {
            if (!ignoreNew || !pet.isNew()) {
                String compName = pet.getName();
                compName = compName.toLowerCase();
                if (compName.equals(name)) {
                    return pet;
                }
            }
        }
        return null;
    }

    @Override
    public String toString() {
        return new ToStringCreator(this)

            .append("id", this.getId())
            .append("new", this.isNew())
            .append("lastName", this.getLastName())
            .append("firstName", this.getFirstName())
            .append("address", this.address)
            .append("city", this.city)
            .append("telephone", this.telephone)
            .toString();
    }
}
```

### Pet.java - Animal under care with visits
```java
package org.springframework.samples.petclinic.model;

import org.springframework.beans.support.MutableSortDefinition;
import org.springframework.beans.support.PropertyComparator;
import org.springframework.format.annotation.DateTimeFormat;

import javax.persistence.*;
import java.time.LocalDate;
import java.util.*;

/**
 * Simple business object representing a pet.
 *
 * @author Ken Krebs
 * @author Juergen Hoeller
 * @author Sam Brannen
 */
@Entity
@Table(name = "pets")
public class Pet extends NamedEntity {

    @Column(name = "birth_date", columnDefinition = "DATE")
    private LocalDate birthDate;

    @ManyToOne
    @JoinColumn(name = "type_id")
    private PetType type;

    @ManyToOne
    @JoinColumn(name = "owner_id")
    private Owner owner;

    @OneToMany(cascade = CascadeType.ALL, mappedBy = "pet", fetch = FetchType.EAGER)
    private Set<Visit> visits;

    public LocalDate getBirthDate() {
        return this.birthDate;
    }

    public void setBirthDate(LocalDate birthDate) {
        this.birthDate = birthDate;
    }

    public PetType getType() {
        return this.type;
    }

    public void setType(PetType type) {
        this.type = type;
    }

    public Owner getOwner() {
        return this.owner;
    }

    public void setOwner(Owner owner) {
        this.owner = owner;
    }

    protected Set<Visit> getVisitsInternal() {
        if (this.visits == null) {
            this.visits = new HashSet<>();
        }
        return this.visits;
    }

    protected void setVisitsInternal(Set<Visit> visits) {
        this.visits = visits;
    }

    public List<Visit> getVisits() {
        List<Visit> sortedVisits = new ArrayList<>(getVisitsInternal());
        PropertyComparator.sort(sortedVisits, new MutableSortDefinition("date", false, false));
        return Collections.unmodifiableList(sortedVisits);
    }

    public void setVisits(List<Visit> visits) {
        this.visits = new HashSet<>(visits);
    }

    public void addVisit(Visit visit) {
        getVisitsInternal().add(visit);
        visit.setPet(this);
    }

}
```

### PetType.java - Animal classification
```java
package org.springframework.samples.petclinic.model;

import javax.persistence.Entity;
import javax.persistence.Table;

/**
 * @author Juergen Hoeller
 *         Can be Cat, Dog, Hamster...
 */
@Entity
@Table(name = "types")
public class PetType extends NamedEntity {

}
```

### Other entities (Specialty, Visit, Vet, Role, User) - Similar jakarta package imports

### DTOs - Generated OpenAPI contracts with validation annotations
- OwnerDto, PetDto, VisitDto, PetTypeDto, SpecialtyDto, VetDto, RoleDto, UserDto
- All contain jakarta imports for validation annotations

## Out of scope

All repository implementations, service layer, REST controllers, and mapper implementations. The domain entities must remain functionally identical - only package migrations (javax→jakarta) are allowed.

## Class roles & target contract (from architecture-profile §7)

- **BaseEntity, NamedEntity, Person** — HARVEST - abstract base classes with no behavioral changes, package migration only
- **Owner, Pet, Visit, PetType, Specialty, Vet, Role, User** — HARVEST - domain entities with package migration only, maintain all JPA annotations and validation constraints
- **DTOs** — HARVEST - data transfer objects with package migration only, maintain validation annotations and OpenAPI contracts

## Decided target shapes

**Entity migration (HARVEST contract):**
- All `javax.persistence.*` imports → `jakarta.persistence.*`
- All `javax.validation.*` imports → `jakarta.validation.*`
- All `javax.transaction.*` imports → `jakarta.transaction.*`
- No changes to entity relationships, validation rules, or business logic
- All JPA annotations and column definitions preserved exactly

**DTO migration:**
- Validation annotations migrate to jakarta packages
- Generated OpenAPI contracts remain identical
- Serialization/deserialization behavior preserved

## Contracts owned by this story

- **seat-budget**: `7`

- **seat-budget**: `3`

- **seat-budget**: `3`
- **Findings**: `removed-javaee-modules-00020` (HARVEST - javax→jakarta package migration only)
- **Preserve**: All domain entity semantics and behavior
- **Behavioral pins**: 
  - Owner#1 has exactly 1 pet with type "cat" (tested by AbstractClinicServiceTests.java:67-71)
  - Pet#7 named "Samantha" belongs to owner "Jean" (tested by AbstractClinicServiceTests.java:109-113)
  - All @NotEmpty and @Digits validation constraints must remain active
  - All JPA relationships (OneToMany, ManyToOne, etc.) must be preserved

## Done-criteria

- All 11 domain entities compile successfully with jakarta.persistence
- All DTOs compile successfully with jakarta.validation  
- All javax.* imports in domain layer successfully migrated to jakarta.*
- Entity relationships and validation constraints remain functionally identical
- OpenAPI generation produces identical contract specifications
- Integration with existing repository and service layers maintained
- The single removed-javaee-modules-00020 finding no longer appears in re-analysis

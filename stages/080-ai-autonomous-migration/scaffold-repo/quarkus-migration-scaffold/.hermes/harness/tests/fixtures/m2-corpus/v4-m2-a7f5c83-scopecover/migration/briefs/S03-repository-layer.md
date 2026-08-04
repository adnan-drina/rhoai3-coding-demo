# S03: Repository layer

## Goal & position

This story converts the repository layer from Spring DI to Quarkus CDI, implementing proper transactional management and thread-safe bean lifecycle. It handles three persistence strategies (JDBC, JPA, Spring Data JPA) and converts them to consistent CDI patterns. The repositories are REDESIGN classes per architecture-profile §7 requiring @ApplicationScoped CDI beans with constructor injection and @Transactional method annotations.

## In scope

### JpaOwnerRepositoryImpl.java - JPA repository with @PersistenceContext injection
```java
package org.springframework.samples.petclinic.repository.jpa;

import java.util.Collection;

import javax.persistence.EntityManager;
import javax.persistence.PersistenceContext;
import javax.persistence.Query;

import org.springframework.context.annotation.Profile;
import org.springframework.dao.DataAccessException;
import org.springframework.orm.hibernate5.support.OpenSessionInViewFilter;
import org.springframework.samples.petclinic.model.Owner;
import org.springframework.samples.petclinic.repository.OwnerRepository;
import org.springframework.stereotype.Repository;

/**
 * JPA implementation of the {@link OwnerRepository} interface.
 *
 * @author Mike Keith
 * @author Rod Johnson
 * @author Sam Brannen
 * @author Michael Isvy
 * @author Vitaliy Fedoriv
 */
@Repository
@Profile("jpa")
public class JpaOwnerRepositoryImpl implements OwnerRepository {

    @PersistenceContext
    private EntityManager em;

    /**
     * Important: in the current version of this method, we load Owners with all their Pets and Visits while
     * we do not need Visits at all and we only need one property from the Pet objects (the 'name' property).
     * There are some ways to improve it such as:
     * - creating a Ligtweight class (example here: https://community.jboss.org/wiki/LightweightClass)
     * - Turning on lazy-loading and using {@link OpenSessionInViewFilter}
     */
    @SuppressWarnings("unchecked")
    public Collection<Owner> findByLastName(String lastName) {
        // using 'join fetch' because a single query should load both owners and pets
        // using 'left join fetch' because it might happen that an owner does not have pets yet
        Query query = this.em.createQuery("SELECT DISTINCT owner FROM Owner owner left join fetch owner.pets WHERE owner.lastName LIKE :lastName");
        query.setParameter("lastName", lastName + "%");
        return query.getResultList();
    }

    @Override
    public Owner findById(int id) {
        // using 'join fetch' because a single query should load both owners and pets
        // using 'left join fetch' because it might happen that an owner does not have pets yet
        Query query = this.em.createQuery("SELECT owner FROM Owner owner left join fetch owner.pets WHERE owner.id =:id");
        query.setParameter("id", id);
        return (Owner) query.getSingleResult();
    }

    @Override
    public void save(Owner owner) {
        if (owner.getId() == null) {
            this.em.persist(owner);
        } else {
            this.em.merge(owner);
        }

    }

	@SuppressWarnings("unchecked")
	@Override
	public Collection<Owner> findAll() throws DataAccessException {
		Query query = this.em.createQuery("SELECT owner FROM Owner owner");
        return query.getResultList();
	}

	@Override
	public void delete(Owner owner) throws DataAccessException {
		this.em.remove(this.em.contains(owner) ? owner : this.em.merge(owner));
	}

}
```

### JdbcOwnerRepositoryImpl.java - JDBC repository with JdbcTemplate
```java
package org.springframework.samples.petclinic.repository.jdbc;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

import javax.sql.DataSource;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.namedparam.BeanPropertySqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.samples.petclinic.model.Owner;
import org.springframework.samples.petclinic.model.Pet;
import org.springframework.samples.petclinic.repository.OwnerRepository;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

/**
 * JPA implementation of the {@link OwnerRepository} interface.
 *
 * @author Mike Keith
 * @author Rod Johnson
 * @author Sam Brannen
 * @author Michael Isvy
 * @author Vitaliy Fedoriv
 */
@Repository
public class JdbcOwnerRepositoryImpl implements OwnerRepository {

    private JdbcTemplate jdbcTemplate;
    private NamedParameterJdbcTemplate namedParameterJdbcTemplate;

    @Autowired
    public JdbcOwnerRepositoryImpl(DataSource dataSource) {
        this.jdbcTemplate = new JdbcTemplate(dataSource);
        this.namedParameterJdbcTemplate = new NamedParameterJdbcTemplate(dataSource);
    }

    // ... methods implementing OwnerRepository with JDBC logic
}
```

### SpringDataPetRepositoryImpl.java - Spring Data JPA repository
```java
package org.springframework.samples.petclinic.repository.springdatajpa;

import java.util.List;

import javax.transaction.Transactional;

import org.springframework.samples.petclinic.model.Pet;
import org.springframework.samples.petclinic.repository.PetRepository;
import org.springframework.stereotype.Repository;

import javax.persistence.EntityManager;
import javax.persistence.PersistenceContext;

/**
 * Spring Data JPA implementation of the {@link PetRepository} interface.
 *
 * @author Vitaliy Fedoriv
 */
@Repository
@Transactional
public class SpringDataPetRepositoryImpl implements PetRepository {

    @PersistenceContext
    private EntityManager em;

    @Override
    public Pet findById(Integer id) {
        return em.find(Pet.class, id);
    }

    @Override
    public List<Pet> findAll() {
        return em.createQuery("SELECT pet FROM Pet pet").getResultList();
    }

    @Override
    public void save(Pet entity) {
        if (entity.getId() == null) {
            em.persist(entity);
        } else {
            em.merge(entity);
        }
    }

    @Override
    public void delete(Pet entity) {
        em.remove(em.contains(entity) ? entity : em.merge(entity));
    }

    @Override
    public void deleteById(Integer id) {
        Pet pet = findById(id);
        if (pet != null) {
            delete(pet);
        }
    }

}
```

## Out of scope

Domain entities, services, REST controllers, and mappers. Repository interfaces remain unchanged - only implementations are modified. All repository implementations must remain functionally identical, only the DI and transaction patterns change.

## Class roles & target contract (from architecture-profile §7)

- **Repository implementations** — REDESIGN - Convert to @ApplicationScoped CDI beans with constructor injection and @Transactional method annotations

## Decided target shapes

**Repository CDI conversion:**
- `@Repository` → `@ApplicationScoped` CDI bean
- `@PersistenceContext` → Constructor injection with `@Inject`
- Field injection → Constructor injection (thread-safe)
- `@Profile` annotations → Removed (profiles handled via Quarkus configuration)
- Add `@Transactional` method annotations where missing
- Remove Spring-specific imports (except in method signatures required for compatibility)

**Transaction management:**
- All mutating methods annotated with `@Transactional`
- Read-only methods annotated with `@Transactional(readOnly = true)`
- Transaction propagation and isolation preserved from Spring behavior

## Contracts owned by this story

- **seat-budget**: `25`

- **seat-budget**: `25`

- **seat-budget**: `25`
- **Findings**: `springboot-di-to-quarkus-00003`, `transaction-to-quarkus-00003` (REDESIGN - CDI conversion + transactional management)
- **Preserve**: All repository interfaces and business logic behavior
- **Behavioral pins**: 
  - All existing JPA queries and JDBC SQL must execute identically
  - Transaction boundaries must match Spring @Transactional behavior
  - Exception propagation and error handling must remain unchanged

## Done-criteria

- All repository implementations converted to @ApplicationScoped CDI beans
- Constructor injection implemented for all dependencies (@Inject EntityManager, DataSource)
- @Transactional annotations applied to all mutating and appropriate read-only methods
- Repository implementations compile successfully with Jakarta persistence
- All three persistence strategies (JDBC, JPA, Spring Data) function identically
- Integration with services layer maintained through CDI injection
- The two repository findings no longer appear in re-analysis

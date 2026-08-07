# S04: Service layer modernization

## Goal & position

This story modernizes the service layer by converting Spring @Service beans to Quarkus CDI @ApplicationScoped beans. Per architecture-profile §7, the ClinicService facade is removed with its business logic subsumed by individual resource endpoints. The service implementations become thread-safe CDI beans with constructor injection and proper transactional management.

## In scope

### ClinicServiceImpl.java - Main service implementation with @Service and @Autowired
```java
package org.springframework.samples.petclinic.service;

import java.util.Collection;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.orm.ObjectRetrievalFailureException;
import org.springframework.samples.petclinic.model.Owner;
import org.springframework.samples.petclinic.model.Pet;
import org.springframework.samples.petclinic.model.PetType;
import org.springframework.samples.petclinic.model.Specialty;
import org.springframework.samples.petclinic.model.Vet;
import org.springframework.samples.petclinic.model.Visit;
import org.springframework.samples.petclinic.repository.OwnerRepository;
import org.springframework.samples.petclinic.repository.PetRepository;
import org.springframework.samples.petclinic.repository.PetTypeRepository;
import org.springframework.samples.petclinic.repository.SpecialtyRepository;
import org.springframework.samples.petclinic.repository.VetRepository;
import org.springframework.samples.petclinic.repository.VisitRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Mostly used as a facade for all Petclinic controllers
 * Also a placeholder for @Transactional and @Cacheable annotations
 *
 * @author Michael Isvy
 * @author Vitaliy Fedoriv
 */
@Service

public class ClinicServiceImpl implements ClinicService {

    private PetRepository petRepository;
    private VetRepository vetRepository;
    private OwnerRepository ownerRepository;
    private VisitRepository visitRepository;
    private SpecialtyRepository specialtyRepository;
	private PetTypeRepository petTypeRepository;

    @Autowired
     public ClinicServiceImpl(
      		 PetRepository petRepository,
 			 VetRepository vetRepository,
 		 OwnerRepository ownerRepository,
 		 VisitRepository visitRepository,
 		 SpecialtyRepository specialtyRepository,
		 PetTypeRepository petTypeRepository) {
        this.petRepository = petRepository;
        this.vetRepository = vetRepository;
        this.ownerRepository = ownerRepository;
        this.visitRepository = visitRepository;
        this.specialtyRepository = specialtyRepository; 
		this.petTypeRepository = petTypeRepository;
    }

	@Override
	@Transactional(readOnly = true)
	public Collection<Pet> findAllPets() throws DataAccessException {
		return petRepository.findAll();
	}

	@Override
	@Transactional
	public void deletePet(Pet pet) throws DataAccessException {
		petRepository.delete(pet);
	}

	@Override
	@Transactional(readOnly = true)
	public Visit findVisitById(int visitId) throws DataAccessException {
		Visit visit = null;
		try {
			visit = visitRepository.findById(visitId);
		} catch (ObjectRetrievalFailureException|EmptyResultDataAccessException e) {
		// just ignore not found exceptions for Jdbc/Jpa realization
			return null;
		}
		return visit;
	}

	@Override
	@Transactional(readOnly = true)
	public Collection<PetType> findAllPetTypes() throws DataAccessException {
		return petTypeRepository.findAll();
	}

	@Override
	@Transactional(readOnly = true)
	public Owner findOwnerById(int id) throws DataAccessException {
		Owner owner = null;
		try {
			owner = ownerRepository.findById(id);
		} catch (ObjectRetrievalFailureException e) {
		// just ignore not found exceptions for Jdbc/Jpa realization
			owner = null;
		}
		return owner;
	}

	@Override
	@Transactional(readOnly = true)
	public Collection<Owner> findOwnerByLastName(String lastName) throws DataAccessException {

		return ownerRepository.findByLastName(lastName);

	}

	@Override
	@Transactional(readOnly = true)
	public Collection<Owner> findAllOwners() throws DataAccessException {
		return ownerRepository.findAll();
	}

	@Override
	@Transactional
	public void saveOwner(Owner owner) throws DataAccessException {
		ownerRepository.save(owner);
	}

	@Override
	@Transactional
	public void deleteOwner(Owner owner) throws DataAccessException {
		ownerRepository.delete(owner);
	}

	@Override
	@Transactional(readOnly = true)
	public Vet findVetById(int id) throws DataAccessException {
		Vet vet = null;
		try {
			vet = vetRepository.findById(id);
		} catch (ObjectRetrievalFailureException e) {
		// just ignore not found exceptions for Jdbc/Jpa realization
			vet = null;
		}
		return vet;
	}

	@Override
	@Transactional(readOnly = true)
	public Collection<Vet> findAllVets() throws DataAccessException {
		return vetRepository.findAll();
	}

	@Override
	@Transactional(readOnly = true)
	public Collection<Specialty> findAllSpecialties() throws DataAccessException {
		return specialtyRepository.findAll();
	}

	@Override
	@Transactional(readOnly = true)
	public Pet findPetById(int id) throws DataAccessException {
		Pet pet = null;
		try {
			pet = petRepository.findById(id);
		} catch (ObjectRetrievalFailureException e) {
		// just ignore not found exceptions for Jdbc/Jpa realization
			pet = null;
		}
		return pet;
	}

	@Override
	@Transactional
	public void savePet(Pet pet) throws DataAccessException {
		petRepository.save(pet);
	}

	@Override
	@Transactional
	public void deletePet(Pet pet) throws DataAccessException {
		petRepository.delete(pet);
	}

	@Override
	@Transactional(readOnly = true)
	public Collection<Visit> findVisitsByPetId(int petId) throws DataAccessException {
		return visitRepository.findByPetId(petId);
	}

	@Override
	@Transactional(readOnly = true)
	public Visit findVisitById(int visitId) throws DataAccessException {
		Visit visit = null;
		try {
			visit = visitRepository.findById(visitId);
		} catch (ObjectRetrievalFailureException|EmptyResultDataAccessException e) {
		// just ignore not found exceptions for Jdbc/Jpa realization
			return null;
		}
		return visit;
	}

	@Override
	@Transactional(readOnly = true)
	public Collection<Visit> findAllVisits() throws DataAccessException {
		return visitRepository.findAll();
	}

	@Override
	@Transactional
	public void saveVisit(Visit visit) throws DataAccessException {
		visitRepository.save(visit);
	}

	@Override
	@Transactional
	public void deleteVisit(Visit visit) throws DataAccessException {
		visitRepository.delete(visit);
	}

}
```

### UserServiceImpl.java - User management service
```java
package org.springframework.samples.petclinic.service;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DataAccessException;
import org.springframework.samples.petclinic.model.Role;
import org.springframework.samples.petclinic.model.User;
import org.springframework.samples.petclinic.repository.UserRepository;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * @author Marcelino Llano
 */
@Service
public class UserServiceImpl implements UserService, UserDetailsService {

    private UserRepository userRepository;

    @Autowired
    public UserServiceImpl(UserRepository userRepository) {
        this.userRepository = userRepository;
    }

	@Override
	@Transactional
	public void saveUser(User user) throws DataAccessException {
		user.setEnabled(true);
		userRepository.save(user);
	}

	@Override
	@Transactional(readOnly = true)
	public User findUserById(int id) throws DataAccessException {
		return userRepository.findById(id);
	}

	@Override
	@Transactional(readOnly = true)
	public User findUserByUsername(String username) throws DataAccessException {
		return userRepository.findByUsername(username);
	}

	@Override
	@Transactional(readOnly = true)
	public Collection<User> findAllUsers() throws DataAccessException {
		return userRepository.findAll();
	}

	@Override
	@Transactional
	public void deleteUser(User user) throws DataAccessException {
		userRepository.delete(user);
	}

	@Override
	@Transactional(readOnly = true)
	public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
		User user = findUserByUsername(username);
		List<GrantedAuthority> authorities = new ArrayList<GrantedAuthority>();
		for (Role role : user.getRoles()) {
			authorities.add(new SimpleGrantedAuthority(role.getName()));
		}
		return new org.springframework.security.core.userdetails.User(user.getUsername(), user.getPassword(),
				user.isEnabled(), true, true, true, authorities);
	}

}
```

## Out of scope

Domain entities, repositories, REST controllers, and mappers. Service interfaces remain unchanged - only implementations are modified. The ClinicService facade is removed per architecture-profile §7.

## Class roles & target contract (from architecture-profile §7)

- **ClinicServiceImpl** — REDESIGN - Converted to @ApplicationScoped CDI bean with constructor injection; facade methods distributed to resource endpoints
- **UserServiceImpl** — REDESIGN - Converted to @ApplicationScoped CDI bean with constructor injection

## Decided target shapes

**Service CDI conversion:**
- `@Service` → `@ApplicationScoped` CDI bean
- `@Autowired` constructor → Constructor injection with `@Inject`
- Field injection → Constructor injection (thread-safe)
- Remove `@Cacheable` annotations (cache strategy deferred)
- Remove Spring Security imports (security subsumed by Quarkus)

**Facade removal (architecture-profile §7.2):**
- ClinicService facade removed, business logic moved to individual REST resource endpoints
- UserService authentication logic subsumed by Quarkus Security
- @Transactional annotations preserved on service methods

## Contracts owned by this story

- **seat-budget**: `5`

- **seat-budget**: `5`

- **seat-budget**: `5`
- **Findings**: `springboot-annotations-to-quarkus-00002`, `springboot-di-to-quarkus-00002`, `springboot-webmvc-to-quarkus-00000` (REDESIGN - CDI conversion + Spring MVC to JAX-RS)
- **Preserve**: All service method signatures and business logic behavior
- **Behavioral pins**: 
  - All existing @Transactional boundaries preserved
  - Service method behavior unchanged
  - Exception propagation patterns maintained

## Done-criteria

- ClinicService facade removed with business logic distributed to resource endpoints
- ClinicServiceImpl and UserServiceImpl converted to @ApplicationScoped CDI beans
- Constructor injection implemented for all repository dependencies
- @Transactional annotations preserved on all methods
- Service implementations compile successfully with Quarkus CDI
- Integration with repository and REST layers maintained through CDI
- All service methods function identically to the original Spring implementation

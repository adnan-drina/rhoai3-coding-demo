package org.springframework.samples.petclinic.repository;

import java.util.Collection;
import java.util.List;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Typed;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;

import io.quarkus.arc.profile.IfBuildProfile;
import org.springframework.samples.petclinic.model.Owner;

/**
 * NEGATIVE CONTROL (v17 t_eca28a3c shape): every member is a throwing placeholder. It
 * compiles, packages and has the approved CDI exposure; it must be rejected by behaviour.
 */
@ApplicationScoped
@Typed(OwnerRepositoryImpl.class)
@IfBuildProfile("spring-data-jpa")
public class OwnerRepositoryImpl implements OwnerRepository {

    @Override
    public Collection<Owner> findByLastName(String lastName) {
        throw new UnsupportedOperationException("not implemented");
    }

    @Override
    public Owner findById(int id) {
        throw new UnsupportedOperationException("not implemented");
    }

    @Override
    public void save(Owner owner) {
        throw new UnsupportedOperationException("not implemented");
    }

    @Override
    public Collection<Owner> findAll() {
        throw new UnsupportedOperationException("not implemented");
    }

    @Override
    public void delete(Owner owner) {
        throw new UnsupportedOperationException("not implemented");
    }
}

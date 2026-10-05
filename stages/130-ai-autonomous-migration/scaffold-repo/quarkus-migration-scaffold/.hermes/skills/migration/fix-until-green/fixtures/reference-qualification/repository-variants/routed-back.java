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
 * NEGATIVE CONTROL (INTERVENTIONS I-6, v29): the fragment implementation delegates to the
 * Spring Data repository that EXTENDS its own fragment. Quarkus Spring Data routes every
 * OwnerRepository member of SpringDataOwnerRepository back to this class, so each call
 * recurses until StackOverflowError. Written from the I-6 description; v29's file itself
 * was not preserved locally.
 */
@ApplicationScoped
@Typed(OwnerRepositoryImpl.class)
@IfBuildProfile("spring-data-jpa")
public class OwnerRepositoryImpl implements OwnerRepository {

    @jakarta.inject.Inject
    org.springframework.samples.petclinic.repository.springdatajpa.SpringDataOwnerRepository springData;

    @Override
    public Collection<Owner> findByLastName(String lastName) {
        return springData.findByLastName(lastName);
    }

    @Override
    public Owner findById(int id) {
        return springData.findById(id);
    }

    @Override
    public void save(Owner owner) {
        springData.save(owner);
    }

    @Override
    public Collection<Owner> findAll() {
        return springData.findAll();
    }

    @Override
    public void delete(Owner owner) {
        springData.delete(owner);
    }
}

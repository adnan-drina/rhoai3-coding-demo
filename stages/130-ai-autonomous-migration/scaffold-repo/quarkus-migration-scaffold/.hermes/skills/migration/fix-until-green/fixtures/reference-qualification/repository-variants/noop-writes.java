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
 * NEGATIVE CONTROL: the reference port's reads with no-op writes ("reads pass, writes do
 * nothing"). Every write must be rejected by a committed read-back.
 */
@ApplicationScoped
@Typed(OwnerRepositoryImpl.class)
@IfBuildProfile("spring-data-jpa")
public class OwnerRepositoryImpl implements OwnerRepository {

    @PersistenceContext
    EntityManager em;

    @Override
    public Collection<Owner> findByLastName(String lastName) {
        return em.createQuery(
                "SELECT DISTINCT owner FROM Owner owner left join fetch owner.pets WHERE owner.lastName LIKE :lastName",
                Owner.class)
            .setParameter("lastName", lastName + "%")
            .getResultList();
    }

    @Override
    public Owner findById(int id) {
        List<Owner> found = em.createQuery(
                "SELECT owner FROM Owner owner left join fetch owner.pets WHERE owner.id =:id", Owner.class)
            .setParameter("id", id)
            .getResultList();
        return found.isEmpty() ? null : found.get(0);
    }

    @Override
    public void save(Owner owner) {
        // a no-op: reads pass, writes do nothing
    }

    @Override
    public Collection<Owner> findAll() {
        return em.createQuery("select owner from Owner owner", Owner.class).getResultList();
    }

    @Override
    public void delete(Owner owner) {
        // a no-op: reads pass, writes do nothing
    }
}

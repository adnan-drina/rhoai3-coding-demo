package org.springframework.samples.petclinic.repository;

import java.util.Collection;
import java.util.List;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;

import io.quarkus.arc.profile.IfBuildProfile;
import org.springframework.samples.petclinic.model.Owner;

/**
 * NEGATIVE CONTROL (v16 t_1118e877 shape): the reference port WITHOUT @Typed, so the class
 * is also a bean of type OwnerRepository beside the generated Spring Data repository
 * (duplicate beans). The platform must refuse augmentation (AmbiguousResolutionException).
 */
@ApplicationScoped
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
        if (owner.isNew()) {
            em.persist(owner);
        } else {
            em.merge(owner);
        }
    }

    @Override
    public Collection<Owner> findAll() {
        return em.createQuery("select owner from Owner owner", Owner.class).getResultList();
    }

    @Override
    public void delete(Owner owner) {
        if (owner.isNew()) {
            return;
        }
        Owner existing = em.find(Owner.class, owner.getId());
        if (existing == null) {
            return;
        }
        em.remove(em.contains(owner) ? owner : em.merge(owner));
    }
}

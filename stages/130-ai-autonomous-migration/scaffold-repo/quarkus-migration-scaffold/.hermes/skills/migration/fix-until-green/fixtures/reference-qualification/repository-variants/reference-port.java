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
 * M-3 reference port of the SELECTED source behaviour (catalog repository_behaviour):
 * the frozen source serves OwnerRepository through SpringDataOwnerRepository under the
 * decided build profile spring-data-jpa. Per member, in Spring Data's precedence:
 *   findByLastName, findById -- the repository's @Query text, verbatim, over entity
 *     property paths (":lastName%" is Spring Data's LIKE shorthand: the bound value
 *     gets the trailing %); a single-entity @Query answers null when nothing matches;
 *   save, findAll, delete -- SimpleJpaRepository's CRUD semantics (crud_defaults).
 * Not the behaviour source: JpaOwnerRepositoryImpl (@Profile("jpa"), inactive).
 * CDI: @ApplicationScoped @Typed(OwnerRepositoryImpl.class) (spring-data-fragment-impl).
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

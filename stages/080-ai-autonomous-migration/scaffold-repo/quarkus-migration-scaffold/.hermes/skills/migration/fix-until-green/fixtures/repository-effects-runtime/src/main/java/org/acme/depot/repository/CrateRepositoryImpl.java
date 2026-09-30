package org.acme.depot.repository;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Typed;
import jakarta.inject.Inject;
import jakarta.persistence.EntityManager;
import java.util.Collection;
import org.acme.depot.model.Crate;

// the fragment delegate the generated Spring Data repository calls, in the
// approved CDI shape: its only bean type is its concrete class
@ApplicationScoped
@Typed(CrateRepositoryImpl.class)
public class CrateRepositoryImpl implements CrateRepository {
    @Inject
    EntityManager em;
    // DELEGATE-FIELD
    // END-DELEGATE-FIELD

    public Collection<Crate> findAll() {
        // READ-ALL
        return em.createQuery("select distinct c from Crate c order by c.id", Crate.class).getResultList();
        // END-READ-ALL
    }

    public Crate findById(int id) {
        // READ-BY-ID
        return em.find(Crate.class, id);
        // END-READ-BY-ID
    }

    public void save(Crate crate) {
        // WRITE-SAVE
        if (crate.id == null) {
            em.persist(crate);
        } else {
            em.merge(crate);
        }
        // END-WRITE-SAVE
    }

    public void delete(Crate crate) {
        // WRITE-DELETE
        em.remove(em.contains(crate) ? crate : em.merge(crate));
        // END-WRITE-DELETE
    }
}

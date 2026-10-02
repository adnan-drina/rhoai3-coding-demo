package org.acme.depot.repository;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.persistence.EntityManager;
import org.acme.depot.model.Kind;

// a plain bean (no Spring Data fragment): the kind delete with its dependents
@ApplicationScoped
public class KindRepository {
    @Inject
    EntityManager em;

    public Kind findById(int id) {
        return em.find(Kind.class, id);
    }

    public void save(Kind kind) {
        em.persist(kind);
    }

    public void delete(Kind kind) {
        // KIND-DELETE: bulk statements only, no entity loading -- the stamps, the
        // pallets, then the kind
        em.createQuery("DELETE FROM Stamp s WHERE s.pallet.id IN (SELECT p.id FROM Pallet p WHERE p.kind.id = :id)")
                .setParameter("id", kind.id).executeUpdate();
        em.createQuery("DELETE FROM Pallet p WHERE p.kind.id = :id").setParameter("id", kind.id).executeUpdate();
        em.createQuery("DELETE FROM Kind k WHERE k.id = :id").setParameter("id", kind.id).executeUpdate();
        // END-KIND-DELETE
    }
}

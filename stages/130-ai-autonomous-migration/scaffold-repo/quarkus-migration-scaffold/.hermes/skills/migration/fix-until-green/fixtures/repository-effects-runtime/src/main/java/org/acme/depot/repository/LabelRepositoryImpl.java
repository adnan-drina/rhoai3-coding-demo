package org.acme.depot.repository;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Typed;
import jakarta.inject.Inject;
import jakarta.persistence.EntityManager;
import org.acme.depot.model.Label;

@ApplicationScoped
@Typed(LabelRepositoryImpl.class)
public class LabelRepositoryImpl implements LabelRepository {
    @Inject
    EntityManager em;

    public Label findById(int id) {
        return em.find(Label.class, id);
    }

    public void save(Label label) {
        em.persist(label);
    }

    public void delete(Label label) {
        // DELETE-ORDER: the dependents (join rows) first, then the entity -- the
        // committed effect of the source override, in an order Hibernate 6 can flush
        em.createNativeQuery("delete from pallet_labels where label_id = ?1").setParameter(1, label.id).executeUpdate();
        em.remove(em.contains(label) ? label : em.merge(label));
        // END-DELETE-ORDER
    }
}

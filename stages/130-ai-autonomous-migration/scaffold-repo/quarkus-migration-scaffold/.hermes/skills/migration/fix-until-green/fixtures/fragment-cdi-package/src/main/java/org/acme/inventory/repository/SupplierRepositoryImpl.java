package org.acme.inventory.repository;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.persistence.EntityManager;
import java.util.Collection;
import org.acme.inventory.model.Supplier;

@ApplicationScoped
public class SupplierRepositoryImpl implements SupplierRepository {
    @Inject
    EntityManager em;

    public Collection<Supplier> findAll() {
        return em.createQuery("from Supplier", Supplier.class).getResultList();
    }

    public Supplier findById(int id) {
        return em.find(Supplier.class, id);
    }

    public void save(Supplier value) {
        em.persist(value);
    }

    public int countNamed(String name) {
        return em.createQuery("from Supplier v where v.name = :n", Supplier.class).setParameter("n", name).getResultList().size();
    }
}

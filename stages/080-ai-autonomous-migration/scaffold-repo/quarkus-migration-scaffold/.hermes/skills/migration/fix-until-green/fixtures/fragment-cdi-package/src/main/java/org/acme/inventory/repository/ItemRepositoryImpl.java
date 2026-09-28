package org.acme.inventory.repository;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import jakarta.persistence.EntityManager;
import java.util.Collection;
import org.acme.inventory.model.Item;

@ApplicationScoped
public class ItemRepositoryImpl implements ItemRepository {
    @Inject
    EntityManager em;

    public Collection<Item> findAll() {
        return em.createQuery("from Item", Item.class).getResultList();
    }

    public Item findById(int id) {
        return em.find(Item.class, id);
    }

    public void save(Item value) {
        em.persist(value);
    }

    public int countNamed(String name) {
        return em.createQuery("from Item v where v.name = :n", Item.class).setParameter("n", name).getResultList().size();
    }
}

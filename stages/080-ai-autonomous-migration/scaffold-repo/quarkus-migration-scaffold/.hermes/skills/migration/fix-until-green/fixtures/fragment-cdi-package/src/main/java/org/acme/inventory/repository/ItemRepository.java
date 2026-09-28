package org.acme.inventory.repository;

import java.util.Collection;
import org.acme.inventory.model.Item;

public interface ItemRepository {
    Collection<Item> findAll();

    Item findById(int id);

    void save(Item value);

    int countNamed(String name);
}

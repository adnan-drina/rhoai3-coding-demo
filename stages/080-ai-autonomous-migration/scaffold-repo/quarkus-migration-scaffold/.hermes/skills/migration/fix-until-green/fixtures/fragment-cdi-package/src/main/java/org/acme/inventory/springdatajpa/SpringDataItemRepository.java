package org.acme.inventory.springdatajpa;

import org.acme.inventory.model.Item;
import org.acme.inventory.repository.ItemRepository;
import org.springframework.data.repository.Repository;

public interface SpringDataItemRepository extends ItemRepository, Repository<Item, Integer> {
}

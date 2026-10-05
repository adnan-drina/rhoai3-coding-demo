package org.acme.inventory.service;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.acme.inventory.repository.SupplierRepository;
import org.acme.inventory.repository.ItemRepository;

@ApplicationScoped
public class StockService {
    @Inject
    ItemRepository items;

    @Inject
    SupplierRepository suppliers;

    public int count(String name) {
        return items.countNamed(name) + suppliers.countNamed(name);
    }
}

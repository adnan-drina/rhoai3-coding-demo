package org.acme.inventory.repository;

import java.util.Collection;
import org.acme.inventory.model.Supplier;

public interface SupplierRepository {
    Collection<Supplier> findAll();

    Supplier findById(int id);

    void save(Supplier value);

    int countNamed(String name);
}

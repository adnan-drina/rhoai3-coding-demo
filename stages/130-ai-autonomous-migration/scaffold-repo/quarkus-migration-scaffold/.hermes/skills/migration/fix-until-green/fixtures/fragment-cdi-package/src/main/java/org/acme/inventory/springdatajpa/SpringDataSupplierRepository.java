package org.acme.inventory.springdatajpa;

import org.acme.inventory.model.Supplier;
import org.acme.inventory.repository.SupplierRepository;
import org.springframework.data.repository.Repository;

public interface SpringDataSupplierRepository extends SupplierRepository, Repository<Supplier, Integer> {
}

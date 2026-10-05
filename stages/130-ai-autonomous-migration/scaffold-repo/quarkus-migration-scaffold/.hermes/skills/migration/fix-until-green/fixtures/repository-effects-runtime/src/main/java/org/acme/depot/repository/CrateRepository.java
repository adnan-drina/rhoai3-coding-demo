package org.acme.depot.repository;

import java.util.Collection;
import org.acme.depot.model.Crate;

public interface CrateRepository {
    Collection<Crate> findAll();

    Crate findById(int id);

    void save(Crate crate);

    void delete(Crate crate);
}

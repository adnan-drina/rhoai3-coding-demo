package org.acme.depot.springdatajpa;

import org.acme.depot.model.Crate;
import org.acme.depot.repository.CrateRepository;
import org.springframework.data.repository.Repository;

public interface SpringDataCrateRepository extends CrateRepository, Repository<Crate, Integer> {
}

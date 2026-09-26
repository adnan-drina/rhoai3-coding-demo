package org.acme.depot.springdatajpa;

import org.acme.depot.model.Label;
import org.acme.depot.repository.LabelRepository;
import org.springframework.data.repository.Repository;

public interface SpringDataLabelRepository extends LabelRepository, Repository<Label, Integer> {
}

package org.acme.depot.repository;

import org.acme.depot.model.Label;

public interface LabelRepository {
    Label findById(int id);

    void save(Label label);

    void delete(Label label);
}

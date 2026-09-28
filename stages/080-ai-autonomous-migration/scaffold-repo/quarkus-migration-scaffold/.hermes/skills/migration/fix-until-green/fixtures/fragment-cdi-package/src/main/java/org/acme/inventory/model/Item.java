package org.acme.inventory.model;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity
public class Item {
    @Id
    public Integer id;
    public String name;
}

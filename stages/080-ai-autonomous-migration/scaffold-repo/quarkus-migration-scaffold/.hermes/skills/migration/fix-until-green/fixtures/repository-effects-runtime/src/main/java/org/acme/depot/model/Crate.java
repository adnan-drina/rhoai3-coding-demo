package org.acme.depot.model;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import java.util.ArrayList;
import java.util.List;

@Entity
public class Crate {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    public Integer id;
    public String name;
    @OneToMany(mappedBy = "crate", cascade = CascadeType.ALL, orphanRemoval = true, fetch = FetchType.EAGER)
    public List<Pallet> pallets = new ArrayList<>();
}

package org.acme.depot.model;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;

// a grandchild under a pallet (no collection on the pallet side)
@Entity
public class Stamp {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    public Integer id;
    public String name;
    @JsonIgnore
    @ManyToOne
    @JoinColumn(name = "pallet_id", nullable = false)
    public Pallet pallet;
}

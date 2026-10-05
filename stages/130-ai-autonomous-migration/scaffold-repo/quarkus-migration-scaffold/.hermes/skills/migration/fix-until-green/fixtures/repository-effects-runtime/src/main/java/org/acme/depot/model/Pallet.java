package org.acme.depot.model;

import com.fasterxml.jackson.annotation.JsonIgnore;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.JoinTable;
import jakarta.persistence.ManyToMany;
import jakarta.persistence.ManyToOne;
import java.util.HashSet;
import java.util.Set;

@Entity
public class Pallet {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    public Integer id;
    public String name;
    @JsonIgnore
    @ManyToOne
    @JoinColumn(name = "crate_id", nullable = false)
    public Crate crate;
    @ManyToMany(fetch = FetchType.EAGER)
    @JoinTable(name = "pallet_labels", joinColumns = @JoinColumn(name = "pallet_id"),
               inverseJoinColumns = @JoinColumn(name = "label_id"))
    public Set<Label> labels = new HashSet<>();
    @ManyToOne
    @JoinColumn(name = "kind_id")
    public Kind kind;
}

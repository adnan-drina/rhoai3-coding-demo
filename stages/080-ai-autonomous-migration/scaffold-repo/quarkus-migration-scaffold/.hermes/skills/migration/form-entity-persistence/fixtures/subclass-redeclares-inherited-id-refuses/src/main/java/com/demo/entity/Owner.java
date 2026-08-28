package com.demo.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity
public class Owner extends Person {
    @Id
    private Integer ownerId;
}

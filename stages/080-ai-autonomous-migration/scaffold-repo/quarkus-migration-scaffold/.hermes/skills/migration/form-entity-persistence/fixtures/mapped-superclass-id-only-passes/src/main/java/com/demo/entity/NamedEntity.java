package com.demo.entity;

import jakarta.persistence.MappedSuperclass;

@MappedSuperclass
public abstract class NamedEntity extends BaseEntity {
    protected String name;
}

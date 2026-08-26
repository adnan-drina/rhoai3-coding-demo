package com.demo.entity;

import jakarta.persistence.MappedSuperclass;

@MappedSuperclass
public abstract class Person extends BaseEntity {
    protected String firstName;
}

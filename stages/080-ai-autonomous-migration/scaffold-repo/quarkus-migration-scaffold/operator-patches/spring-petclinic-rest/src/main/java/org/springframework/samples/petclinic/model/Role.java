package org.springframework.samples.petclinic.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import com.fasterxml.jackson.annotation.JsonIgnore;

import io.quarkus.security.jpa.RolesValue;

/**
 * ADR-014: the role side of the identity store. {@code name} holds the value the
 * source's {@code select username,role from roles where username=?} returned and
 * the value {@code Roles} names in every {@code @PreAuthorize} expression, so it
 * is the value quarkus-security-jpa must read. Nothing else changes.
 */
@Entity
@Table(name = "roles" ,uniqueConstraints = @UniqueConstraint(columnNames = {"username", "role"}))
public class Role extends BaseEntity {

    @ManyToOne
    @JoinColumn(name = "username")
    @JsonIgnore
    private User user;

    @Column( name = "role")
    @RolesValue
    private String name;

    public User getUser() {
        return user;
    }

    public void setUser(User user) {
        this.user = user;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }
}

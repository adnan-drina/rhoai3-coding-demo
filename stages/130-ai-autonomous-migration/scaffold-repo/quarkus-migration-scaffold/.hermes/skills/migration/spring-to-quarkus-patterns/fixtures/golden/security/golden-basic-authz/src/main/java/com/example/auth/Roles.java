package com.example.auth;

/** Compile-time role constants — never inject these into @RolesAllowed. */
public final class Roles {
    public static final String ADMIN = "admin";
    public static final String USER = "user";

    private Roles() {}
}

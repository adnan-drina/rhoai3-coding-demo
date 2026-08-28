package com.example.auth;

import jakarta.annotation.security.RolesAllowed;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.MediaType;

@Path("/api/admin")
public class AdminResource {

    @GET
    @RolesAllowed(Roles.ADMIN)
    @Produces(MediaType.TEXT_PLAIN)
    public String adminOnly() {
        return "ok";
    }
}

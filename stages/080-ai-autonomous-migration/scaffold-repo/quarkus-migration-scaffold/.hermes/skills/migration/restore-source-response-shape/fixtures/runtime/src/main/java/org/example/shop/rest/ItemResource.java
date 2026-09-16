package org.example.shop.rest;

import jakarta.ws.rs.Consumes;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.PUT;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.PathParam;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.core.Response;

/** Mirrors the fixture source's ItemController: a permissive @CrossOrigin policy. */
@Path("/api/items")
public class ItemResource {

    @GET
    @Produces("application/json")
    public String list() {
        return "[]";
    }

    @POST
    @Consumes("application/json")
    @Produces("application/json")
    public Response create(String body) {
        return Response.status(201).entity("{}").build();
    }

    @PUT
    @Path("{itemId}")
    @Consumes("application/json")
    public Response update(@PathParam("itemId") int itemId, String body) {
        return Response.noContent().build();
    }

    @GET
    @Path("{any}/name/{name}")
    @Produces("application/json")
    public String byName(@PathParam("any") String any, @PathParam("name") String name) {
        return "[]";
    }
}

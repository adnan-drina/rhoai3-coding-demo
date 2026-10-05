package org.example.shop.rest;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.POST;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;

/** Mirrors the fixture source's NarrowController: a RESTRICTIVE @CrossOrigin policy. */
@Path("/api/narrow")
public class NarrowResource {

    @GET
    @Produces("text/plain")
    public String read() {
        return "narrow";
    }

    @POST
    @Produces("text/plain")
    public String write() {
        return "written";
    }
}

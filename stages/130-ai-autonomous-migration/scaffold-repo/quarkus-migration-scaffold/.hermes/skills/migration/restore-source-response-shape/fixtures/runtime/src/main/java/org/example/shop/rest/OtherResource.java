package org.example.shop.rest;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;

/** Mirrors the fixture source's OtherController: no @CrossOrigin at all. */
@Path("/api/other")
public class OtherResource {

    @GET
    @Produces("text/plain")
    public String read() {
        return "other";
    }
}

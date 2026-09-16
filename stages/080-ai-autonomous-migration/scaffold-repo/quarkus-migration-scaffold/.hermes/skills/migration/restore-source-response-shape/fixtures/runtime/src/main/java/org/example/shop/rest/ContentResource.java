package org.example.shop.rest;

import jakarta.ws.rs.GET;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.core.Response;

/** Responses whose Content-Type the media-type adapter must, or must not, change. */
@Path("/api/content")
public class ContentResource {

    private static Response typed(String type) {
        return Response.ok("{\"k\":\"v\"}".getBytes(java.nio.charset.StandardCharsets.UTF_8))
                       .header("Content-Type", type).build();
    }

    @GET
    @Path("json-utf8")
    public Response jsonUtf8() {
        return typed("application/json;charset=UTF-8");
    }

    @GET
    @Path("json-latin")
    public Response jsonLatin() {
        return typed("application/json;charset=ISO-8859-1");
    }

    @GET
    @Path("json-extra")
    public Response jsonExtra() {
        return typed("application/json;profile=x;charset=UTF-8");
    }

    /** What the application sees of Origin (a same-origin request keeps it). */
    @GET
    @Path("origin")
    @jakarta.ws.rs.Produces("text/plain")
    public String origin(@jakarta.ws.rs.HeaderParam("Origin") String origin) {
        return String.valueOf(origin);
    }

    @GET
    @Path("text-utf8")
    public Response textUtf8() {
        return typed("text/plain;charset=UTF-8");
    }
}

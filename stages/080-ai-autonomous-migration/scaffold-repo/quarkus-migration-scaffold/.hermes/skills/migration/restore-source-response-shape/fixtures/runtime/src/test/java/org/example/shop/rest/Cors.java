package org.example.shop.rest;

import static io.restassured.RestAssured.given;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.util.List;

import io.restassured.RestAssured;
import io.restassured.response.Response;
import io.restassured.specification.RequestSpecification;

/** Shared request shapes and assertions. */
final class Cors {

    static final String CLIENT = "http://client.example";
    static final String ALLOWED = "http://allowed.example";
    static final String EVIL = "http://evil.example";
    static final List<String> CORS_HEADERS = List.of(
        "Access-Control-Allow-Origin", "Access-Control-Allow-Methods", "Access-Control-Allow-Headers",
        "Access-Control-Allow-Credentials", "Access-Control-Expose-Headers", "Access-Control-Max-Age");

    private Cors() {
    }

    static RequestSpecification req() {
        return given().urlEncodingEnabled(false);
    }

    static Response preflight(String path, String origin, String method, String headers) {
        RequestSpecification r = req().header("Origin", origin).header("Access-Control-Request-Method", method);
        if (headers != null) {
            r = r.header("Access-Control-Request-Headers", headers);
        }
        return r.options(path);
    }

    static String sameOrigin() {
        return "http://localhost:" + RestAssured.port;
    }

    static void noCors(Response r) {
        for (String h : CORS_HEADERS) {
            assertNull(r.getHeader(h), h + " must be absent: " + r.getHeaders());
        }
    }

    static void header(Response r, String name, String value) {
        assertEquals(value, r.getHeader(name), name + " in " + r.getHeaders());
    }
}

package org.example.shop.rest;

import static org.example.shop.rest.Cors.CLIENT;
import static org.example.shop.rest.Cors.header;
import static org.example.shop.rest.Cors.preflight;
import static org.example.shop.rest.Cors.req;
import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Map;

import org.junit.jupiter.api.Test;

import io.quarkus.test.junit.QuarkusTest;
import io.quarkus.test.junit.QuarkusTestProfile;
import io.quarkus.test.junit.TestProfile;
import io.restassured.response.Response;

/**
 * CONTROL: the same configuration with neither adapter registered. The platform's own
 * early preflight answer has a different shape (echoed origin, its whole method list,
 * an explicit credentials header), which is what makes the adapter tests evidence that
 * the adapter reached that answer. Also: the CORS rows alone never touch Content-Type.
 */
@QuarkusTest
@TestProfile(PlatformOnlyTest.PlatformOnly.class)
class PlatformOnlyTest {

    public static class PlatformOnly implements QuarkusTestProfile {
        @Override
        public Map<String, String> getConfigOverrides() {
            return Map.of("rhoai3.source-cors.rule-count", "0", "rhoai3.source-media-type.media-types", "");
        }
    }

    @Test
    void thePlatformsOwnPreflightShapeIsNotTheSources() {
        Response r = preflight("/api/items", CLIENT, "POST", "Content-Type");
        assertEquals(200, r.statusCode());
        header(r, "Access-Control-Allow-Origin", CLIENT);
        header(r, "Access-Control-Allow-Credentials", "false");
        assertEquals(true, r.getHeader("Access-Control-Allow-Methods").contains(","), r.getHeaders().toString());
    }

    @Test
    void thePlatformAloneRejectsASameOriginMethodOutsideItsList() {
        // the stricter-than-source case ADR-020 rules a repair obligation; the adapter removes it
        Response r = req().header("Origin", Cors.sameOrigin()).delete("/api/items");
        assertEquals(403, r.statusCode());
    }

    @Test
    void withoutTheMediaTypeAdapterTheParameterStays() {
        Response r = req().header("Origin", CLIENT).get("/api/content/json-utf8");
        assertEquals("application/json;charset=UTF-8", r.getHeader("Content-Type"));
    }
}

package org.example.shop.rest;

import static org.example.shop.rest.Cors.CLIENT;
import static org.example.shop.rest.Cors.EVIL;
import static org.example.shop.rest.Cors.header;
import static org.example.shop.rest.Cors.noCors;
import static org.example.shop.rest.Cors.preflight;
import static org.example.shop.rest.Cors.req;
import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Map;

import org.junit.jupiter.api.Test;

import io.quarkus.test.junit.QuarkusTest;
import io.quarkus.test.junit.QuarkusTestProfile;
import io.quarkus.test.junit.TestProfile;
import io.restassured.response.Response;

/** The source's security switch ON: its security ran before its CORS processing. */
@QuarkusTest
@TestProfile(EnabledModeTest.Enabled.class)
class EnabledModeTest {

    public static class Enabled implements QuarkusTestProfile {
        @Override
        public Map<String, String> getConfigOverrides() {
            return Map.of("fixture.security.enable", "true");
        }
    }

    static final String USER = "fixture-user";
    static final String PASSWORD = "fixture-pass";

    @Test
    void anonymousPreflightIsRejectedByAuthenticationWithoutCorsHeaders() {
        Response r = preflight("/api/items", CLIENT, "POST", "Content-Type");
        assertEquals(401, r.statusCode());
        noCors(r);
        // the challenge is the real mechanism's, exactly as for an anonymous request without Origin (ADR-020)
        assertEquals(req().get("/api/items").getHeader("WWW-Authenticate"), r.getHeader("WWW-Authenticate"));
        org.junit.jupiter.api.Assertions.assertNotNull(r.getHeader("WWW-Authenticate"));
    }

    @Test
    void authenticatedPreflightIsAnsweredInTheSourceShape() {
        Response r = req().auth().preemptive().basic(USER, PASSWORD)
            .header("Origin", CLIENT).header("Access-Control-Request-Method", "POST")
            .header("Access-Control-Request-Headers", "Content-Type").options("/api/items");
        assertEquals(200, r.statusCode());
        header(r, "Access-Control-Allow-Origin", "*");
        header(r, "Access-Control-Allow-Methods", "POST");
        header(r, "Access-Control-Allow-Headers", "Content-Type");
        header(r, "Access-Control-Max-Age", "1800");
        header(r, "Access-Control-Allow-Credentials", null);
    }

    @Test
    void anonymousActualRequestIsA401WithoutCorsHeaders() {
        Response r = req().header("Origin", CLIENT).get("/api/items");
        assertEquals(401, r.statusCode());
        noCors(r);
    }

    @Test
    void invalidCredentialsAreA401WithoutCorsHeaders() {
        Response r = req().auth().preemptive().basic(USER, "wrong").header("Origin", CLIENT).get("/api/items");
        assertEquals(401, r.statusCode());
        noCors(r);
    }

    @Test
    void authenticatedActualRequestCarriesTheSourceHeaders() {
        Response r = req().auth().preemptive().basic(USER, PASSWORD).header("Origin", CLIENT).get("/api/items");
        assertEquals(200, r.statusCode());
        header(r, "Access-Control-Allow-Origin", "*");
        header(r, "Access-Control-Expose-Headers", "errors, content-type");
        header(r, "Access-Control-Allow-Credentials", null);
    }

    @Test
    void refusedOriginIsDecidedAfterAuthentication() {
        Response anonymous = req().header("Origin", EVIL).get("/api/narrow");
        assertEquals(401, anonymous.statusCode());
        noCors(anonymous);
        Response authenticated = req().auth().preemptive().basic(USER, PASSWORD).header("Origin", EVIL).get("/api/narrow");
        assertEquals(403, authenticated.statusCode());
        assertEquals("Invalid CORS request", authenticated.asString());
        noCors(authenticated);
        Response pre = req().auth().preemptive().basic(USER, PASSWORD)
            .header("Origin", EVIL).header("Access-Control-Request-Method", "GET").options("/api/narrow");
        assertEquals(403, pre.statusCode());
        noCors(pre);
    }

    @Test
    void sameOriginUnmappedMethodIsRoutedInBothIdentities() {
        Response anon = req().header("Origin", Cors.sameOrigin()).delete("/api/items");
        assertEquals(req().delete("/api/items").statusCode(), anon.statusCode());
        assertEquals(401, anon.statusCode());
        noCors(anon);
        Response auth = req().auth().preemptive().basic(USER, PASSWORD).header("Origin", Cors.sameOrigin()).delete("/api/items");
        assertEquals(req().auth().preemptive().basic(USER, PASSWORD).delete("/api/items").statusCode(), auth.statusCode());
        assertEquals(405, auth.statusCode());
        noCors(auth);
    }

    @Test
    void noOriginAndSameOriginAreUntouched() {
        Response r = req().auth().preemptive().basic(USER, PASSWORD).get("/api/items");
        assertEquals(200, r.statusCode());
        noCors(r);
        Response s = req().auth().preemptive().basic(USER, PASSWORD).header("Origin", Cors.sameOrigin()).get("/api/items");
        assertEquals(200, s.statusCode());
        noCors(s);
        assertEquals(401, req().get("/api/items").statusCode());
    }
}

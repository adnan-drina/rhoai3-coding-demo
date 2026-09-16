package org.example.shop.rest;

import static org.example.shop.rest.Cors.ALLOWED;
import static org.example.shop.rest.Cors.CLIENT;
import static org.example.shop.rest.Cors.EVIL;
import static org.example.shop.rest.Cors.header;
import static org.example.shop.rest.Cors.noCors;
import static org.example.shop.rest.Cors.preflight;
import static org.example.shop.rest.Cors.req;
import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

import io.quarkus.test.junit.QuarkusTest;
import io.restassured.response.Response;

/** The source's security switch OFF: the permissive and the restrictive policy, on the real HTTP layer. */
@QuarkusTest
class DisabledModeTest {

    @Test
    void preflightIsAnsweredInTheSourceShape() {
        // the platform answers this before any endpoint; the source's shape proves the adapter reached it
        Response r = preflight("/api/items", CLIENT, "POST", "Content-Type");
        assertEquals(200, r.statusCode());
        header(r, "Access-Control-Allow-Origin", "*");
        header(r, "Access-Control-Allow-Methods", "POST");
        header(r, "Access-Control-Allow-Headers", "Content-Type");
        header(r, "Access-Control-Max-Age", "1800");
        header(r, "Access-Control-Expose-Headers", "errors, content-type");
        header(r, "Access-Control-Allow-Credentials", null);
    }

    @Test
    void preflightNamesOnlyTheMatchedHandlersMethods() {
        Response r = preflight("/api/items/7", CLIENT, "PUT", null);
        assertEquals(200, r.statusCode());
        header(r, "Access-Control-Allow-Methods", "PUT");
        header(r, "Access-Control-Allow-Headers", null);
        Response p = preflight("/api/items/any/name/smith", CLIENT, "GET", null);
        header(p, "Access-Control-Allow-Methods", "GET");
    }

    @Test
    void preflightForAMethodNoHandlerServesGrantsNothing() {
        Response r = preflight("/api/items/7", CLIENT, "DELETE", null);
        noCors(r);
    }

    @Test
    void actualRequestCarriesOnlyTheSourcesActualHeaders() {
        Response r = req().header("Origin", CLIENT).get("/api/items");
        assertEquals(200, r.statusCode());
        header(r, "Access-Control-Allow-Origin", "*");
        header(r, "Access-Control-Expose-Headers", "errors, content-type");
        header(r, "Access-Control-Allow-Credentials", null);
        header(r, "Access-Control-Allow-Methods", null);
        header(r, "Access-Control-Allow-Headers", null);
        header(r, "Access-Control-Max-Age", null);
    }

    @Test
    void noOriginIsUntouched() {
        Response r = req().get("/api/items");
        assertEquals(200, r.statusCode());
        assertEquals("[]", r.asString());
        noCors(r);
    }

    @Test
    void sameOriginIsNotACorsRequest() {
        Response r = req().header("Origin", Cors.sameOrigin()).get("/api/items");
        assertEquals(200, r.statusCode());
        assertEquals("[]", r.asString());
        noCors(r);
    }

    @Test
    void sameOriginProceedsToRoutingExactlyAsWithoutOrigin() {
        // ADR-020: DELETE is outside the platform's method list; the platform would answer 403.
        // The source routed it: the resource maps no DELETE here, so the answer is the routing's own.
        Response plain = req().delete("/api/items");
        Response same = req().header("Origin", Cors.sameOrigin()).delete("/api/items");
        assertEquals(405, plain.statusCode());
        assertEquals(plain.statusCode(), same.statusCode());
        assertEquals(plain.getHeader("Allow"), same.getHeader("Allow"));
        noCors(same);
        Response patch = req().header("Origin", Cors.sameOrigin()).patch("/api/items/7");
        assertEquals(req().patch("/api/items/7").statusCode(), patch.statusCode());
        noCors(patch);
        // a same-origin OPTIONS carrying Access-Control-Request-Method is not a preflight for the source
        Response opt = preflight("/api/items", Cors.sameOrigin(), "DELETE", null);
        assertEquals(req().options("/api/items").statusCode(), opt.statusCode());
        noCors(opt);
        // the application still sees the Origin it was sent
        assertEquals(Cors.sameOrigin(), req().header("Origin", Cors.sameOrigin()).get("/api/content/origin").asString());
    }

    @Test
    void aRouteWithoutASourcePolicyGetsNoPermission() {
        Response r = req().header("Origin", CLIENT).get("/api/other");
        assertEquals(200, r.statusCode());
        assertEquals("other", r.asString());
        noCors(r);
        noCors(preflight("/api/other", CLIENT, "GET", null));
    }

    @Test
    void restrictivePolicyRefusesAnOriginItDoesNotName() {
        // the platform's origins are the UNION ("*" here); the adapter still refuses for this handler
        Response r = preflight("/api/narrow", EVIL, "GET", null);
        assertEquals(403, r.statusCode());
        assertEquals("Invalid CORS request", r.asString());
        noCors(r);
        Response a = req().header("Origin", EVIL).get("/api/narrow");
        assertEquals(403, a.statusCode());
        assertEquals("Invalid CORS request", a.asString());
        noCors(a);
    }

    @Test
    void restrictivePolicyNeverEchoesARejectedMethod() {
        Response r = preflight("/api/narrow", ALLOWED, "POST", null);
        assertEquals(403, r.statusCode());
        noCors(r);
        Response a = req().header("Origin", ALLOWED).post("/api/narrow");
        assertEquals(403, a.statusCode());
        noCors(a);
    }

    @Test
    void restrictivePolicyEchoesOnlyAllowedHeaders() {
        Response r = preflight("/api/narrow", ALLOWED, "GET", "X-Allowed, X-Evil");
        assertEquals(200, r.statusCode());
        header(r, "Access-Control-Allow-Origin", ALLOWED);
        header(r, "Access-Control-Allow-Methods", "GET");
        header(r, "Access-Control-Allow-Headers", "X-Allowed");
        header(r, "Access-Control-Allow-Credentials", "true");
        header(r, "Access-Control-Max-Age", "600");
        header(r, "Access-Control-Expose-Headers", null);
        Response none = preflight("/api/narrow", ALLOWED, "GET", "X-Evil");
        assertEquals(403, none.statusCode());
        noCors(none);
    }

    @Test
    void restrictivePolicyActualRequestFromItsOrigin() {
        Response r = req().header("Origin", ALLOWED).get("/api/narrow");
        assertEquals(200, r.statusCode());
        assertEquals("narrow", r.asString());
        header(r, "Access-Control-Allow-Origin", ALLOWED);
        header(r, "Access-Control-Allow-Credentials", "true");
    }

    @Test
    void theDecidedMediaTypeParameterIsRemovedAndNothingElse() {
        assertEquals("application/json", req().get("/api/content/json-utf8").getHeader("Content-Type"));
        assertEquals("application/json;charset=ISO-8859-1", req().get("/api/content/json-latin").getHeader("Content-Type"));
        assertEquals("application/json;profile=x", req().get("/api/content/json-extra").getHeader("Content-Type"));
        assertEquals("text/plain;charset=UTF-8", req().get("/api/content/text-utf8").getHeader("Content-Type"));
        assertEquals("{\"k\":\"v\"}", req().get("/api/content/json-utf8").asString());
    }
}

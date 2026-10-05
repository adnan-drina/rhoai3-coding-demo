package com.example.auth;

import static io.restassured.RestAssured.given;

import io.quarkus.test.junit.QuarkusTest;
import org.junit.jupiter.api.Test;

/**
 * Golden runtime proof for security-config.md A-bar (401 / 403 / 200).
 * Requires product module deps: quarkus-junit5, rest-assured, security + JDBC.
 */
@QuarkusTest
class SecurityAuthzIT {

    @Test
    void anonymousIs401() {
        given().when().get("/api/admin").then().statusCode(401);
    }

    @Test
    void wrongRoleIs403() {
        given().auth().preemptive().basic("user", "user").when().get("/api/admin").then().statusCode(403);
    }

    @Test
    void adminIs200() {
        given().auth().preemptive().basic("admin", "admin").when().get("/api/admin").then().statusCode(200);
    }
}

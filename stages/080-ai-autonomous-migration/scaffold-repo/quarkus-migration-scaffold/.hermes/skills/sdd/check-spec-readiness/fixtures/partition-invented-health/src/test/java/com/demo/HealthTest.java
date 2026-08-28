package com.demo;

import io.quarkus.test.junit.QuarkusTest;

import io.restassured.RestAssured;

import org.junit.jupiter.api.Test;

import static io.restassured.RestAssured.given;
import static org.hamcrest.Matchers.is;

@QuarkusTest
class HealthTest {

    @Test
    void healthEndpointShouldReturnUp() {
        // /q/health is a Quarkus management endpoint — it sits outside the
        // application root-path (/api), so we must clear basePath.
        String originalBasePath = RestAssured.basePath;
        RestAssured.basePath = "";
        try {
            given()
                .when().get("/q/health")
                .then()
                    .statusCode(200)
                    .body("status", is("UP"));
        } finally {
            RestAssured.basePath = originalBasePath;
        }
    }
}

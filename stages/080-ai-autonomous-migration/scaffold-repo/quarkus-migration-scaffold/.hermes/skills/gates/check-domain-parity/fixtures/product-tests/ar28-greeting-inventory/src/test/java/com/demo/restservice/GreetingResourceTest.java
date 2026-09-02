package com.demo.restservice;

import io.quarkus.test.junit.QuarkusTest;

/** dest-8-shaped: @QuarkusTest GET /greeting is boot. No /q/health. */
@QuarkusTest
public class GreetingResourceTest {
    void hello() {
        // GET /greeting
    }
}

package com.example.app.rest.controller;

import static io.restassured.RestAssured.given;
import static org.hamcrest.CoreMatchers.is;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import io.quarkus.test.InjectMock;
import io.quarkus.test.junit.QuarkusTest;
import io.restassured.http.ContentType;
import org.junit.jupiter.api.Test;
import com.example.app.mapper.SampleTypeMapper;
import com.example.app.model.SampleType;
import com.example.app.rest.dto.SampleTypeDto;
import com.example.app.service.ApplicationService;

/**
 * Golden copy-pattern for Quarkus REST controller tests (S-010 / testing.md).
 * Fixture path only — not compiled by scaffold pom; copy into dest test tree.
 *
 * Pattern: {@code @QuarkusTest} + REST Assured + {@code @InjectMock} on the
 * <b>service</b> (not mapper) for MockMvc-isolation ports; stub every method
 * the request path calls.
 */
@QuarkusTest
class SampleTypeRestControllerTests {

    @InjectMock
    ApplicationService clinicService;

    @InjectMock
    SampleTypeMapper sampleTypeMapper;

    @Test
    void getPetType_happyPath() {
        SampleType entity = new SampleType();
        entity.setId(1);
        entity.setName("cat");
        SampleTypeDto dto = new SampleTypeDto();
        dto.setId(1);
        dto.setName("cat");

        when(clinicService.findPetTypeById(1)).thenReturn(entity);
        when(sampleTypeMapper.toPetTypeDto(any(SampleType.class))).thenReturn(dto);

        given()
                .accept(ContentType.JSON)
                .when()
                .get("/api/pettypes/1")
                .then()
                .statusCode(200)
                .body("id", is(1))
                .body("name", is("cat"));
    }
}

package org.springframework.samples.petclinic.rest.controller;

import static io.restassured.RestAssured.given;
import static org.hamcrest.CoreMatchers.is;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import io.quarkus.test.InjectMock;
import io.quarkus.test.junit.QuarkusTest;
import io.restassured.http.ContentType;
import org.junit.jupiter.api.Test;
import org.springframework.samples.petclinic.mapper.PetTypeMapper;
import org.springframework.samples.petclinic.model.PetType;
import org.springframework.samples.petclinic.rest.dto.PetTypeDto;
import org.springframework.samples.petclinic.service.ClinicService;

/**
 * Golden copy-pattern for Quarkus REST controller tests (S-010 / testing.md).
 * Fixture path only — not compiled by scaffold pom; copy into dest test tree.
 *
 * Pattern: {@code @QuarkusTest} + REST Assured + {@code @InjectMock} on the
 * <b>service</b> (not mapper) for MockMvc-isolation ports; stub every method
 * the request path calls.
 */
@QuarkusTest
class PetTypeRestControllerTests {

    @InjectMock
    ClinicService clinicService;

    @InjectMock
    PetTypeMapper petTypeMapper;

    @Test
    void getPetType_happyPath() {
        PetType entity = new PetType();
        entity.setId(1);
        entity.setName("cat");
        PetTypeDto dto = new PetTypeDto();
        dto.setId(1);
        dto.setName("cat");

        when(clinicService.findPetTypeById(1)).thenReturn(entity);
        when(petTypeMapper.toPetTypeDto(any(PetType.class))).thenReturn(dto);

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

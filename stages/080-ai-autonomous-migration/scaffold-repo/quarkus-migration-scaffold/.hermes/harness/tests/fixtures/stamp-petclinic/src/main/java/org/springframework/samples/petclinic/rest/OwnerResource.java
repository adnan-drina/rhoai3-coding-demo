package org.springframework.samples.petclinic.rest;

import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OwnerResource {
    @GetMapping("/owners")
    public String list(@Valid String q) {
        return "ok";
    }
}

package org.acme.ledger.rest;

import jakarta.inject.Inject;
import jakarta.validation.ConstraintViolation;
import jakarta.validation.Validator;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.UriInfo;
import java.util.Collection;
import java.util.Set;
import java.util.stream.Collectors;
import org.acme.ledger.dto.OwnerDto;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/owners")
public class OwnerRestController {

    @Inject
    Validator validator;

    @Inject
    OwnerStore store;

    @GetMapping(produces = "application/json")
    public Collection<OwnerDto> listOwners() {
        return store.all();
    }

    @PostMapping(consumes = "application/json", produces = "application/json")
    public ResponseEntity<OwnerDto> addOwner(@RequestBody OwnerDto ownerDto, @Context UriInfo uriInfo) {
        HttpHeaders headers = new HttpHeaders();
        Set<ConstraintViolation<OwnerDto>> violations = validator.validate(ownerDto);
        if (!violations.isEmpty() || ownerDto.getId() != null) {
            headers.add("errors", errors(violations, ownerDto.getId() != null));
            return new ResponseEntity<>(headers, HttpStatus.BAD_REQUEST);
        }
        OwnerDto saved = store.save(ownerDto);
        headers.setLocation(uriInfo.getBaseUriBuilder().path("/api/owners/{id}").build(saved.getId()));
        return new ResponseEntity<>(saved, headers, HttpStatus.CREATED);
    }

    @PutMapping(path = "/{ownerId}", consumes = "application/json", produces = "application/json")
    public ResponseEntity<OwnerDto> updateOwner(@PathVariable("ownerId") int ownerId, @RequestBody OwnerDto ownerDto) {
        HttpHeaders headers = new HttpHeaders();
        Set<ConstraintViolation<OwnerDto>> violations = validator.validate(ownerDto);
        if (!violations.isEmpty()) {
            headers.add("errors", errors(violations, false));
            return new ResponseEntity<>(headers, HttpStatus.BAD_REQUEST);
        }
        OwnerDto current = store.find(ownerId);
        if (current == null) {
            return new ResponseEntity<>(HttpStatus.NOT_FOUND);
        }
        current.setFirstName(ownerDto.getFirstName());
        current.setLastName(ownerDto.getLastName());
        return new ResponseEntity<>(HttpStatus.NO_CONTENT);
    }

    static String errors(Set<ConstraintViolation<OwnerDto>> violations, boolean idGiven) {
        String fields = violations.stream().map(v -> v.getPropertyPath().toString()).sorted().collect(Collectors.joining(","));
        return "[" + fields + (idGiven ? (fields.isEmpty() ? "id" : ",id") : "") + "]";
    }
}

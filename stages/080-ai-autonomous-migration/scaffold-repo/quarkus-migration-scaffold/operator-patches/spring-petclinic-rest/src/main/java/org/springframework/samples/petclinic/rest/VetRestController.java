/*
 * Copyright 2016-2018 the original author or authors.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
package org.springframework.samples.petclinic.rest;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.samples.petclinic.dto.VetDto;
import org.springframework.samples.petclinic.mapper.SpecialtyMapper;
import org.springframework.samples.petclinic.mapper.VetMapper;
import org.springframework.samples.petclinic.model.Specialty;
import org.springframework.samples.petclinic.model.Vet;
import org.springframework.samples.petclinic.service.ClinicService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.*;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.UriInfo;

import jakarta.validation.ConstraintViolationException;
import jakarta.validation.Valid;

import jakarta.transaction.Transactional;
import java.util.ArrayList;
import java.util.Collection;

/**
 * @author Vitaliy Fedoriv
 */

@RestController
@RequestMapping("api/vets")
public class VetRestController {

    private final ClinicService clinicService;
    private final VetMapper vetMapper;
    private final SpecialtyMapper specialtyMapper;

    public VetRestController(ClinicService clinicService, VetMapper vetMapper, SpecialtyMapper specialtyMapper) {
        this.clinicService = clinicService;
        this.vetMapper = vetMapper;
        this.specialtyMapper = specialtyMapper;
    }

    @PreAuthorize("@securityMode.disabled() or hasRole(@roles.VET_ADMIN)")
    @RequestMapping(value = "", method = RequestMethod.GET, produces = "application/json")
    public ResponseEntity<Collection<VetDto>> getAllVets() {
        Collection<VetDto> vets = new ArrayList<VetDto>();
        vets.addAll(vetMapper.toVetDtos(this.clinicService.findAllVets()));
        if (vets.isEmpty()) {
            return new ResponseEntity<Collection<VetDto>>(HttpStatus.NOT_FOUND);
        }
        return new ResponseEntity<Collection<VetDto>>(vets, HttpStatus.OK);
    }

    @PreAuthorize("@securityMode.disabled() or hasRole(@roles.VET_ADMIN)")
    @RequestMapping(value = "/{vetId}", method = RequestMethod.GET, produces = "application/json")
    public ResponseEntity<VetDto> getVet(@PathVariable("vetId") int vetId) {
        Vet vet = this.clinicService.findVetById(vetId);
        if (vet == null) {
            return new ResponseEntity<VetDto>(HttpStatus.NOT_FOUND);
        }
        return new ResponseEntity<VetDto>(vetMapper.toVetDto(vet), HttpStatus.OK);
    }

    @PreAuthorize("@securityMode.disabled() or hasRole(@roles.VET_ADMIN)")
    @RequestMapping(value = "", method = RequestMethod.POST, produces = "application/json")
    public ResponseEntity<VetDto> addVet(@RequestBody @Valid VetDto vetDto, @Context UriInfo uriInfo) {
        BindingErrorsResponse errors = new BindingErrorsResponse();
        HttpHeaders headers = new HttpHeaders();
        try {
            if (vetDto == null) {
                headers.add("errors", errors.toJSON());
                return new ResponseEntity<VetDto>(headers, HttpStatus.BAD_REQUEST);
            }
        } catch (ConstraintViolationException e) {
            errors.addAllErrors(e.getConstraintViolations());
            headers.add("errors", errors.toJSON());
            return new ResponseEntity<VetDto>(headers, HttpStatus.BAD_REQUEST);
        }
        Vet vet = vetMapper.toVet(vetDto);
        this.clinicService.saveVet(vet);
        headers.setLocation(uriInfo.getBaseUriBuilder().path("/api/vets/{id}").build(vet.getId()));
        return new ResponseEntity<VetDto>(vetMapper.toVetDto(vet), headers, HttpStatus.CREATED);
    }

    @PreAuthorize("@securityMode.disabled() or hasRole(@roles.VET_ADMIN)")
    @RequestMapping(value = "/{vetId}", method = RequestMethod.PUT, produces = "application/json")
    public ResponseEntity<VetDto> updateVet(@PathVariable("vetId") int vetId, @RequestBody @Valid VetDto vetDto) {
        BindingErrorsResponse errors = new BindingErrorsResponse();
        HttpHeaders headers = new HttpHeaders();
        try {
            if (vetDto == null) {
                headers.add("errors", errors.toJSON());
                return new ResponseEntity<VetDto>(headers, HttpStatus.BAD_REQUEST);
            }
        } catch (ConstraintViolationException e) {
            errors.addAllErrors(e.getConstraintViolations());
            headers.add("errors", errors.toJSON());
            return new ResponseEntity<VetDto>(headers, HttpStatus.BAD_REQUEST);
        }
        Vet currentVet = this.clinicService.findVetById(vetId);
        if (currentVet == null) {
            return new ResponseEntity<VetDto>(HttpStatus.NOT_FOUND);
        }
        currentVet.setFirstName(vetDto.getFirstName());
        currentVet.setLastName(vetDto.getLastName());
        currentVet.clearSpecialties();
        for (Specialty spec : specialtyMapper.toSpecialtys(vetDto.getSpecialties())) {
            currentVet.addSpecialty(spec);
        }
        this.clinicService.saveVet(currentVet);
        return new ResponseEntity<VetDto>(vetMapper.toVetDto(currentVet), HttpStatus.NO_CONTENT);
    }

    @PreAuthorize("@securityMode.disabled() or hasRole(@roles.VET_ADMIN)")
    @RequestMapping(value = "/{vetId}", method = RequestMethod.DELETE, produces = "application/json")
    @Transactional
    public ResponseEntity<Void> deleteVet(@PathVariable("vetId") int vetId) {
        Vet vet = this.clinicService.findVetById(vetId);
        if (vet == null) {
            return new ResponseEntity<Void>(HttpStatus.NOT_FOUND);
        }
        this.clinicService.deleteVet(vet);
        return new ResponseEntity<Void>(HttpStatus.NO_CONTENT);
    }


}

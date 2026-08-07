package org.springframework.samples.petclinic.rest;

import java.util.ArrayList;
import java.util.Collection;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.samples.petclinic.dto.VetDto;
import org.springframework.samples.petclinic.service.ClinicService;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;

/**
 * Shape-matched to spring-petclinic-rest VetRestController (v2.6.2):
 * class @RequestMapping + method RequestMethod.GET + ResponseEntity&lt;Collection&lt;VetDto&gt;&gt;.
 */
@RestController
@RequestMapping("api/vets")
public class VetResource {
    private final ClinicService clinicService;

    public VetResource(ClinicService clinicService) {
        this.clinicService = clinicService;
    }

    @RequestMapping(value = "", method = RequestMethod.GET, produces = "application/json")
    public ResponseEntity<Collection<VetDto>> getAllVets() {
        Collection<VetDto> vets = new ArrayList<VetDto>();
        if (vets.isEmpty()) {
            return new ResponseEntity<Collection<VetDto>>(HttpStatus.NOT_FOUND);
        }
        return new ResponseEntity<Collection<VetDto>>(vets, HttpStatus.OK);
    }

    @RequestMapping(value = "/{vetId}", method = RequestMethod.GET, produces = "application/json")
    public ResponseEntity<VetDto> getVet(@PathVariable("vetId") int vetId) {
        return new ResponseEntity<VetDto>(HttpStatus.NOT_FOUND);
    }
}

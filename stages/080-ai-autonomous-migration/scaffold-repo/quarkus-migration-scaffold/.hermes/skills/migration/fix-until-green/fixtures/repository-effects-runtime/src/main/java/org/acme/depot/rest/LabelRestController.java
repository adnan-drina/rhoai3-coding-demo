package org.acme.depot.rest;

import jakarta.inject.Inject;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.UriInfo;
import java.net.URI;
import org.acme.depot.model.Label;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/labels")
public class LabelRestController {
    @Inject
    DepotService service;

    public static class LabelDto {
        public Integer id;
        public String name;
    }

    @GetMapping(path = "/{id}", produces = "application/json")
    public ResponseEntity<Label> get(@PathVariable("id") int id) {
        Label l = service.findLabel(id);
        return l == null ? new ResponseEntity<>(HttpStatus.NOT_FOUND) : new ResponseEntity<>(l, HttpStatus.OK);
    }

    // the source built this Location from the REQUEST body's id, which a create
    // does not carry (Spring: ucBuilder.path("/api/labels/{id}").buildAndExpand(dto.getId()))
    @PostMapping(consumes = "application/json", produces = "application/json")
    public ResponseEntity<Label> create(@RequestBody LabelDto dto, @Context UriInfo uriInfo) {
        Label label = new Label();
        label.name = dto.name;
        Label saved = service.saveLabel(label);   // committed when this call returns
        // LOCATION
        URI location = uriInfo.getBaseUriBuilder().path("/api/labels/{id}").build(dto.id == null ? "" : dto.id);
        // END-LOCATION
        return ResponseEntity.created(location).body(saved);
    }

    @DeleteMapping(path = "/{id}")
    public ResponseEntity<Void> delete(@PathVariable("id") int id) {
        Label l = service.findLabel(id);
        if (l == null) {
            return new ResponseEntity<>(HttpStatus.NOT_FOUND);
        }
        service.deleteLabel(l);
        return new ResponseEntity<>(HttpStatus.NO_CONTENT);
    }
}

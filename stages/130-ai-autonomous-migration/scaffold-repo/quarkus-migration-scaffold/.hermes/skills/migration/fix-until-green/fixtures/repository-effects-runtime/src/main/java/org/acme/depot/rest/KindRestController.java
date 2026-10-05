package org.acme.depot.rest;

import jakarta.inject.Inject;
import org.acme.depot.model.Kind;
import org.acme.depot.model.Stamp;
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
@RequestMapping("/api")
public class KindRestController {
    @Inject
    DepotService service;

    @GetMapping(path = "/kinds/{id}", produces = "application/json")
    public ResponseEntity<Kind> get(@PathVariable("id") int id) {
        Kind k = service.findKind(id);
        return k == null ? new ResponseEntity<>(HttpStatus.NOT_FOUND) : new ResponseEntity<>(k, HttpStatus.OK);
    }

    @PostMapping(path = "/kinds", consumes = "application/json", produces = "application/json")
    public ResponseEntity<Kind> create(@RequestBody Kind kind) {
        kind.id = null;
        return new ResponseEntity<>(service.saveKind(kind), HttpStatus.CREATED);
    }

    @DeleteMapping(path = "/kinds/{id}")
    public ResponseEntity<Void> delete(@PathVariable("id") int id) {
        Kind k = service.findKind(id);   // one transaction: the row as committed
        if (k == null) {
            return new ResponseEntity<>(HttpStatus.NOT_FOUND);
        }
        service.deleteKind(k);           // another: the detached row is deleted
        return new ResponseEntity<>(HttpStatus.NO_CONTENT);
    }

    @PostMapping(path = "/pallets/{pid}/kind/{kid}")
    public ResponseEntity<Void> setKind(@PathVariable("pid") int pid, @PathVariable("kid") int kid) {
        return new ResponseEntity<>(service.setKind(pid, kid) ? HttpStatus.NO_CONTENT : HttpStatus.NOT_FOUND);
    }

    @PostMapping(path = "/pallets/{pid}/stamps", consumes = "application/json", produces = "application/json")
    public ResponseEntity<Stamp> stamp(@PathVariable("pid") int pid, @RequestBody Stamp stamp) {
        Stamp saved = service.addStamp(pid, stamp.name);
        return saved == null ? new ResponseEntity<>(HttpStatus.NOT_FOUND) : new ResponseEntity<>(saved, HttpStatus.CREATED);
    }

    @GetMapping(path = "/stamps/{id}", produces = "application/json")
    public ResponseEntity<Stamp> getStamp(@PathVariable("id") int id) {
        Stamp s = service.findStamp(id);
        return s == null ? new ResponseEntity<>(HttpStatus.NOT_FOUND) : new ResponseEntity<>(s, HttpStatus.OK);
    }
}

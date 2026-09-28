package org.acme.depot.rest;

import jakarta.inject.Inject;
import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.UriInfo;
import java.util.Collection;
import java.util.Map;
import org.acme.depot.model.Crate;
import org.acme.depot.model.Pallet;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api")
public class CrateRestController {
    @Inject
    DepotService service;

    @GetMapping(path = "/crates", produces = "application/json")
    public Collection<Crate> list() {
        return service.allCrates();
    }

    @GetMapping(path = "/crates/{id}", produces = "application/json")
    public ResponseEntity<Crate> get(@PathVariable("id") int id) {
        Crate c = service.findCrate(id);
        return c == null ? new ResponseEntity<>(HttpStatus.NOT_FOUND) : new ResponseEntity<>(c, HttpStatus.OK);
    }

    @PostMapping(path = "/crates", consumes = "application/json", produces = "application/json")
    public ResponseEntity<Crate> create(@RequestBody Crate crate, @Context UriInfo uriInfo) {
        Crate saved = service.saveCrate(crate);
        return ResponseEntity.created(uriInfo.getBaseUriBuilder().path("/api/crates/{id}").build(saved.id == null ? "" : saved.id))
                .body(saved);
    }

    @PutMapping(path = "/crates/{id}", consumes = "application/json")
    public ResponseEntity<Void> update(@PathVariable("id") int id, @RequestBody Map<String, String> body) {
        Crate current = service.findCrate(id);   // one transaction: the row as committed
        if (current == null) {
            return new ResponseEntity<>(HttpStatus.NOT_FOUND);
        }
        current.name = body.get("name");
        service.saveCrate(current);              // another: the detached change is saved
        return new ResponseEntity<>(HttpStatus.NO_CONTENT);
    }

    @DeleteMapping(path = "/crates/{id}")
    public ResponseEntity<Void> delete(@PathVariable("id") int id) {
        Crate current = service.findCrate(id);
        if (current == null) {
            return new ResponseEntity<>(HttpStatus.NOT_FOUND);
        }
        service.deleteCrate(current);
        return new ResponseEntity<>(HttpStatus.NO_CONTENT);
    }

    @GetMapping(path = "/pallets/{id}", produces = "application/json")
    public ResponseEntity<Pallet> pallet(@PathVariable("id") int id) {
        Pallet p = service.findPallet(id);
        return p == null ? new ResponseEntity<>(HttpStatus.NOT_FOUND) : new ResponseEntity<>(p, HttpStatus.OK);
    }

    @PostMapping(path = "/pallets/{pid}/labels/{lid}")
    public ResponseEntity<Void> link(@PathVariable("pid") int pid, @PathVariable("lid") int lid) {
        return new ResponseEntity<>(service.link(pid, lid) ? HttpStatus.NO_CONTENT : HttpStatus.NOT_FOUND);
    }
}

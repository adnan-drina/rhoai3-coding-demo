package org.acme.ledger.rest;

import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.UriBuilder;
import jakarta.ws.rs.core.UriInfo;
import java.net.URI;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/entries")
public class EntryRestController {

    @PostMapping(consumes = "application/json", produces = "application/json")
    public ResponseEntity<Entry> addEntry(@RequestBody Entry entry, @Context UriInfo uriInfo) {
        entry.id = 7;
        URI location = uriInfo.getBaseUriBuilder().path("/api/entries/{id}").build(entry.id);
        return ResponseEntity.created(location).body(entry);
    }

    @PostMapping(path = "/touch", consumes = "application/json", produces = "application/json")
    public ResponseEntity<Entry> touch(@RequestBody Entry entry, @Context UriInfo uriInfo) {
        return ResponseEntity.ok(entry);
    }

    @GetMapping(path = "/{id}/archive", produces = "text/plain")
    public String archive(@PathVariable("id") int id) {
        return archiveLink(UriBuilder.fromPath("/archive"), id).toString();
    }

    static URI archiveLink(UriBuilder builder, int id) {
        return builder.path("{id}").build(id);
    }
}

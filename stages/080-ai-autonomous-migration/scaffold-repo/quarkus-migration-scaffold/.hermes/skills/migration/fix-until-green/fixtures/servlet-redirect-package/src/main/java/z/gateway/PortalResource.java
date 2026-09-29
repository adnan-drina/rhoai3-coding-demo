package z.gateway;

import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.UriInfo;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** A renamed equivalent of the same source shape (other package, class, method, parameter and target). */
@RestController
@RequestMapping("/portal")
public class PortalResource {

    @RequestMapping(value = "/")
    public ResponseEntity<Void> showPortal(@Context UriInfo info) {
        return ResponseEntity.status(HttpStatus.FOUND)
            .location(info.getBaseUriBuilder().path("docs/index.html").build())
            .build();
    }
}

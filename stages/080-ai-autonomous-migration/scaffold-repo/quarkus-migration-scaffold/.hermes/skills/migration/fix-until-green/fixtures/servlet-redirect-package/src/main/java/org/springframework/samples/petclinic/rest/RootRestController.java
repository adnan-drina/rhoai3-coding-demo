package org.springframework.samples.petclinic.rest;

import jakarta.ws.rs.core.Context;
import jakarta.ws.rs.core.UriInfo;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * The source handler, translated by the servlet-redirect-response recipe: it took
 * HttpServletResponse and called response.sendRedirect(servletContextPath + "/swagger-ui/index.html"),
 * with servletContextPath read by @Value("#{servletContext.contextPath}").
 */
@RestController
@RequestMapping("/")
public class RootRestController {

    @RequestMapping(value = "/")
    public ResponseEntity<Void> redirectToSwagger(@Context UriInfo uriInfo) {
        return ResponseEntity.status(HttpStatus.FOUND)
            .location(uriInfo.getBaseUriBuilder().path("swagger-ui/index.html").build())
            .build();
    }
}

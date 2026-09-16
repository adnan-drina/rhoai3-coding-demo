package org.example.shop.security;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;

import org.eclipse.microprofile.config.inject.ConfigProperty;

import io.quarkus.vertx.http.runtime.security.BasicAuthenticationMechanism;
import io.quarkus.vertx.http.security.HttpSecurity;

/** The fixture's security switch, registered the way the destination registers its own. */
@ApplicationScoped
public class FixtureSecurity {

    @ConfigProperty(name = "fixture.security.enable", defaultValue = "false")
    boolean enabled;

    void configure(@Observes HttpSecurity httpSecurity) {
        if (enabled) {
            httpSecurity.mechanism(new BasicAuthenticationMechanism("fixture", false)).path("*").authenticated();
        } else {
            httpSecurity.path("*").permit();
        }
    }
}

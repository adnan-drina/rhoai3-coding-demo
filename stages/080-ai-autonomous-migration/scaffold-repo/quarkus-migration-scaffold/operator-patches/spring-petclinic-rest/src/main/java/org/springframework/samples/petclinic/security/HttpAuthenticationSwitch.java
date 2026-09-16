package org.springframework.samples.petclinic.security;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.inject.Inject;

import io.quarkus.vertx.http.security.HttpSecurity;

/**
 * ADR-014: HTTP authentication follows the source's switch.
 *
 * <p>The source had two configurations over one property, and authentication
 * was one of the things the property decided: with the switch on,
 * {@code BasicAuthenticationConfig} registered {@code httpBasic()}; with it
 * off, {@code DisableSecurityConfig} permitted every request and no
 * authentication mechanism existed, so no credential was ever requested,
 * consulted or challenged for.
 *
 * <p>The platform resolves {@code quarkus.http.auth.basic} at build time, so
 * that key alone cannot carry a runtime switch. The mechanism is therefore
 * registered here instead, through the platform's programmatic HTTP security
 * API: the {@code HttpSecurity} event is fired at RUNTIME, from
 * {@code HttpSecurityConfiguration#prepareHttpSecurity} through the CDI
 * {@code BeanManager}, after configuration is available -- so this observer
 * reads the same runtime value {@link SecurityMode} reads, and either registers
 * the mechanism or leaves the application with none.
 * {@code quarkus.http.auth.basic=false} in application.properties keeps the
 * build from registering one unconditionally; a mechanism registered here still
 * turns basic authentication on, because
 * {@code HttpSecurityConfiguration#initializeHttpSecurityConfiguration}
 * promotes the build-time value to true when the programmatic registration
 * supplies one.
 *
 * <p>With the switch off nothing is registered, so an anonymous request is
 * never challenged and a request that does carry credentials is never
 * authenticated against them -- which is what the source did. With the switch
 * on, the mechanism authenticates against the seeded users/roles tables and
 * every {@code @PreAuthorize} expression decides the call.
 */
@ApplicationScoped
public class HttpAuthenticationSwitch {

    @Inject
    SecurityMode securityMode;

    void configure(@Observes HttpSecurity httpSecurity) {
        if (this.securityMode.isEnabled()) {
            httpSecurity.mechanism(new SourceBasicAuthenticationMechanism());
        }
    }
}

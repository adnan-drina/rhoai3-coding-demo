package org.springframework.samples.petclinic.security;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.inject.Inject;

import io.quarkus.vertx.http.security.HttpSecurity;

/**
 * ADR-014: the source's HTTP security configuration, in both modes.
 *
 * <p>The source expressed its switch structurally, as two mutually exclusive
 * configurations over one property, and each of them configured TWO things:
 *
 * <ul>
 *   <li>{@code BasicAuthenticationConfig} ({@code petclinic.security.enable=true})
 *       registered {@code httpBasic()} <em>and</em>
 *       {@code authorizeRequests().anyRequest().authenticated()} -- every request
 *       under the application's context path needed an authenticated identity,
 *       including the routes that carry no {@code @PreAuthorize} at all, such as
 *       the root redirect.</li>
 *   <li>{@code DisableSecurityConfig} ({@code petclinic.security.enable=false})
 *       registered {@code authorizeRequests().anyRequest().permitAll()} and no
 *       authentication mechanism, so no credential was ever requested,
 *       consulted or challenged for.</li>
 * </ul>
 *
 * <p>Both halves are registered here, from one observer, off one value, so the
 * two cannot drift apart. {@link SecurityMode} is the single reader of the
 * property; the {@code @PreAuthorize} expressions read the same bean.
 *
 * <h2>Why registration happens at runtime</h2>
 *
 * <p>The platform resolves {@code quarkus.http.auth.basic} at build time, so
 * that key alone cannot carry a runtime switch. The platform's programmatic
 * HTTP security API can: {@code HttpSecurityConfiguration#prepareHttpSecurity}
 * fires {@link HttpSecurity} as a CDI event at RUNTIME, through
 * {@code Arc.container().beanManager().getEvent()}, from
 * {@code initializeHttpSecurityConfiguration}, which has already resolved its
 * configuration through {@code ConfigProvider}. This observer therefore runs
 * after runtime configuration is available and decides what to register.
 * {@code quarkus.http.auth.basic=false} in application.properties keeps the
 * build from registering a mechanism unconditionally; a mechanism registered
 * here still turns basic authentication on, because
 * {@code initializeHttpSecurityConfiguration} promotes an empty or false
 * build-time value to {@code Optional.of(TRUE)} when the programmatically
 * supplied mechanism list contains a {@code BasicAuthenticationMechanism}.
 *
 * <h2>The scope of the request policy</h2>
 *
 * <p>{@link #APPLICATION_ROOT} has no leading slash on purpose. The platform
 * prepends {@code quarkus.http.root-path} to a permission path that does not
 * start with {@code /} -- measured in
 * {@code ImmutablePathMatcher.ImmutablePathMatcherBuilder#addPath}, which
 * concatenates the configured root path onto any path not already absolute --
 * so this one permission covers exactly the application's own routes, whatever
 * the root path is configured to be, and nothing outside them. It is the
 * destination's rendering of {@code anyRequest()}, whose scope in the source
 * was likewise the application's context path.
 *
 * <p>The non-application root ({@code quarkus.http.non-application-root-path},
 * {@code /q} by default and absolute) is deliberately NOT covered: it is
 * platform surface with no counterpart in the source, and it keeps the
 * platform's own defaults for health, metrics and the OpenAPI document.
 */
@ApplicationScoped
public class HttpSecuritySwitch {

    /**
     * Every path under the application root. Relative on purpose: the platform
     * prepends {@code quarkus.http.root-path}, so no root path is written here.
     */
    private static final String APPLICATION_ROOT = "*";

    @Inject
    SecurityMode securityMode;

    void configure(@Observes HttpSecurity httpSecurity) {
        if (this.securityMode.isEnabled()) {
            // BasicAuthenticationConfig: httpBasic() and anyRequest().authenticated().
            httpSecurity
                .mechanism(new SourceBasicAuthenticationMechanism())
                .path(APPLICATION_ROOT)
                .authenticated();
        } else {
            // DisableSecurityConfig: anyRequest().permitAll(), and no mechanism,
            // so an anonymous request is never challenged and a request that
            // does carry credentials is never authenticated against them.
            httpSecurity
                .path(APPLICATION_ROOT)
                .permit();
        }
    }
}

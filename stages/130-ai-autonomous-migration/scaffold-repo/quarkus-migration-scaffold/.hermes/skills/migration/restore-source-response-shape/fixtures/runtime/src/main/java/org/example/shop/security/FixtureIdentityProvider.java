package org.example.shop.security;

import jakarta.enterprise.context.ApplicationScoped;

import io.quarkus.security.AuthenticationFailedException;
import io.quarkus.security.identity.AuthenticationRequestContext;
import io.quarkus.security.identity.IdentityProvider;
import io.quarkus.security.identity.SecurityIdentity;
import io.quarkus.security.identity.request.UsernamePasswordAuthenticationRequest;
import io.quarkus.security.runtime.QuarkusPrincipal;
import io.quarkus.security.runtime.QuarkusSecurityIdentity;
import io.smallrye.mutiny.Uni;

/** One fixture identity (a test value, not a credential of anything). */
@ApplicationScoped
public class FixtureIdentityProvider implements IdentityProvider<UsernamePasswordAuthenticationRequest> {

    static final String USER = "fixture-user";
    static final String PASSWORD = "fixture-pass";

    @Override
    public Class<UsernamePasswordAuthenticationRequest> getRequestType() {
        return UsernamePasswordAuthenticationRequest.class;
    }

    @Override
    public Uni<SecurityIdentity> authenticate(UsernamePasswordAuthenticationRequest request,
                                              AuthenticationRequestContext context) {
        if (USER.equals(request.getUsername()) && PASSWORD.equals(new String(request.getPassword().getPassword()))) {
            return Uni.createFrom().item(QuarkusSecurityIdentity.builder()
                .setPrincipal(new QuarkusPrincipal(USER)).addRole("user").build());
        }
        return Uni.createFrom().failure(new AuthenticationFailedException());
    }
}

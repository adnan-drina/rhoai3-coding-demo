package org.springframework.samples.petclinic.security;

import java.util.Set;

import io.quarkus.security.identity.IdentityProviderManager;
import io.quarkus.security.identity.SecurityIdentity;
import io.quarkus.security.identity.request.AuthenticationRequest;
import io.quarkus.vertx.http.runtime.security.BasicAuthenticationMechanism;
import io.quarkus.vertx.http.runtime.security.ChallengeData;
import io.quarkus.vertx.http.runtime.security.HttpAuthenticationMechanism;
import io.quarkus.vertx.http.runtime.security.HttpCredentialTransport;
import io.smallrye.mutiny.Uni;
import io.vertx.ext.web.RoutingContext;

/**
 * ADR-014: HTTP Basic authentication as the source performed it.
 *
 * <p>Credential reading, decoding and the identity request are the platform's
 * own {@code BasicAuthenticationMechanism}, non-silent, over the realm the
 * source used. Only the challenge line is written here, because the two differ
 * in one observable byte: the source answered
 * {@code WWW-Authenticate: Basic realm="Realm"} (Spring's
 * {@code BasicAuthenticationEntryPoint}, default realm name {@code Realm}),
 * while the platform's mechanism builds its challenge from the constant
 * {@code basic} in lower case -- measured in
 * {@code BasicAuthenticationMechanism}'s string-concatenation recipe
 * {@code basic realm=""} in quarkus-vertx-http 3.27.3. Forty of the
 * enabled-mode source captures assert that header, so the case is part of the
 * comparison.
 *
 * <p>This class is deliberately NOT a CDI bean: a bean of this type would be
 * collected as an authentication mechanism in both modes, and the switch must
 * decide. {@link HttpSecuritySwitch} constructs and registers it, and only when
 * the switch is on.
 */
public final class SourceBasicAuthenticationMechanism implements HttpAuthenticationMechanism {

    /** The realm the source's challenge named. */
    static final String REALM = "Realm";

    private static final String CHALLENGE = "Basic realm=\"" + REALM + "\"";

    private static final String WWW_AUTHENTICATE = "WWW-Authenticate";

    private static final int UNAUTHORIZED = 401;

    private final BasicAuthenticationMechanism delegate = new BasicAuthenticationMechanism(REALM, false);

    @Override
    public Uni<SecurityIdentity> authenticate(RoutingContext context,
                                              IdentityProviderManager identityProviderManager) {
        return this.delegate.authenticate(context, identityProviderManager);
    }

    @Override
    public Uni<ChallengeData> getChallenge(RoutingContext context) {
        return Uni.createFrom().item(new ChallengeData(UNAUTHORIZED, WWW_AUTHENTICATE, CHALLENGE));
    }

    @Override
    public Set<Class<? extends AuthenticationRequest>> getCredentialTypes() {
        return this.delegate.getCredentialTypes();
    }

    @Override
    public Uni<HttpCredentialTransport> getCredentialTransport(RoutingContext context) {
        return this.delegate.getCredentialTransport(context);
    }

    @Override
    public int getPriority() {
        return this.delegate.getPriority();
    }
}

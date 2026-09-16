package org.springframework.samples.petclinic.security;

import java.util.List;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import org.hibernate.FlushMode;
import org.hibernate.Session;
import org.hibernate.SessionFactory;

import io.quarkus.security.AuthenticationFailedException;
import io.quarkus.security.identity.AuthenticationRequestContext;
import io.quarkus.security.identity.SecurityIdentity;
import io.quarkus.security.identity.SecurityIdentityAugmentor;
import io.smallrye.mutiny.Uni;

/**
 * ADR-014: account status, the half of the source's identity query that the
 * identity provider does not carry.
 *
 * <p>The source authenticated with
 * {@code select username,password,enabled from users where username=?}
 * ({@code BasicAuthenticationConfig#configureGlobal},
 * {@code jdbcAuthentication}), and Spring's {@code JdbcDaoImpl} refuses a row
 * whose {@code enabled} column is false: it raises {@code DisabledException},
 * an {@code AuthenticationException}, so the caller is answered with the
 * authentication challenge -- 401, never 403. The password may be correct and
 * the roles may be present; the account is still not usable.
 *
 * <p>quarkus-security-jpa 3.27 has no account-status member -- {@code @UserDefinition},
 * {@code @Username}, {@code @Password}, {@code @Roles}, {@code @RolesValue} are
 * the whole annotation set -- so the generated identity provider reads
 * {@code username}, {@code password} and the roles and stops there. This
 * augmentor supplies the missing term, and only that term.
 *
 * <h2>What it does and does not do</h2>
 *
 * <ul>
 *   <li>It denies authentication -- {@link AuthenticationFailedException},
 *       which the platform answers with the mechanism's challenge (401), not
 *       with an authorization failure (403). That is the source's status.</li>
 *   <li>It reads the {@code enabled} column of the one row that just
 *       authenticated. It does NOT filter the {@code User} entity globally: an
 *       entity-wide {@code @SQLRestriction} would also change what
 *       {@code UserRepositoryImpl#save} sees through
 *       {@code em.find(User.class, username)}, and so would change
 *       user-management behaviour on {@code POST /api/users}, which ADR-014
 *       does not authorize.</li>
 *   <li>It is inert for an anonymous identity and inert with the switch off,
 *       where no mechanism is registered and no identity is ever built from the
 *       store. It contributes no role, no identity and no credential in either
 *       mode, and it never widens an identity -- the only outcomes are "the
 *       identity the provider built" and "authentication failed".</li>
 *   <li>A row that has vanished between the provider's read and this one is
 *       refused for the same reason the source refused it: the source's
 *       {@code JdbcDaoImpl} raises {@code UsernameNotFoundException}, again an
 *       {@code AuthenticationException}, for an absent row.</li>
 * </ul>
 *
 * <p>The session handling is the platform's own recipe for reading the identity
 * store off the request thread, taken from
 * {@code io.quarkus.security.jpa.runtime.JpaIdentityProvider}: run under
 * {@code AuthenticationRequestContext#runBlocking}, open a short read-only
 * session with manual flush, and close it.
 */
@ApplicationScoped
public class DisabledAccountAugmentor implements SecurityIdentityAugmentor {

    /**
     * The account-status term of the source's identity query, by itself. The
     * username is the one the identity provider has already matched.
     */
    private static final String ACCOUNT_STATUS_QUERY =
        "select u.enabled from User u where u.username = :username";

    private static final String USERNAME_PARAMETER = "username";

    /** No identifier is named in the message: it answers an unauthenticated caller. */
    private static final String ACCOUNT_NOT_USABLE = "account is disabled or no longer exists";

    @Inject
    SecurityMode securityMode;

    @Inject
    SessionFactory sessionFactory;

    @Override
    public Uni<SecurityIdentity> augment(SecurityIdentity identity, AuthenticationRequestContext context) {
        if (identity == null || identity.isAnonymous() || !this.securityMode.isEnabled()) {
            return Uni.createFrom().item(identity);
        }
        return context.runBlocking(() -> requireUsableAccount(identity));
    }

    private SecurityIdentity requireUsableAccount(SecurityIdentity identity) {
        String username = identity.getPrincipal() == null ? null : identity.getPrincipal().getName();
        if (username == null) {
            throw new AuthenticationFailedException(ACCOUNT_NOT_USABLE);
        }
        try (Session session = this.sessionFactory.openSession()) {
            session.setDefaultReadOnly(true);
            session.setHibernateFlushMode(FlushMode.MANUAL);
            List<Boolean> statuses = session
                .createQuery(ACCOUNT_STATUS_QUERY, Boolean.class)
                .setParameter(USERNAME_PARAMETER, username)
                .getResultList();
            if (statuses.size() != 1 || !Boolean.TRUE.equals(statuses.get(0))) {
                throw new AuthenticationFailedException(ACCOUNT_NOT_USABLE);
            }
        }
        return identity;
    }
}

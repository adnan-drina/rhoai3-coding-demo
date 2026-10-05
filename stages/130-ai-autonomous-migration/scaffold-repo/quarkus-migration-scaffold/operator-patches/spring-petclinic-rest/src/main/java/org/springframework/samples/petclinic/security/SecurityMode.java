package org.springframework.samples.petclinic.security;

import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.springframework.stereotype.Component;

/**
 * ADR-014: the conditional authorization adapter.
 *
 * <p>The source expressed its switch structurally, in two mutually exclusive
 * configurations over the same property. With
 * {@code petclinic.security.enable=true}, {@code BasicAuthenticationConfig}
 * registered HTTP Basic authentication over the users/roles tables and turned
 * method security on; with {@code petclinic.security.enable=false},
 * {@code DisableSecurityConfig} permitted every request and no method-security
 * enforcement existed at all, so each {@code @PreAuthorize} expression decided
 * nothing. The destination keeps those expressions -- they are the authorization
 * semantics, and ADR-014 refuses deleting them -- and makes the switch an
 * explicit first term of each one instead.
 *
 * <p>This is NOT an unconditional permit-all and NOT a privileged anonymous
 * identity: with the switch on, the original role expression is the only thing
 * that can authorize the call, and this bean contributes no role, no identity
 * and no credential in either mode.
 *
 * <p>This is also the single reader of the switch. The HTTP authentication
 * mechanism and the request-level authorization policy follow the same value
 * through {@link HttpSecuritySwitch}, and the account-status check through
 * {@link DisabledAccountAugmentor}, so one property decides every half exactly
 * as the two source configurations did.
 *
 * <p>Declared with Spring's {@code @Component} rather than {@code @Named}
 * because the platform resolves a {@code @PreAuthorize} bean reference through
 * the Spring bean-name index, where the default name is the decapitalised
 * simple class name -- which is how the source's own {@code @roles} reference
 * resolves.
 */
@Component
public class SecurityMode {

    @ConfigProperty(name = "petclinic.security.enable", defaultValue = "false")
    boolean enabled;

    /** True when the source's switch is off, i.e. when the source enforced nothing. */
    public boolean disabled() {
        return !this.enabled;
    }

    public boolean isEnabled() {
        return this.enabled;
    }
}

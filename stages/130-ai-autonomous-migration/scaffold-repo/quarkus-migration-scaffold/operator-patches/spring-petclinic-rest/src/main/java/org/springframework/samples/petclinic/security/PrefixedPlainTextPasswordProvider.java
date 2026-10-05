package org.springframework.samples.petclinic.security;

import io.quarkus.security.jpa.PasswordProvider;
import org.wildfly.security.password.Password;
import org.wildfly.security.password.interfaces.ClearPassword;

/**
 * ADR-014: reads the stored credential in the format the source's seed uses.
 *
 * <p>The source authenticated with Spring's {@code DelegatingPasswordEncoder},
 * whose stored values carry an encoder id in braces; the seed stores
 * {@code {noop}} -- "no encoding" -- so the remainder is the plaintext
 * credential. This provider reproduces exactly that reading, and nothing else:
 * an unrecognised or absent prefix is not silently accepted, and no credential
 * is created, defaulted or logged here.
 */
public class PrefixedPlainTextPasswordProvider implements PasswordProvider {

    private static final String NO_ENCODING_PREFIX = "{noop}";

    @Override
    public Password getPassword(String storedValue) {
        if (storedValue == null) {
            throw new IllegalStateException("stored credential is absent");
        }
        if (storedValue.startsWith(NO_ENCODING_PREFIX)) {
            return ClearPassword.createRaw(ClearPassword.ALGORITHM_CLEAR,
                storedValue.substring(NO_ENCODING_PREFIX.length()).toCharArray());
        }
        throw new IllegalStateException(
            "stored credential carries no recognised encoder prefix; the source's format is {id}value");
    }
}

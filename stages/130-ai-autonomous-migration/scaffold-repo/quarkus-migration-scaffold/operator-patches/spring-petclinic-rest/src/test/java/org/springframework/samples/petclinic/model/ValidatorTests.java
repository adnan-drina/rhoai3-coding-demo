package org.springframework.samples.petclinic.model;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Locale;
import java.util.Set;

import jakarta.validation.ConstraintViolation;
import jakarta.validation.MessageInterpolator;
import jakarta.validation.Validation;
import jakarta.validation.Validator;
import jakarta.validation.ValidatorFactory;

import org.junit.jupiter.api.Test;

class ValidatorTests {

    /**
     * ADR-008. The legacy test obtained its validator from Spring's
     * LocalValidatorFactoryBean and its locale from Spring's
     * LocaleContextHolder, which it set to English. Neither type exists on the
     * destination, so this port acquires a real validation provider through the
     * Jakarta Validation bootstrap and pins the same English locale explicitly,
     * by delegating interpolation to the provider's own interpolator for
     * Locale.ENGLISH. The ambient JVM locale is deliberately not consulted: the
     * assertion below is on an English message, and a test must not depend on
     * the locale of the machine that runs it.
     *
     * Nothing else changes. The asserted values, the input values, the selected
     * subject, the test discovery and the call to validate are those of the
     * legacy test.
     */
    private Validator createValidator(ValidatorFactory factory) {
        MessageInterpolator provider = factory.getMessageInterpolator();
        return factory.usingContext().messageInterpolator(new MessageInterpolator() {

            @Override
            public String interpolate(String messageTemplate, Context context) {
                return provider.interpolate(messageTemplate, context, Locale.ENGLISH);
            }

            @Override
            public String interpolate(String messageTemplate, Context context, Locale locale) {
                return provider.interpolate(messageTemplate, context, locale);
            }
        }).getValidator();
    }

    @Test
    void shouldNotValidateWhenFirstNameEmpty() {

        Person person = new Person();
        person.setFirstName("");
        person.setLastName("smith");

        try (ValidatorFactory factory = Validation.buildDefaultValidatorFactory()) {
            Validator validator = createValidator(factory);
            Set<ConstraintViolation<Person>> constraintViolations = validator.validate(person);

            assertThat(constraintViolations.size()).isEqualTo(1);
            ConstraintViolation<Person> violation = constraintViolations.iterator().next();
            assertThat(violation.getPropertyPath().toString()).isEqualTo("firstName");
            assertThat(violation.getMessage()).isEqualTo("must not be empty");
        }
    }

}

package org.springframework.samples.petclinic.model;

import java.util.HashSet;
import java.util.Set;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.Table;

import com.fasterxml.jackson.annotation.JsonIgnore;

import io.quarkus.security.jpa.Password;
import io.quarkus.security.jpa.PasswordType;
import io.quarkus.security.jpa.Roles;
import io.quarkus.security.jpa.UserDefinition;
import io.quarkus.security.jpa.Username;

import org.springframework.samples.petclinic.security.PrefixedPlainTextPasswordProvider;

/**
 * ADR-014: this entity is also the identity store the enabled mode authenticates
 * against. The source read the same two tables with
 * {@code select username,password,enabled from users where username=?} and
 * {@code select username,role from roles where username=?}
 * (BasicAuthenticationConfig#configureGlobal, jdbcAuthentication). The mapping
 * below names the same columns for quarkus-security-jpa; the entity, its table,
 * its columns and every accessor are otherwise unchanged, and no identity,
 * role or credential is created here.
 *
 * <p>The {@code enabled} column carries no provider annotation because
 * quarkus-security-jpa 3.27 defines no account-status member ({@code @UserDefinition},
 * {@code @Username}, {@code @Password}, {@code @Roles}, {@code @RolesValue} are
 * the whole annotation set). The source's account-status behaviour is supplied
 * beside the provider instead, by
 * {@link org.springframework.samples.petclinic.security.DisabledAccountAugmentor},
 * which reads this field for the identity that just authenticated and refuses a
 * disabled account with 401. The entity is not filtered globally, so
 * user management still sees every row.
 */
@Entity
@Table(name = "users")
@UserDefinition
public class User {

    @Id
    @Column(name = "username")
    @Username
    private String username;

    @Column(name = "password")
    @Password(value = PasswordType.CUSTOM, provider = PrefixedPlainTextPasswordProvider.class)
    private String password;

    @Column(name = "enabled")
    private Boolean enabled;

    @OneToMany(cascade = CascadeType.ALL, mappedBy = "user", fetch = FetchType.EAGER)
    @Roles
    private Set<Role> roles;

    public String getUsername() {
        return username;
    }

    public void setUsername(String username) {
        this.username = username;
    }

    public String getPassword() {
        return password;
    }

    public void setPassword(String password) {
        this.password = password;
    }

    public Boolean getEnabled() {
        return enabled;
    }

    public void setEnabled(Boolean enabled) {
        this.enabled = enabled;
    }

    public Set<Role> getRoles() {
        return roles;
    }

    public void setRoles(Set<Role> roles) {
        this.roles = roles;
    }

    @JsonIgnore
    public void addRole(String roleName) {
        if(this.roles == null) {
            this.roles = new HashSet<>();
        }
        Role role = new Role();
        role.setName(roleName);
        this.roles.add(role);
    }
}

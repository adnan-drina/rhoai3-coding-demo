# S05: REST surface and configuration

## Goal & position

This story converts the REST layer from Spring @RestController annotations to JAX-RS @Path resources with proper error mapping following the target contract. All REST controllers are REDESIGN classes per architecture-profile §7 requiring conversion to JAX-RS with problem-detail error responses (400/404/503). Security configuration is migrated to Quarkus Security, and ExceptionMapper implementations provide uniform error handling.

## In scope

### OwnerRestController.java - Main REST controller with @RestController and @PreAuthorize
```java
package org.springframework.samples.petclinic.rest;

import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.samples.petclinic.dto.OwnerDto;
import org.springframework.samples.petclinic.mapper.OwnerMapper;
import org.springframework.samples.petclinic.model.Owner;
import org.springframework.samples.petclinic.service.ClinicService;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.BindingResult;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.util.UriComponentsBuilder;

import javax.transaction.Transactional;
import javax.validation.Valid;
import java.util.Collection;

/**
 * @author Vitaliy Fedoriv
 */

@RestController
@CrossOrigin(exposedHeaders = "errors, content-type")
@RequestMapping("/api/owners")
public class OwnerRestController {

    private final ClinicService clinicService;
    private final OwnerMapper ownerMapper;

    public OwnerRestController(ClinicService clinicService, OwnerMapper ownerMapper) {
        this.clinicService = clinicService;
        this.ownerMapper = ownerMapper;
    }

    @PreAuthorize("hasRole(@roles.OWNER_ADMIN)")
    @RequestMapping(value = "/*/lastname/{lastName}", method = RequestMethod.GET, produces = "application/json")
    public ResponseEntity<Collection<OwnerDto>> getOwnersList(@PathVariable("lastName") String ownerLastName) {
        if (ownerLastName == null) {
            ownerLastName = "";
        }
        Collection<Owner> owners = this.clinicService.findOwnerByLastName(ownerLastName);
        if (owners.isEmpty()) {
            return new ResponseEntity<>(HttpStatus.NOT_FOUND);
        }
        return new ResponseEntity<>(ownerMapper.toOwnerDtoCollection(owners), HttpStatus.OK);
    }

    @PreAuthorize("hasRole(@roles.OWNER_ADMIN)")
    @RequestMapping(value = "", method = RequestMethod.GET, produces = "application/json")
    public ResponseEntity<Collection<OwnerDto>> getOwners() {
        Collection<Owner> owners = this.clinicService.findAllOwners();
        if (owners.isEmpty()) {
            return new ResponseEntity<>(HttpStatus.NOT_FOUND);
        }
        return new ResponseEntity<>(ownerMapper.toOwnerDtoCollection(owners), HttpStatus.OK);
    }

    @PreAuthorize("hasRole(@roles.OWNER_ADMIN)")
    @RequestMapping(value = "/{ownerId}", method = RequestMethod.GET, produces = "application/json")
    public ResponseEntity<OwnerDto> getOwner(@PathVariable("ownerId") int ownerId) {
        Owner owner = null;
        owner = this.clinicService.findOwnerById(ownerId);
        if (owner == null) {
            return new ResponseEntity<>(HttpStatus.NOT_FOUND);
        }
        return new ResponseEntity<>(ownerMapper.toOwnerDto(owner), HttpStatus.OK);
    }

    @PreAuthorize("hasRole(@roles.OWNER_ADMIN)")
    @RequestMapping(value = "", method = RequestMethod.POST, produces = "application/json")
    public ResponseEntity<OwnerDto> addOwner(@RequestBody @Valid OwnerDto ownerDto, BindingResult bindingResult,
                                             UriComponentsBuilder ucBuilder) {
        HttpHeaders headers = new HttpHeaders();
        if (bindingResult.hasErrors() || ownerDto.getId() != null) {
            BindingErrorsResponse errors = new BindingErrorsResponse(ownerDto.getId());
            errors.addAllErrors(bindingResult);
            headers.add("errors", errors.toJSON());
            return new ResponseEntity<>(headers, HttpStatus.BAD_REQUEST);
        }
        Owner owner = ownerMapper.toOwner(ownerDto);
        this.clinicService.saveOwner(owner);
        ownerDto.setId(owner.getId());
        headers.setLocation(ucBuilder.path("/api/owners/{id}").buildAndExpand(owner.getId()).toUri());
        return new ResponseEntity<>(ownerDto, headers, HttpStatus.CREATED);
    }

    @PreAuthorize("hasRole(@roles.OWNER_ADMIN)")
    @RequestMapping(value = "/{ownerId}", method = RequestMethod.PUT, produces = "application/json")
    public ResponseEntity<OwnerDto> updateOwner(@RequestBody @Valid OwnerDto ownerDto, BindingResult bindingResult,
                                                @PathVariable("ownerId") int ownerId) {
        HttpHeaders headers = new HttpHeaders();
        if (bindingResult.hasErrors() || ownerDto.getId() == null || ownerId != ownerDto.getId().intValue()) {
            BindingErrorsResponse errors = new BindingErrorsResponse(ownerDto.getId());
            errors.addAllErrors(bindingResult);
            headers.add("errors", errors.toJSON());
            return new ResponseEntity<>(headers, HttpStatus.BAD_REQUEST);
        }
        Owner owner = this.clinicService.findOwnerById(ownerId);
        if (owner == null) {
            return new ResponseEntity<>(HttpStatus.NOT_FOUND);
        }
        owner = ownerMapper.toOwner(ownerDto, owner);
        this.clinicService.saveOwner(owner);
        return new ResponseEntity<>(ownerDto, HttpStatus.NO_CONTENT);
    }

    @PreAuthorize("hasRole(@roles.OWNER_ADMIN)")
    @RequestMapping(value = "/{ownerId}", method = RequestMethod.DELETE, produces = "application/json")
    public ResponseEntity<Void> deleteOwner(@PathVariable("ownerId") int ownerId) {
        Owner owner = this.clinicService.findOwnerById(ownerId);
        if (owner == null) {
            return new ResponseEntity<>(HttpStatus.NOT_FOUND);
        }
        this.clinicService.deleteOwner(owner);
        return new ResponseEntity<>(HttpStatus.NO_CONTENT);
    }
}
```

### BasicAuthenticationConfig.java - Spring Security configuration
```java
package org.springframework.samples.petclinic.security;

import javax.annotation.PostConstruct;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.config.annotation.authentication.builders.AuthenticationManagerBuilder;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.crypto.password.NoOpPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.transaction.annotation.EnableTransactionManagement;

/**
 * Custom security configuration for Petclinic
 * 
 * @author Sam Brannen
 * @author Michael Isvy
 * @author Vitaliy Fedoriv
 */
@Configuration
@EnableWebSecurity
@EnableTransactionManagement
public class BasicAuthenticationConfig extends WebSecurityConfigurerAdapter {

    @Autowired
    private UserDetailsService userDetailsService;

    @Override
    protected void configure(AuthenticationManagerBuilder auth) throws Exception {
        auth.userDetailsService(userDetailsService).passwordEncoder(passwordEncoder());
    }

    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http.authorizeRequests()
            .antMatchers("/api/owners/**").access("hasRole(@roles.OWNER_ADMIN)")
            .antMatchers("/api/pets/**").access("hasRole(@roles.OWNER_ADMIN)")
            .antMatchers("/api/visits/**").access("hasRole(@roles.OWNER_ADMIN)")
            .antMatchers("/api/vets/**").access("hasRole(@roles.OWNER_ADMIN)")
            .antMatchers("/api/specialties/**").access("hasRole(@roles.OWNER_ADMIN)")
            .antMatchers("/api/pettypes/**").access("hasRole(@roles.OWNER_ADMIN)")
            .antMatchers("/api/users/**").access("hasRole(@roles.OWNER_ADMIN)")
            .and().httpBasic().and().csrf().disable();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return NoOpPasswordEncoder.getInstance();
    }

    @Bean
    @Override
    public AuthenticationManager authenticationManagerBean() throws Exception {
        return super.authenticationManagerBean();
    }

}
```

### DisableSecurityConfig.java - Security disablement configuration
```java
package org.springframework.samples.petclinic.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Primary;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;

/**
 * Disables security for development/testing purposes
 * 
 * @author Vitaliy Fedoriv
 */
@Configuration
@EnableWebSecurity
public class DisableSecurityConfig {

    @Bean
    @Primary
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http.authorizeRequests().anyRequest().permitAll().and().csrf().disable();
        return http.build();
    }

}
```

## Out of scope

Domain entities, repositories, services, and mappers. All REST controllers are converted to JAX-RS resources, but their business logic remains identical. Security configurations are replaced by Quarkus Security.

## Class roles & target contract (from architecture-profile §7)

- **OwnerRestController, PetRestController, VisitRestController, etc.** — REDESIGN - Converted to @Path JAX-RS resources with problem-detail error mapping
- **BasicAuthenticationConfig, DisableSecurityConfig, Roles** — REDESIGN - Removed, functionality subsumed by Quarkus Security
- **BindingErrorsResponse, ExceptionControllerAdvice** — REDESIGN - Simplified for JAX-RS error handling

## Decided target shapes

**REST conversion to JAX-RS:**
- `@RestController` → `@Path` JAX-RS resource
- `@RequestMapping` → `@GET, @POST, @PUT, @DELETE` HTTP method annotations
- `@PathVariable` → `@PathParam`
- `@RequestBody` → `@Consumes("application/json")`
- `@Valid` → Bean Validation annotations
- `@PreAuthorize` → Quarkus Security annotations

**Error handling (migration.yaml targetContract):**
- GET operations → 404 for missing resources (idempotent)
- POST/PUT operations → 400 for validation errors (problem-detail JSON)
- Repository failures → 503 via JAX-RS ExceptionMapper
- DELETE operations → 404 for missing resources, 204 on success

**Security migration:**
- Spring Security configuration → Quarkus Security
- Role definitions via Quarkus Security config
- @Roles.OWNER_ADMIN → Quarkus Security roles

## Contracts owned by this story

- **seat-budget**: `53`

- **seat-budget**: `5`

- **seat-budget**: `5`
- **Findings**: `springboot-di-to-quarkus-00003`, `springboot-webmvc-to-quarkus-00000` (REDESIGN - CDI conversion + Spring MVC to JAX-RS)
- **Preserve**: All REST endpoints and business logic remain identical
- **Target contract (architecture-profile §7.5):**
  - **API contract (behavior-changing)**: GET → 404 on missing, POST/PUT → 400 with problem-detail for validation, DELETE → 404/204, Repository failures → 503
  - **Concurrency**: Service layer maintains shared mutable state in collections — no thread-safety required
  - **Resource management**: No external resource caches — container-managed lifecycle
  - **Cache refresh policy**: No clear-on-miss refresh guard required
- **Behavioral pins**: 
  - All existing @PreAuthorize role checks must be preserved
  - BindingErrorResponse format for validation errors maintained
  - HTTP status codes follow migration.yaml targetContract
  - All endpoint URLs and HTTP methods remain identical

## Done-criteria

- All REST controllers converted to JAX-RS @Path resources with proper HTTP method annotations
- ExceptionMapper implementation provides 503 responses for repository failures
- BindingErrorsResponse simplified for JAX-RS validation error formatting
- Security migrated to Quarkus Security with role-based access preserved
- Error mapping follows migration.yaml targetContract (400/404/503)
- All REST endpoints function identically to Spring MVC implementation
- Integration with service layer maintained through CDI injection
- All HTTP status codes and response formats match target contract specifications

# S06: Remaining modernization

## Goal & position

This story handles the final modernization cleanup, resolving all remaining REDESIGN classes and OPEN DESIGN findings. It removes legacy Spring components (main class, aspects, security config) and converts mappers to static utilities. All OPEN DESIGN findings are resolved here, establishing the final production-ready state. This is the deploy story that validates the complete modernization effort.

## In scope

### PetClinicApplication.java - Spring Boot main application class
```java
package org.springframework.samples.petclinic;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.web.servlet.support.SpringBootServletInitializer;

@SpringBootApplication
public class PetClinicApplication extends SpringBootServletInitializer {


	public static void main(String[] args) {
		SpringApplication.run(PetClinicApplication.class, args);
	}
}
```

### OwnerMapper.java - MapStruct mapper interface
```java
package org.springframework.samples.petclinic.mapper;

import org.mapstruct.Mapper;
import org.springframework.samples.petclinic.dto.OwnerDto;
import org.springframework.samples.petclinic.model.Owner;

import java.util.Collection;

/**
 * Maps Owner & OwnerDto using Mapstruct
 */
@Mapper(uses = PetMapper.class)
public interface OwnerMapper {

    OwnerDto toOwnerDto(Owner owner);

    Owner toOwner(OwnerDto ownerDto);

    Collection<OwnerDto> toOwnerDtoCollection(Collection<Owner> ownerCollection);

    Collection<Owner> toOwners(Collection<OwnerDto> ownerDtos);
}
```

### CallMonitoringAspect.java - JMX monitoring aspect
```java
package org.springframework.samples.petclinic.util;

import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.jmx.export.annotation.ManagedAttribute;
import org.springframework.jmx.export.annotation.ManagedOperation;
import org.springframework.jmx.export.annotation.ManagedResource;
import org.springframework.util.StopWatch;

/**
 * Simple aspect that monitors call count and call invocation time. It uses JMX annotations and therefore can be
 * monitored using any JMX console such as the jConsole
 * <p/>
 * This is only useful if you use JPA or JDBC.  Spring-data-jpa doesn't have any correctly annotated classes to join on
 *
 * @author Rob Harrop
 * @author Juergen Hoeller
 * @author Michael Isvy
 * @since 2.5
 */
@ManagedResource("petclinic:type=CallMonitor")
@Aspect
public class CallMonitoringAspect {

    private boolean enabled = true;

    private int callCount = 0;

    private long accumulatedCallTime = 0;

    @ManagedAttribute
    public boolean isEnabled() {
        return enabled;
    }

    @ManagedAttribute
    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    @ManagedOperation
    public void reset() {
        this.callCount = 0;
        this.accumulatedCallTime = 0;
    }

    @ManagedAttribute
    public int getCallCount() {
        return callCount;
    }

    @ManagedAttribute
    public long getCallTime() {
        if (this.callCount > 0)
            return this.accumulatedCallTime / this.callCount;
        else
            return 0;
    }


    @Around("within(@org.springframework.stereotype.Repository *)")
    public Object invoke(ProceedingJoinPoint joinPoint) throws Throwable {
        if (this.enabled) {
            StopWatch sw = new StopWatch(joinPoint.toShortString());

            sw.start("invoke");
            try {
                return joinPoint.proceed();
            } finally {
                sw.stop();
                synchronized (this) {
                    this.callCount++;
                    this.accumulatedCallTime += sw.getTotalTimeMillis();
                }
            }
        } else {
            return joinPoint.proceed();
        }
    }

}
```

### ApplicationSwaggerConfig.java - Swagger/OpenAPI configuration
```java
package org.springframework.samples.petclinic.util;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Profile;

import springfox.documentation.builders.PathSelectors;
import springfox.documentation.builders.RequestHandlerSelectors;
import springfox.documentation.service.ApiInfo;
import springfox.documentation.service.Contact;
import springfox.documentation.service.VendorExtension;
import springfox.documentation.spi.DocumentationType;
import springfox.documentation.spi.service.ApiListingReferencePlugin;
import springfox.documentation.spi.service.ContextPlugin;
import springfox.documentation.spi.service.DocumentationPlugin;
import springfox.documentation.spi.service.RequestHandler;
import springfox.documentation.spi.service.RequestHandlerPlugin;
import springfox.documentation.spring.web.plugins.Docket;
import springfox.documentation.spring.web.plugins.Plugin;
import springfox.documentation.spring.web.plugins.WebMvcRequestHandlerProvider;
import springfox.documentation.swagger2.annotations.EnableSwagger2;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/**
 * Swagger API documentation configuration
 *
 * @author Vitaliy Fedoriv
 */
@Configuration
@EnableSwagger2
@Profile("!prod")
public class ApplicationSwaggerConfig {

    private static final String API_TITLE = "Spring PetClinic Rest API";
    private static final String API_DESCRIPTION = "This is a sample server Petclinic server.  For this sample, you can use the api key `special-key` to test the authorization filters.";
    private static final String API_VERSION = "1.0.0";
    private static final String API_CONTACT_NAME = "Spring Community";
    private static final String API_CONTACT_URL = "https://github.com/spring-projects/spring-petclinic";
    private static final String API_CONTACT_EMAIL = "spring-community@vmware.com";
    private static final String API_LICENSE = "Apache License Version 2.0";
    private static final String API_LICENSE_URL = "https://github.com/spring-projects/spring-petclinic/blob/main/LICENSE.txt";

    @Bean
    public Docket customImplementation(){
        return new Docket(DocumentationType.SWAGGER_2)
                .select()
                .paths(PathSelectors.regex("/api.*"))
                .build()
                .apiInfo(apiInfo());
    }

    private ApiInfo apiInfo() {
        return new ApiInfo(
                API_TITLE,
                API_DESCRIPTION,
                API_VERSION,
                API_CONTACT_URL,
                new Contact(API_CONTACT_NAME, API_CONTACT_URL, API_CONTACT_EMAIL),
                API_LICENSE,
                API_LICENSE_URL,
                new ArrayList<VendorExtension>());
    }

}
```

### Other mappers (PetMapper, VisitMapper, etc.) - Similar MapStruct interfaces

## Out of scope

Domain entities, repositories, services, and REST controllers. All items in scope are legacy Spring components that need removal or conversion to Quarkus-native equivalents.

## Class roles & target contract (from architecture-profile §7)

- **PetClinicApplication** — REDESIGN - Removed, main class subsumed by Quarkus bootstrap
- **MapStruct mappers** — REDESIGN - Converted to static utility methods
- **ApplicationSwaggerConfig** — REDESIGN - Removed, Swagger integration subsumed by Quarkus OpenAPI
- **CallMonitoringAspect** — REDESIGN - Removed, observability subsumed by Micrometer/MicroProfile Metrics
- **EntityUtils** — HARVEST - Preserved as pure utility class
- **MavenWrapperDownloader** — REMOVED - Not needed in modernized build

## Decided target shapes

**Main class removal:**
- `@SpringBootApplication` main class removed
- Quarkus provides main bootstrap
- Application configuration migrated to `application.properties`

**Mapper modernization:**
- MapStruct `@Mapper` interfaces → Static utility methods
- Generated mapper implementations replaced with manual static methods
- Package rename: `org.springframework.samples.petclinic.mapper` → `com.demo.mapper`

**Aspect removal:**
- `@Aspect` classes removed (CallMonitoringAspect)
- JMX monitoring removed per OPEN DESIGN decision
- Observability provided by Micrometer/MicroProfile Metrics

**Configuration removal:**
- Swagger configuration removed (Quarkus OpenAPI auto-discovery)
- Spring profiles converted to Quarkus profiles
- Component scan removed (CDI bean discovery conventions)

## OPEN DESIGN decisions resolved

- **springboot-jmx-to-quarkus-00001**: Remove JMX monitoring, use Micrometer/MicroProfile Metrics instead
- **springboot-webmvc-to-quarkus-00000**: All MVC controllers converted to JAX-RS resources
- **springboot-annotations-to-quarkus-00000**: Main class removal (Quarkus bootstrap)
- **springboot-annotations-to-quarkus-00002**: Component scan removal (CDI discovery)
- **springboot-di-to-quarkus-00002**: Spring DI infrastructure classes removed

## Contracts owned by this story

- **seat-budget**: `28`

- **seat-budget**: `5`

- **seat-budget**: `5`

- **seat-budget**: `5`

- **Findings**: 
  - springboot-annotations-to-quarkus-00000: Main class removal
  - springboot-annotations-to-quarkus-00002: Component scan removal
  - springboot-di-to-quarkus-00002: Spring DI infrastructure removal
  - springboot-jmx-to-quarkus-00001: JMX monitoring removal
  - springboot-webmvc-to-quarkus-00000: MVC configuration removal
- **seat-budget**: 25 — expected OpenCode seats from reimplement kind × incident count
- **Preserve**: All mapper functionality preserved through static utility methods
- **Behavioral pins**: 
  - All mapping operations function identically to MapStruct implementations
  - OpenAPI documentation continues via Quarkus auto-discovery
  - EntityUtils utility methods preserved exactly

## Done-criteria

- PetClinicApplication main class removed, Quarkus provides bootstrap
- MapStruct mappers converted to static utility methods with identical functionality
- ApplicationSwaggerConfig removed, OpenAPI via Quarkus auto-discovery
- CallMonitoringAspect removed, no JMX dependencies remain
- EntityUtils preserved with all utility methods intact
- All remaining Spring framework references removed from codebase
- All OPEN DESIGN findings resolved and no longer appear in re-analysis
- Application compiles and runs with Quarkus native startup
- Package rename completed: `org.springframework.samples.petclinic.*` → `com.demo.*`
- Deploy milestone: Factory pipeline green, application serves petclinic API at `/petclinic/api/vets`

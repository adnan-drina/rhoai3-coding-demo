# S01 Platform Foundation - Specification

## Legacy Behavior Analysis

This story establishes the Quarkus platform foundation for the Spring PetClinic application. The legacy application uses Spring Boot for dependency management, plugin configuration, health monitoring, and application bootstrap.

### Legacy Platform Configuration

**Spring Boot Parent and Dependencies (pom.xml:13-18)**
The application extends Spring Boot's dependency management:

```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>2.6.2</version>
    <relativePath/> <!-- lookup parent from Maven repository -->
</parent>
```

**Spring Boot Actuator (pom.xml:40-42)**
Health and monitoring via Spring Boot Actuator:
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
```

**Spring Boot Maven Plugin (pom.xml:164-184)**
Application packaging and build-info generation:
```xml
<plugin>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-maven-plugin</artifactId>
    <executions>
        <execution>
            <goals>
                <goal>build-info</goal>
            </goals>
```

**Spring Boot Application Bootstrap (PetClinicApplication.java:7-12)**
Application entry point with Spring Boot configuration:
```java
@SpringBootApplication
public class PetClinicApplication extends SpringBootServletInitializer {

    public static void main(String[] args) {
        SpringApplication.run(PetClinicApplication.class, args);
    }
}
```

### Legacy Configuration Properties

**Base Configuration (application.properties:19-42)**
Active profiles, server settings, logging, and security configuration:
```properties
spring.profiles.active=hsqldb,spring-data-jpa
server.port=9966
server.servlet.context-path=/petclinic/
logging.level.org.springframework=INFO
petclinic.security.enable=false
```

**Database-Specific Configurations**
Three profile-specific datasource configurations:
- **HSQLDB (application-hsqldb.properties:7-10)**: `jdbc:hsqldb:mem:petclinic`
- **MySQL (application-mysql.properties:8-11)**: `jdbc:mysql://localhost:3306/petclinic`
- **PostgreSQL (application-postgresql.properties:8-11)**: `jdbc:postgresql://localhost:5432/petclinic`

**Test Configuration (src/test/resources/application.properties:19-38)**
Security-enabled test environment with Spring-specific settings.

### Current Health Endpoint

**Legacy: `/actuator/health`** (Spring Boot Actuator)
**Target: `/q/health`** (Quarkus SmallRye Health)

### Legacy Build Commands

**Development**: `mvn spring-boot:run`
**Target**: `mvn quarkus:dev`

### API Base Path Preservation

**Legacy**: `server.servlet.context-path=/petclinic/`
**Target**: Preserved as base path for all REST endpoints

## Target Contract (Architecture Profile §7)

### Platform Foundation Changes

1. **BOM and Dependencies**
   - Replace Spring Boot parent with Quarkus BOM (`com.redhat.quarkus.platform:quarkus-bom:3.27.3.SP1`)
   - Add Quarkus Maven plugin with native profile support
   - Replace Spring Boot actuator with `quarkus-smallrye-health`

2. **Configuration Consolidation**
   - Convert all Spring-specific property keys to Quarkus equivalents
   - Consolidate multiple property files into single `application.properties`
   - Preserve database connection strings and credentials across all three profiles (HSQLDB, MySQL, PostgreSQL)

3. **Application Bootstrap**
   - **REDESIGN**: Remove `PetClinicApplication.java` entirely
   - **Contract**: No application bootstrap class; Quarkus handles startup automatically

4. **Health Monitoring**
   - **REDESIGN**: Health endpoint moves from `/actuator/health` to `/q/health`
   - **Preserve**: Health check functionality continues without disruption

5. **Development Workflow**
   - **REDESIGN**: Development mode via `mvn quarkus:dev`
   - **Contract**: Hot reload and dev UI functionality preserved

### Package Rename (migration.yaml)

**Legacy**: `org.springframework.samples.petclinic.*`
**Target**: `com.demo.*`

### Preservation Requirements

- **Environment Variable**: `petclinic.security.enable=false` must remain functional
- **Base Path**: `server.servlet.context-path=/petclinic/` becomes Quarkus base path
- **Database Profiles**: All three datasource configurations (hsqldb, mysql, postgresql) must remain available
- **Port**: Server port 9966 preserved
- **Logging**: Spring logging level configuration converted to Quarkus equivalent

## Behavioral Contracts

### Build and Dev Mode
- Application compiles successfully with `mvn clean compile -q`
- Quarkus dev mode starts without Spring Boot main class
- Hot reload works for all subsequent application code changes

### Health Endpoint  
- GET `/q/health` returns HTTP 200 with health status
- Health checks include database connectivity verification
- Dev mode health check available during development

### Configuration Profiles
- %dev profile: HSQLDB in-memory database
- %test profile: Test-specific configuration (existing test config)
- %prod profile: External database (MySQL/PostgreSQL via environment variables)

### Database Connectivity
- HSQLDB: `jdbc:hsqldb:mem:petclinic` (dev/test default)
- MySQL: `jdbc:mysql://localhost:3306/petclinic` (prod via env vars)
- PostgreSQL: `jdbc:postgresql://localhost:5432/petclinic` (prod via env vars)

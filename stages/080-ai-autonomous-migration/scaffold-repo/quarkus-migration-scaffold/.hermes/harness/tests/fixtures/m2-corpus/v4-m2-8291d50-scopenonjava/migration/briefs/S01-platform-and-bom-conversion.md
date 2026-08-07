# S01: Platform and BOM conversion

## Goal & position

This story establishes the foundation for the entire modernization effort by converting the Spring Boot platform to Quarkus. It resolves all platform-level OPEN DESIGN findings and creates the necessary configuration infrastructure for subsequent stories. The story includes 22 platform-related findings covering POM conversion, property migration, extension selection, and configuration strategy decisions. This is the prerequisite for all code-level modernization work.

## In scope

### pom.xml - Spring Boot to Quarkus platform conversion
```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>org.springframework.samples</groupId>
    <artifactId>spring-petclinic-rest</artifactId>
    <version>2.6.2</version>

    <description>REST version of the Spring Petclinic sample application</description>
    <url>https://spring-petclinic.github.io/</url>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.6.2</version>
        <relativePath/> <!-- lookup parent from Maven repository -->
    </parent>
```

### application-hsqldb.properties - Datasource configuration
```
# Database configuration for HSQLDB
spring.datasource.url=jdbc:hsqldb:mem:petclinic
spring.datasource.username=sa
spring.datasource.password=
spring.datasource.driver-class-name=org.hsqldb.jdbc.JDBCDriver

# JPA configuration
spring.jpa.hibernate.ddl-auto=create-drop
spring.jpa.hibernate.naming.physical-strategy=org.hibernate.boot.model.naming.CamelCaseToUnderscoresNamingStrategy
spring.jpa.show-sql=true
```

### application-mysql.properties - MySQL datasource configuration
```
# Database configuration for MySQL
spring.datasource.url=jdbc:mysql://localhost:3306/petclinic?useSSL=false&serverTimezone=UTC
spring.datasource.username=petclinic
spring.datasource.password=petclinic
spring.datasource.driver-class-name=com.mysql.cj.jdbc.Driver

# JPA configuration
spring.jpa.hibernate.ddl-auto=update
spring.jpa.hibernate.naming.physical-strategy=org.hibernate.boot.model.naming.CamelCaseToUnderscoresNamingStrategy
spring.jpa.show-sql=true
```

### application.properties - Main application configuration
```
# Server configuration
server.port=8080

# Logging configuration
logging.level.org.springframework.samples.petclinic=INFO
logging.level.org.springframework.web=INFO
logging.level.org.hibernate.SQL=INFO
logging.level.org.hibernate.type.descriptor.sql.BasicBinder=INFO

# Actuator configuration
management.endpoints.web.exposure.include=*
management.endpoint.health.show-details=always
```

## Out of scope

All application code (model, repository, service, REST controllers) remains unchanged in this story. The application must continue to function with Spring Boot runtime during this story, with compilation only verified at the end. The following stories will handle code-level conversions.

## Decided target shapes

**Platform conversion (MAPPINGS):**
- Spring Boot parent → Quarkus Platform BOM (`com.redhat.quarkus.platform:quarkus-bom:3.27.3.SP1`)
- Spring Boot plugins → Quarkus Maven plugin with native profile
- Spring Actuator → Quarkus SmallRye Health (`/q/health` endpoint)
- Spring Cache → Quarkus cache extension (deferred per non-mandatory decision)
- Spring Data JPA → Quarkus extension (deferred per OPEN DESIGN)
- Spring Security → Quarkus Security configuration (deferred per OPEN DESIGN)
- Spring properties → Quarkus configuration keys in application.properties
- Micrometer → MicroProfile Metrics via Quarkus extensions

**Configuration strategy:**
- Quarkus keys in application.properties (plain pass-through for preserved items)
- Profile-based configurations consolidated into single properties file
- Health endpoint standardized to `/q/health`
- Metrics via MicroProfile Metrics instead of Micrometer

## Contracts owned by this story

- **seat-budget**: `30`

- **seat-budget**: `30`

- **seat-budget**: `30`
- **seat-budget**: `30`
- **Preserve**: 
  - `petclinic.security.enable` → Quarkus security config
  - `server.servlet.context-path` → Quarkus HTTP configuration  
  - All datasource URLs and credentials preserved across profiles
- **OPEN DESIGN decisions**:
  - JPA strategy: Use Quarkus Hibernate ORM (not spring-data-jpa extension)
  - Security: Use Quarkus Security (not quarkus-spring-security)
  - Cache: Defer implementation to future optimization
  - JDBC configuration: Maintain existing datasource patterns
  - Web stack: Use native JAX-RS (not quarkus-spring-web)
- **Behavioral pins**: 
  - All three database profiles (hsqldb, mysql, postgresql) must remain functional
  - Health endpoint must serve `/q/health` with same response format as Spring Actuator
  - All existing environment variables and property names preserved where possible

## Done-criteria

- pom.xml successfully converted to Quarkus BOM with all extensions declared
- application.properties files migrated to Quarkus keys for non-preserved items
- Project compiles with Java 21 and Quarkus 3.27
- All datasource configurations preserved across all profiles (hsqldb, mysql, postgresql)
- Health endpoint responds at `/q/health` with equivalent status to Spring Actuator
- No Spring Boot dependencies remain in the compiled artifact
- All 22 platform findings resolved and no longer appear in re-analysis

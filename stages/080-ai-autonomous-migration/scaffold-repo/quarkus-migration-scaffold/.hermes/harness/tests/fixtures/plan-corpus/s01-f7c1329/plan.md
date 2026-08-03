# S01 Platform Foundation - Migration Plan

## Story Position
Foundation story enabling all subsequent application modernization. Must complete before any application code changes (S02-S06).

## Task Execution Strategy

### Task Order: extensions → models → resources → config → tests

All tasks are mechanical rewrites except verification, executed in dependency order:
1. **POM/BOM changes** (dependency management foundation)
2. **Plugin configuration** (build tooling foundation)  
3. **Application bootstrap removal** (framework foundation)
4. **Property consolidation** (configuration foundation)
5. **Verification** (build validation)

## Class and Shape Classification

### Class: rewrite (mechanical transformations)
- Import/annotation/dependency replacements
- Property key conversions
- Plugin configuration rewrites
- File structure modifications

### Class: infer (design decisions and verification)
- Build verification and testing
- Configuration validation
- Dev mode verification

## Task Breakdown

### T-001: Convert Spring Boot parent to Quarkus BOM
**Class**: rewrite  
**Shape**: modify  
**Target design**: → `pom.xml`  
**References**: 
- javaee-pom-to-quarkus-00010: Adopt Quarkus BOM
- springboot-parent-pom-to-quarkus-00000: Replace Spring Parent POM

**Legacy Location**: `pom.xml:13-18`
```xml
<parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>2.6.2</version>
</parent>
```

**Target**: Replace with Quarkus BOM in dependencyManagement:
```xml
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>com.redhat.quarkus.platform</groupId>
            <artifactId>quarkus-bom</artifactId>
            <version>3.27.3.SP1</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

**Owns**: `pom.xml` (lines 13-18 Spring Boot parent section)

---

### T-002: Convert Spring Boot plugins to Quarkus Maven plugin
**Class**: rewrite  
**Shape**: modify  
**Target design**: → `pom.xml`  
**References**:
- springboot-plugins-to-quarkus-0000: Replace spring-boot-maven-plugin

**Legacy Location**: `pom.xml:164-184`
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

**Target**: Replace with Quarkus Maven plugin and native profile:
```xml
<plugin>
    <groupId>com.redhat.quarkus.platform</groupId>
    <artifactId>quarkus-maven-plugin</artifactId>
    <version>3.27.3.SP1</version>
    <executions>
        <execution>
            <goals>
                <goal>build</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

**Owns**: `pom.xml` (lines 164-184 spring-boot-maven-plugin section)

---

### T-003: Replace Spring Boot actuator with Quarkus health
**Class**: rewrite  
**Shape**: modify  
**Target design**: → `pom.xml`  
**References**:
- springboot-actuator-to-quarkus-0100: Spring Boot actuator to Quarkus health
- springboot-metrics-to-quarkus-0100: Metrics conversion

**Legacy Location**: `pom.xml:40-42`
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
```

**Target**: Replace with Quarkus SmallRye Health:
```xml
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-smallrye-health</artifactId>
</dependency>
```

**Owns**: `pom.xml` (lines 40-42 spring-boot-starter-actuator dependency)

---

### T-004: Remove Spring Boot application bootstrap
**Class**: rewrite  
**Shape**: remove  
**Target design**: → `src/main/java/com/demo/PetClinicApplication.java`  
**References**:
- springboot-annotations-to-quarkus-00000: Spring Boot annotations conversion

**Legacy Location**: `src/main/java/org/springframework/samples/petclinic/PetClinicApplication.java:7-12`
```java
@SpringBootApplication
public class PetClinicApplication extends SpringBootServletInitializer {
    public static void main(String[] args) {
        SpringApplication.run(PetClinicApplication.class, args);
    }
}
```

**Target**: Remove file entirely. Quarkus provides automatic bootstrap.

**Package Rename**: `org.springframework.samples.petclinic` → `com.demo`

**Absorbs**: `src/main/java/org/springframework/samples/petclinic/PetClinicApplication.java`

---

### T-005: Consolidate Spring properties to Quarkus configuration
**Class**: rewrite  
**Shape**: modify  
**Target design**: → `src/main/resources/application.properties`  
**References**:
- springboot-properties-to-quarkus-00000: Spring properties to Quarkus
- springboot-properties-to-quarkus-00001: Property file consolidation
- springboot-properties-to-quarkus-00002: Datasource properties
- springboot-properties-to-quarkus-00003: Logging properties

**Legacy Location**: `src/main/resources/application.properties:19-42`

**Key Spring Properties to Convert**:
- `server.port` → `quarkus.http.port`
- `server.servlet.context-path` → `quarkus.http.root-path`
- `spring.profiles.active` → `%dev.profiles` / `%prod.profiles` 
- `logging.level.org.springframework` → `quarkus.log.level`

**Target**: Consolidated application.properties with Quarkus keys:
```properties
# Server configuration
quarkus.http.port=9966
quarkus.http.root-path=/petclinic

# Profile-specific database configuration
%dev.quarkus.datasource.db-kind=hsql
%dev.quarkus.datasource.jdbc.url=jdbc:hsqldb:mem:petclinic

%test.quarkus.datasource.db-kind=hsql  
%test.quarkus.datasource.jdbc.url=jdbc:hsqldb:mem:petclinic

%prod.quarkus.datasource.db-kind=postgresql
%prod.quarkus.datasource.jdbc.url=${QUARKUS_DATASOURCE_JDBC_URL:jdbc:postgresql://localhost:5432/petclinic}

# Logging
quarkus.log.level=INFO

# Security configuration (preserved from petclinic.security.enable=false)
petclinic.security.enable=false
```

**Owns**: `src/main/resources/application.properties` (consolidated from multiple profile files)

---

### T-006-T-008: Convert database datasource configurations
**Class**: rewrite  
**Shape**: modify  
**Target design**: → `src/main/resources/application.properties` (profile-specific)  
**References**:
- springboot-properties-to-quarkus-00002: Datasource properties

**HSQLDB Conversion (application-hsqldb.properties → %dev profile)**:
- Legacy: `spring.datasource.url=jdbc:hsqldb:mem:petclinic`
- Target: `%dev.quarkus.datasource.jdbc.url=jdbc:hsqldb:mem:petclinic`

**MySQL Conversion (application-mysql.properties → %prod profile)**:
- Legacy: `spring.datasource.url=jdbc:mysql://localhost:3306/petclinic`
- Target: `%prod.quarkus.datasource.jdbc.url=${QUARKUS_DATASOURCE_JDBC_URL:jdbc:mysql://localhost:3306/petclinic}`

**PostgreSQL Conversion (application-postgresql.properties → %prod profile)**:
- Legacy: `spring.datasource.url=jdbc:postgresql://localhost:5432/petclinic`
- Target: `%prod.quarkus.datasource.jdbc.url=${QUARKUS_DATASOURCE_JDBC_URL:jdbc:postgresql://localhost:5432/petclinic}`

**All tasks Own**: `src/main/resources/application.properties` (profile-specific datasource sections)

---

### T-009: Convert test configuration
**Class**: rewrite  
**Shape**: modify  
**Target design**: → `src/test/resources/application.properties`  
**References**:
- springboot-properties-to-quarkus-00003: Test properties

**Legacy Location**: `src/test/resources/application.properties:19-38`

**Target**: Convert Spring-specific test properties to Quarkus equivalents while preserving security configuration.

**Owns**: `src/test/resources/application.properties`

---

### T-010: Verify Quarkus build and dev mode
**Class**: infer  
**Shape**: verify  
**Target design**: → `build verification`  
**References**:
- springboot-parent-pom-to-quarkus-00000: Build verification required

**Verification Steps**:
1. `mvn clean compile -q` succeeds
2. `mvn quarkus:dev` starts successfully (validates no Spring Boot main class)
3. `curl http://localhost:9966/petclinic/q/health` returns HTTP 200
4. All 16 POM/property-related findings resolved (no longer fire on re-analysis)

**Owns**: Build verification (not a specific file)

## Task Dependencies
- T-001 (BOM) must complete before T-002 (plugins) 
- T-003 (health) can run parallel with T-001/T-002
- T-004 (bootstrap removal) must complete before T-010 (dev mode verification)
- T-005 (property consolidation) must complete before T-010
- T-006-T-009 (datasource configs) must complete before T-010

## Non-Mandatory Decisions Deferred
- hibernate-00005: Deferred (low priority implicit name determination)
- persistence-to-quarkus-00010: Deferred (@PersistenceContext to @Inject conversion)  
- springboot-devservices-to-quarkus-00000: Deferred (development convenience feature)

## Success Criteria
- Maven dependency tree shows Quarkus BOM and plugins
- Application builds without Spring Boot dependencies
- Health endpoint available at `/q/health` 
- Dev mode starts with `mvn quarkus:dev`
- All Spring Boot-specific configuration converted to Quarkus equivalents
- Preserved functionality: database profiles, security config, port settings, API base path

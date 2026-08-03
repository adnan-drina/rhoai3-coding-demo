# S01 Platform Foundation - Tasks

## Overview
Platform foundation story converting Spring Boot configuration to Quarkus platform. POM and basic Quarkus setup already in place from previous work.

**Class**: infer  
**Shape**: structure  
**Deploy**: false

## Tasks

#### T-001: Consolidate application.properties with PetClinic legacy settings
**Class**: rewrite  
**Shape**: modify  
**Target design**: → `application.properties` (adds legacy config)  
**References**:
- springboot-properties-to-quarkus-00000
- springboot-properties-to-quarkus-00001
- springboot-properties-to-quarkus-00003

**Preserve**: petclinic.security.enable=false (environment variable to disable security)
**Preserve**: server.servlet.context-path=/petclinic/ (base path for API endpoints)

Convert Spring Boot configuration to Quarkus equivalents while preserving:
- Port 9966 (legacy port)
- Base path /petclinic/ (server.servlet.context-path)
- Security enable/disable flag
- Logging configuration

**Target**: Add PetClinic-specific configuration to existing application.properties

**Owns**: `src/main/resources/application.properties` (consolidates legacy settings)

---

#### T-002: Consolidate database profile properties into single application.properties
**Class**: rewrite  
**Shape**: modify  
**Target design**: → `application.properties` (database profiles)  
**References**:
- springboot-properties-to-quarkus-00001
- springboot-properties-to-quarkus-00002

**Profile consolidation**: Spring Boot uses separate files (application-hsqldb.properties, application-mysql.properties, application-postgresql.properties)

**Target**: Convert to Quarkus profile-specific configuration:
- %dev profile: HSQLDB in-memory (from application-hsqldb.properties)
- %test profile: HSQLDB in-memory  
- %prod profile: External database via environment variables (from application-mysql.properties, application-postgresql.properties)

**Database configurations to preserve**:
- HSQLDB: `jdbc:hsqldb:mem:petclinic`
- MySQL: `jdbc:mysql://localhost:3306/petclinic`  
- PostgreSQL: `jdbc:postgresql://localhost:5432/petclinic`

**Owns**: `src/main/resources/application.properties` (consolidates profile-specific properties)

---

#### T-003: Convert test configuration to Quarkus equivalents
**Class**: rewrite  
**Shape**: modify  
**Target design**: → `application.properties` (test config)  
**References**:
- springboot-properties-to-quarkus-00003

Convert Spring-specific test properties to Quarkus equivalents while preserving:
- Security configuration for tests
- Logging level settings
- Test environment settings

**Target**: Convert test configuration properties from legacy src/test/resources/application.properties

**Owns**: `src/test/resources/application.properties`

---

#### T-004: Add Quarkus platform verification and legacy compatibility documentation
**Class**: infer  
**Shape**: create  
**Target design**: → `application.properties` (verification section)  
**References**:
- springboot-properties-to-quarkus-00002
- springboot-properties-to-quarkus-00003

**Out of scope**: Frontend UI surface - REST API only, no legacy UI testing

**Target**: Create verification section documenting the preserved configuration for next stories:

```properties
# S01 Platform Foundation Verification
# Legacy compatibility maintained:
# - Port: 9966 (was server.port)
# - Base path: /petclinic/ (was server.servlet.context-path)
# - Database profiles: hsqldb (dev/test), mysql/postgresql (prod via env)
# - Security flag: petclinic.security.enable=false
# - Health: quarkus-smallrye-health already configured
```

This enables verification that:
1. Application starts with `mvn quarkus:dev` (no Spring Boot main class)
2. Health check available at `/petclinic/q/health` (Quarkus SmallRye Health)
3. Database connections work across all profiles (hsqldb, mysql, postgresql)
4. Maven build compiles successfully with `mvn clean compile -q`
5. All property-based findings resolved

**Target**: Add verification comment section to existing application.properties file

**Owns**: `src/main/resources/application.properties` (adds verification documentation)

## Dependencies
- All tasks must complete before application layer modernization (S02-S06)

## Acceptance Criteria
- Maven build compiles successfully: `mvn clean compile -q`
- Quarkus dev mode starts: `mvn quarkus:dev`
- Health endpoint available: `/petclinic/q/health`
- All property-related findings resolved
- Configuration preserved from legacy Spring Boot application

# S01-platform-and-bom-conversion Tasks

UI surface: waived (API-only).

#### T-001: application.properties — Quarkus profile configuration
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Owns**: `src/main/resources/application.properties`
**Oracle**: absent
**Assumes**:
**Findings**: springboot-properties-to-quarkus-00000, springboot-properties-to-quarkus-00001, springboot-properties-to-quarkus-00002, springboot-properties-to-quarkus-00003
**Goal**: Convert Spring Boot application.properties to Quarkus with profile prefixes and preserve petclinic.security.enable and server.servlet.context-path tokens
**Target design**:
- → `src/main/resources/application.properties`
**Acceptance**: plan-lint green; sensors green

#### T-002: application-hsqldb.properties — HSQLDB datasource
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Owns**: `src/main/resources/application-hsqldb.properties`
**Oracle**: absent
**Assumes**:
**Findings**: localhost-jdbc-00002
**Goal**: Convert HSQLDB datasource configuration to Quarkus Agroal format
**Target design**:
- → `src/main/resources/application-hsqldb.properties`
**Acceptance**: plan-lint green; sensors green

#### T-003: application-mysql.properties — MySQL datasource
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Owns**: `src/main/resources/application-mysql.properties`
**Oracle**: absent
**Assumes**:
**Findings**: localhost-jdbc-00002
**Goal**: Convert MySQL datasource configuration to Quarkus Agroal format
**Target design**:
- → `src/main/resources/application-mysql.properties`
**Acceptance**: plan-lint green; sensors green

#### T-004: application-postgresql.properties — PostgreSQL datasource
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Owns**: `src/main/resources/application-postgresql.properties`
**Oracle**: absent
**Assumes**:
**Findings**: localhost-jdbc-00002
**Goal**: Convert PostgreSQL datasource configuration to Quarkus Agroal format
**Target design**:
- → `src/main/resources/application-postgresql.properties`
**Acceptance**: plan-lint green; sensors green

#### T-005: messages.properties — Default message bundles
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Owns**: `src/main/resources/messages/messages.properties`
**Oracle**: absent
**Assumes**:
**Findings**: spring-components-00001, spring-components-00002
**Goal**: Convert Spring message source configuration to Quarkus format
**Target design**:
- → `src/main/resources/messages/messages.properties`
**Acceptance**: plan-lint green; sensors green

#### T-006: messages_de.properties — German message bundles
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Owns**: `src/main/resources/messages/messages_de.properties`
**Oracle**: absent
**Assumes**:
**Findings**: spring-components-00001, spring-components-00002
**Goal**: Convert German message bundle to Quarkus format
**Target design**:
- → `src/main/resources/messages/messages_de.properties`
**Acceptance**: plan-lint green; sensors green

#### T-007: messages_en.properties — English message bundles
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Owns**: `src/main/resources/messages/messages_en.properties`
**Oracle**: absent
**Assumes**:
**Findings**: spring-components-00001, spring-components-00002
**Goal**: Convert English message bundle to Quarkus format
**Target design**:
- → `src/main/resources/messages/messages_en.properties`
**Acceptance**: plan-lint green; sensors green

#### T-008: api-docs.yml — API documentation configuration
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Owns**: `src/main/resources/api-docs.yml`
**Oracle**: absent
**Assumes**:
**Findings**: springboot-web-to-quarkus-00000
**Goal**: Convert Spring REST documentation to Quarkus format
**Target design**:
- → `src/main/resources/api-docs.yml`
**Acceptance**: plan-lint green; sensors green

#### T-009: test-application.properties — Test configuration
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Owns**: `src/test/resources/application.properties`
**Oracle**: absent
**Assumes**:
**Findings**: springboot-properties-to-quarkus-00000
**Goal**: Convert test application properties to Quarkus format
**Target design**:
- → `src/test/resources/application.properties`
**Acceptance**: plan-lint green; sensors green

#### T-011: SpringConfigTests — Spring configuration tests
**Class**: infer
**Shape**: create
**Port**: reimplement
**Owns**: `src/test/java/com/demo/SpringConfigTests.java`
**Oracle**: absent
**Assumes**: Test framework converted to Quarkus testing model
**Findings**: springboot-actuator-to-quarkus-0100, springboot-metrics-to-quarkus-0100, springboot-metrics-to-quarkus-0200, springboot-cache-to-quarkus-00000, springboot-di-to-quarkus-00000, springboot-jpa-to-quarkus-00000, springboot-security-to-quarkus-00000
**Goal**: Convert Spring configuration tests to Quarkus testing framework with proper profile-based configuration validation
**Target design**:
- → `src/test/java/com/demo/SpringConfigTests.java`
**Acceptance**: plan-lint green; sensors green


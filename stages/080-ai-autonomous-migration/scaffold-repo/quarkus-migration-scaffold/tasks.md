UI surface: waived (API-only).

#### T-009: Convert JPA repository implementations to CDI
**Class**: rewrite
**Findings**: springboot-di-to-quarkus-00003
**Goal**: Convert JPA repository implementations to CDI
**Target**: `src/main/java/com/demo/repository/jpa/*.java`

#### T-010: Convert ClinicServiceImpl to Quarkus CDI
**Class**: rewrite
**Findings**: springboot-di-to-quarkus-00003
**Goal**: Convert Spring @Service to Quarkus @ApplicationScoped with CDI injection
**Target**: `src/main/java/com/demo/service/ClinicServiceImpl.java`

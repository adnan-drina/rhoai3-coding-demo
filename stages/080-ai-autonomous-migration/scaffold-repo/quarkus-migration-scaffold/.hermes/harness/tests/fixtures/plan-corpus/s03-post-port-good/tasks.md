# Tasks

UI surface: waived (API-only service; no legacy web frontend).

<!-- O-PLANCORPUS known-GREEN: post-Port plan shape (mapping + owned peers). -->

#### T-001: Convert JDBC repositories to Agroal (harvest-then-convert)
**Class**: infer
**Shape**: create
**Port**: reimplement
**Goal**: Harvest JDBC repository types then convert NamedParameterJdbcTemplate / JdbcTemplate implementations to Agroal DataSource + @Inject (O-SDJPAHARVEST / harvest-then-convert)
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java`
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcPet.java`
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcPetVisitExtractor.java`
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcPetRowMapper.java`
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcVisitRowMapper.java`
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcPetRepositoryImpl.java`
**Target**: → `src/main/java/com/demo/repository/jdbc/JdbcVisitRepositoryImpl.java`
**Target**: → `src/main/java/com/demo/repository/OwnerRepository.java`
**Owns**: src/main/java/com/demo/repository/jdbc/JdbcOwnerRepositoryImpl.java, src/main/java/com/demo/repository/jdbc/JdbcPet.java, src/main/java/com/demo/repository/jdbc/JdbcPetVisitExtractor.java, src/main/java/com/demo/repository/jdbc/JdbcPetRowMapper.java, src/main/java/com/demo/repository/jdbc/JdbcVisitRowMapper.java, src/main/java/com/demo/repository/jdbc/JdbcPetRepositoryImpl.java, src/main/java/com/demo/repository/jdbc/JdbcVisitRepositoryImpl.java, src/main/java/com/demo/repository/OwnerRepository.java
**API mapping**:
| legacy | target |
| NamedParameterJdbcTemplate | Agroal `DataSource` + `java.sql` |
| DataAccessException | PersistenceException (jakarta.persistence) |
| EmptyResultDataAccessException | NoResultException |
| ObjectRetrievalFailureException | EntityNotFoundException |
**Findings**: springboot-di-to-quarkus-00003, springboot-di-to-quarkus-00000, springboot-di-to-quarkus-00002
**Acceptance**: convert-after-harvest (O-SDJPAHARVESTONLY); no org.springframework.jdbc|dao under src/main; omit throws or remap per table (O-M3PRESERVEDAO / O-DAOEXMAP); repository package compiles under Quarkus

#### T-002: Characterize OwnerRepository contract (O-PLANCOVERGATE / O-M3COVEREMIT)
**Class**: infer
**Shape**: create
**Goal**: Add characterization so ship new_coverage can pass (F-plan-covers-gate)
**Owns**: src/test/java/com/demo/repository/OwnerRepositoryTest.java
**Oracle**: absent
**Acceptance**: characterization pins layer contract for ship coverage (O-M3COVEREMIT / F-plan-covers-gate)

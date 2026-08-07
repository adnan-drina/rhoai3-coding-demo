# Modernization roadmap

## S01: Platform and BOM conversion
- scope: pom.xml
- findings: javaee-pom-to-quarkus-00010, javaee-pom-to-quarkus-00020, javaee-pom-to-quarkus-00030, javaee-pom-to-quarkus-00040, javaee-pom-to-quarkus-00050, javaee-pom-to-quarkus-00060, springboot-parent-pom-to-quarkus-00000, springboot-plugins-to-quarkus-0000, springboot-properties-to-quarkus-00000, springboot-actuator-to-quarkus-0100, springboot-metrics-to-quarkus-0100, spring-components-00001, spring-components-00002, springboot-properties-to-quarkus-00001, springboot-properties-to-quarkus-00002, springboot-properties-to-quarkus-00003, localhost-jdbc-00002, springboot-cache-to-quarkus-00000
- depends: -
- deploy: false
- done: Quarkus BOM configured, Maven plugins configured, Spring Boot dependencies replaced
- rationale: Establishes Quarkus platform foundation before any code transformation (dependency-order.md:19-20)
- kind: mixed
- seat-budget: 10

## S02: Package rename and recipe-executed transformations
- scope: src/main/java/org/springframework/samples/petclinic/model/BaseEntity.java, src/main/java/org/springframework/samples/petclinic/model/NamedEntity.java, src/main/java/org/springframework/samples/petclinic/model/Owner.java, src/main/java/org/springframework/samples/petclinic/model/Person.java, src/main/java/org/springframework/samples/petclinic/model/Pet.java, src/main/java/org/springframework/samples/petclinic/model/PetType.java, src/main/java/org/springframework/samples/petclinic/model/Role.java, src/main/java/org/springframework/samples/petclinic/model/Specialty.java, src/main/java/org/springframework/samples/petclinic/model/User.java, src/main/java/org/springframework/samples/petclinic/model/Vet.java, src/main/java/org/springframework/samples/petclinic/model/Visit.java, src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcOwnerRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaOwnerRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetTypeRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaSpecialtyRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaUserRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVetRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVisitRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetTypeRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataSpecialtyRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVisitRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java, src/main/java/org/springframework/samples/petclinic/rest/PetRestController.java, src/main/java/org/springframework/samples/petclinic/rest/PetTypeRestController.java, src/main/java/org/springframework/samples/petclinic/rest/RootRestController.java, src/main/java/org/springframework/samples/petclinic/rest/SpecialtyRestController.java, src/main/java/org/springframework/samples/petclinic/rest/UserRestController.java, src/main/java/org/springframework/samples/petclinic/rest/VetRestController.java, src/main/java/org/springframework/samples/petclinic/rest/VisitRestController.java
- findings: javax-to-jakarta-import-00001, removed-javaee-modules-00020, springboot-annotations-to-quarkus-00000, springboot-annotations-to-quarkus-00002
- depends: S01
- deploy: false
- done: All javax→jakarta imports converted, @SpringBootApplication removed, package renamed from org.springframework.samples.petclinic to com.demo
- rationale: Recipe-executed transformations and package rename harvest from migration/staging (SEQUENCING.md:54-60), god nodes first per dependency order
- kind: rename
- seat-budget: 1

## S03: Domain model and entity foundation
- scope: src/main/java/org/springframework/samples/petclinic/model/BaseEntity.java, src/main/java/org/springframework/samples/petclinic/model/NamedEntity.java, src/main/java/org/springframework/samples/petclinic/model/Person.java, src/main/java/org/springframework/samples/petclinic/model/Owner.java, src/main/java/org/springframework/samples/petclinic/model/Pet.java, src/main/java/org/springframework/samples/petclinic/model/PetType.java, src/main/java/org/springframework/samples/petclinic/model/Specialty.java, src/main/java/org/springframework/samples/petclinic/model/Vet.java, src/main/java/org/springframework/samples/petclinic/model/Role.java, src/main/java/org/springframework/samples/petclinic/model/User.java, src/main/java/org/springframework/samples/petclinic/model/Visit.java
- findings: -
- depends: S02
- deploy: false
- done: Domain entities preserved with jakarta.persistence annotations, validation constraints maintained
- rationale: HARVEST classes (architecture-profile §7) - god nodes BaseEntity, NamedEntity, PetType first per dependency order, foundational layer for all downstream components
- kind: rename
- seat-budget: 1

## S04: Repository layer and circular dependency cluster
- scope: src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcOwnerRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetTypeRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcSpecialtyRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcUserRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVetRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVisitRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaOwnerRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetTypeRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaSpecialtyRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaUserRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVetRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVisitRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/PetRepositoryOverride.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpecialtyRepositoryOverride.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataOwnerRepository.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepository.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetTypeRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataSpecialtyRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVisitRepositoryImpl.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataUserRepository.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVetRepository.java, src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/VisitRepositoryOverride.java
- findings: springboot-jpa-to-quarkus-00000, springboot-di-to-quarkus-00000, springboot-di-to-quarkus-00003, transaction-to-quarkus-00003
- depends: S03
- deploy: false
- done: All repository implementations converted to @ApplicationScoped CDI beans with constructor injection, transaction management configured
- rationale: Circular dependency cluster (dependency-order.md:42-104) - 54 mutually-dependent classes converted together to maintain transactional consistency, repository layer before service layer

## S05: Service layer modernization
- scope: src/main/java/org/springframework/samples/petclinic/service/ClinicService.java, src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java, src/main/java/org/springframework/samples/petclinic/service/UserService.java, src/main/java/org/springframework/samples/petclinic/service/UserServiceImpl.java
- findings: -
- depends: S04
- deploy: false
- done: Services converted to @ApplicationScoped CDI beans, constructor injection implemented, facade removed
- rationale: Service layer (architecture-profile §7) - service layer after repository layer per dependency order, implements target contract with CDI modernization
- kind: reimplement
- seat-budget: 5

## S06: REST endpoints and configuration
- scope: src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java, src/main/java/org/springframework/samples/petclinic/rest/PetRestController.java, src/main/java/org/springframework/samples/petclinic/rest/PetTypeRestController.java, src/main/java/org/springframework/samples/petclinic/rest/SpecialtyRestController.java, src/main/java/org/springframework/samples/petclinic/rest/UserRestController.java, src/main/java/org/springframework/samples/petclinic/rest/VetRestController.java, src/main/java/org/springframework/samples/petclinic/rest/VisitRestController.java, src/main/java/org/springframework/samples/petclinic/rest/RootRestController.java, src/main/java/org/springframework/samples/petclinic/rest/ExceptionControllerAdvice.java, src/main/java/org/springframework/samples/petclinic/rest/BindingErrorsResponse.java, src/main/java/org/springframework/samples/petclinic/util/EntityUtils.java, src/main/java/org/springframework/samples/petclinic/util/CallMonitoringAspect.java, src/main/java/org/springframework/samples/petclinic/security/BasicAuthenticationConfig.java, src/main/java/org/springframework/samples/petclinic/security/DisableSecurityConfig.java, src/main/java/org/springframework/samples/petclinic/security/Roles.java, src/main/java/org/springframework/samples/petclinic/util/ApplicationSwaggerConfig.java
- findings: springboot-web-to-quarkus-00000, springboot-metrics-to-quarkus-0200, springboot-webmvc-to-quarkus-00000, springboot-security-to-quarkus-00000, springboot-jmx-to-quarkus-00001, spring-components-00001, spring-components-00002
- depends: S05
- deploy: true
- done: REST controllers converted to JAX-RS resources with error handling, security configured, observability implemented
- rationale: REST endpoints and configuration (architecture-profile §7) - HTTP surface after dependencies, final deploy milestone with complete API contract (migration.yaml targetContract)
- kind: reimplement
- seat-budget: 5

## Non-mandatory decisions
- hibernate-00005: defer (low priority optimization, out of scope for initial migration)
- persistence-to-quarkus-00010: adopt (standardizes persistence context injection)
- springboot-devservices-to-quarkus-00000: defer (development convenience, not required for production migration)

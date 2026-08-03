# Findings inventory (M1 spec input bundle)

Rules: 37; incidents: 266. Join source: MAPPINGS.md rule-join table (16 rows).

## javax-to-jakarta-import-00001 [recipe]

- The package 'javax' has been replaced by 'jakarta'.
- Decided target: jakarta.* imports
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/BaseEntity.java: line 18, 19, 20, 21
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/NamedEntity.java: line 18, 19, 21
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Owner.java: line 22, 23, 24
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Person.java: line 18, 19, 21
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Pet.java: line 22
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/PetType.java: line 18, 19
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Role.java: line 3, 4, 5, 6, 7, 8
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Specialty.java: line 18, 19
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/User.java: line 6, 7, 8, 9, 10, 11, 12
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Vet.java: line 22, 23
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/model/Visit.java: line 20, 21
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcOwnerRepositoryImpl.java: line 36
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaOwnerRepositoryImpl.java: line 20, 21, 22
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetRepositoryImpl.java: line 21, 22
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetTypeRepositoryImpl.java: line 23, 24
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaSpecialtyRepositoryImpl.java: line 21, 22
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaUserRepositoryImpl.java: line 3, 4
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVetRepositoryImpl.java: line 24, 25
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVisitRepositoryImpl.java: line 21, 22, 23
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepositoryImpl.java: line 19, 20
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetTypeRepositoryImpl.java: line 24, 25
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataSpecialtyRepositoryImpl.java: line 19, 20
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVisitRepositoryImpl.java: line 19, 20
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/OwnerRestController.java: line 31, 32
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/PetRestController.java: line 32, 33
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/PetTypeRestController.java: line 31, 32
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/RootRestController.java: line 21
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/SpecialtyRestController.java: line 31, 32
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/UserRestController.java: line 30
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/VetRestController.java: line 32, 33
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/VisitRestController.java: line 31, 32
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/OwnerMapperImpl.java: line 6
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/PetMapperImpl.java: line 6
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/PetTypeMapperImpl.java: line 5
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/SpecialtyMapperImpl.java: line 5
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/UserMapperImpl.java: line 8
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/VetMapperImpl.java: line 6
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/VisitMapperImpl.java: line 5
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/OwnerAllOfDto.java: line 11, 12
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/OwnerDto.java: line 13, 14
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/OwnerFieldsDto.java: line 8, 9
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/PetAllOfDto.java: line 12, 13
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/PetDto.java: line 15, 16
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/PetFieldsDto.java: line 9, 10
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/PetTypeDto.java: line 8, 9
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/RestErrorDto.java: line 13, 14
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/RoleDto.java: line 8, 9
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/SpecialtyDto.java: line 8, 9
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/UserDto.java: line 11, 12
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/ValidationMessageDto.java: line 10, 11
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/VetDto.java: line 11, 12
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/VisitAllOfDto.java: line 8, 9
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/VisitDto.java: line 11, 12
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/VisitFieldsDto.java: line 9, 10

## springboot-di-to-quarkus-00003 [infer]

- Apply Quarkus Spring DI conversion guidance for common Spring DI annotations
- Decided target: native CDI constructor injection (NOT the spring-di extension)
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcOwnerRepositoryImpl.java: line 54, 62
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetRepositoryImpl.java: line 54, 67
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcPetTypeRepositoryImpl.java: line 47, 55
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcSpecialtyRepositoryImpl.java: line 43, 51
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcUserRepositoryImpl.java: line 21, 28
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVetRepositoryImpl.java: line 56, 64
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jdbc/JdbcVisitRepositoryImpl.java: line 51, 58
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaOwnerRepositoryImpl.java: line 40
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetRepositoryImpl.java: line 40
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetTypeRepositoryImpl.java: line 39
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaSpecialtyRepositoryImpl.java: line 35
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaUserRepositoryImpl.java: line 12
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVetRepositoryImpl.java: line 37
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaVisitRepositoryImpl.java: line 42
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/rest/RootRestController.java: line 38
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/security/BasicAuthenticationConfig.java: line 17, 22, 40
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/security/DisableSecurityConfig.java: line 12
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/security/Roles.java: line 5
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/service/ClinicServiceImpl.java: line 47, 58
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/service/UserServiceImpl.java: line 10, 13
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/util/ApplicationSwaggerConfig.java: line 50, 55, 83
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/OwnerMapperImpl.java: line 17, 20
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/PetMapperImpl.java: line 18
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/PetTypeMapperImpl.java: line 13
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/SpecialtyMapperImpl.java: line 13
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/UserMapperImpl.java: line 18
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/VetMapperImpl.java: line 17, 20
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/VisitMapperImpl.java: line 13

## removed-javaee-modules-00020 [rewrite]

- The java.annotation (Common Annotations) module has been removed from OpenJDK 11
- Decided target: JEE modules removed from the JDK → provided by Quarkus platform dependencies (BOM) — resolved with the pom conversion
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/OwnerMapperImpl.java: line 6
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/PetMapperImpl.java: line 6
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/PetTypeMapperImpl.java: line 5
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/SpecialtyMapperImpl.java: line 5
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/UserMapperImpl.java: line 8
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/VetMapperImpl.java: line 6
- /projects/legacy/target/generated-sources/annotations/org/springframework/samples/petclinic/mapper/VisitMapperImpl.java: line 5
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/OwnerAllOfDto.java: line 18
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/OwnerDto.java: line 21
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/OwnerFieldsDto.java: line 16
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/PetAllOfDto.java: line 19
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/PetDto.java: line 23
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/PetFieldsDto.java: line 17
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/PetTypeDto.java: line 16
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/RestErrorDto.java: line 21
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/RoleDto.java: line 16
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/SpecialtyDto.java: line 16
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/UserDto.java: line 19
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/ValidationMessageDto.java: line 18
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/VetDto.java: line 19
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/VisitAllOfDto.java: line 15
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/VisitDto.java: line 19
- /projects/legacy/target/generated-sources/openapi/src/main/java/org/springframework/samples/petclinic/dto/VisitFieldsDto.java: line 17

## spring-components-00002 [infer]

- Version of Spring not compatible with Jakarta EE 9+
- Decided target: umbrella version-incompatibility rules — resolved by the conversion tasks as a whole; map to the service/endpoint conversion tasks
- /projects/legacy/pom.xml: line 40, 44, 48, 52, 56, 60, 64, 68, 88, 100, 105, 124

## springboot-properties-to-quarkus-00002 [rewrite]

- Replace Spring datasource property key/value pairs with Quarkus properties
- Decided target: Quarkus keys in application.properties (plain pass-throughs keep working; NOT the spring-boot-properties extension)
- /projects/legacy/src/main/resources/application-hsqldb.properties: line 7, 8, 9
- /projects/legacy/src/main/resources/application-mysql.properties: line 8, 9, 10, 11
- /projects/legacy/src/main/resources/application-postgresql.properties: line 8, 9, 10, 11

## spring-components-00001 [infer]

- Version of Spring Boot not compatible with Jakarta EE 9+
- Decided target: umbrella version-incompatibility rules — resolved by the conversion tasks as a whole; map to the service/endpoint conversion tasks
- /projects/legacy/pom.xml: line 40, 44, 48, 52, 56, 60, 64, 68, 100

## springboot-jmx-to-quarkus-00001 [OPEN DESIGN]

- Spring JMX annotations are not a supported Quarkus migration path; use Micrometer-based observability instead
- Decided target: no MAPPINGS join — decide the shape in the plan
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/util/CallMonitoringAspect.java: line 37, 47, 52, 57, 63, 68

## springboot-properties-to-quarkus-00003 [rewrite]

- Replace Spring log level property with Quarkus property
- Decided target: Quarkus keys in application.properties (plain pass-throughs keep working; NOT the spring-boot-properties extension)
- /projects/legacy/src/main/resources/application.properties: line 33, 34
- /projects/legacy/src/test/resources/application.properties: line 28, 29

## springboot-properties-to-quarkus-00001 [rewrite]

- Spring property profiles in separate files must be refactored into Quarkus properties file
- Decided target: Quarkus keys in application.properties (plain pass-throughs keep working; NOT the spring-boot-properties extension)
- /projects/legacy/src/main/resources/application-hsqldb.properties: line ?
- /projects/legacy/src/main/resources/application-mysql.properties: line ?
- /projects/legacy/src/main/resources/application-postgresql.properties: line ?

## transaction-to-quarkus-00003 [OPEN DESIGN]

- EntityManager remove operations require @Transactional in Quarkus
- Decided target: no MAPPINGS join — decide the shape in the plan
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/jpa/JpaPetRepositoryImpl.java: line 80
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataPetRepositoryImpl.java: line 42
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/repository/springdatajpa/SpringDataVisitRepositoryImpl.java: line 42

## localhost-jdbc-00002 [OPEN DESIGN]

- Local JDBC Calls
- Decided target: no MAPPINGS join — decide the shape in the plan
- /projects/legacy/src/main/resources/application-mysql.properties: line 8
- /projects/legacy/src/main/resources/application-postgresql.properties: line 8

## springboot-security-to-quarkus-00000 [OPEN DESIGN]

- Replace the SpringBoot Security artifact with Quarkus 'spring-security' extension
- Decided target: no MAPPINGS join — decide the shape in the plan
- /projects/legacy/pom.xml: line 64, 105

## javaee-pom-to-quarkus-00010 [rewrite]

- Adopt Quarkus BOM
- Decided target: scaffold pom conventions: platform BOM, pinned quarkus/compiler/surefire/failsafe plugins, native profile, quarkus junit
- /projects/legacy/pom.xml: line 4

## javaee-pom-to-quarkus-00020 [rewrite]

- Adopt Quarkus Maven plugin
- Decided target: scaffold pom conventions: platform BOM, pinned quarkus/compiler/surefire/failsafe plugins, native profile, quarkus junit
- /projects/legacy/pom.xml: line 4

## javaee-pom-to-quarkus-00030 [rewrite]

- Adopt Maven Compiler plugin
- Decided target: scaffold pom conventions: platform BOM, pinned quarkus/compiler/surefire/failsafe plugins, native profile, quarkus junit
- /projects/legacy/pom.xml: line 4

## javaee-pom-to-quarkus-00040 [rewrite]

- Adopt Maven Surefire plugin
- Decided target: scaffold pom conventions: platform BOM, pinned quarkus/compiler/surefire/failsafe plugins, native profile, quarkus junit
- /projects/legacy/pom.xml: line 4

## javaee-pom-to-quarkus-00050 [rewrite]

- Adopt Maven Failsafe plugin
- Decided target: scaffold pom conventions: platform BOM, pinned quarkus/compiler/surefire/failsafe plugins, native profile, quarkus junit
- /projects/legacy/pom.xml: line 4

## javaee-pom-to-quarkus-00060 [rewrite]

- Add Maven profile to run the Quarkus native build
- Decided target: scaffold pom conventions: platform BOM, pinned quarkus/compiler/surefire/failsafe plugins, native profile, quarkus junit
- /projects/legacy/pom.xml: line 4

## javax-to-jakarta-dependencies-00001 [recipe]

- The 'javax' groupId has been replaced by 'jakarta' group id in dependencies.
- Decided target: jakarta.* imports
- /projects/legacy/pom.xml: line 156

## javax-to-jakarta-dependencies-00003 [recipe]

- javax.xml.bind jaxb-api artifactId has been replaced by jakarta.xml.bind jakarta.xml.bind-api
- Decided target: jakarta.* imports
- /projects/legacy/pom.xml: line 157

## springboot-actuator-to-quarkus-0100 [rewrite]

- Replace Spring Boot Actuator with Quarkus health, metrics, info and management interface capabilities
- Decided target: `quarkus-smallrye-health` (`/q/health`)
- /projects/legacy/pom.xml: line 40

## springboot-annotations-to-quarkus-00000 [rewrite]

- Replace SpringBootApplication bootstrap model with Quarkus bootstrap and CDI
- Decided target: delete `@SpringBootApplication` + main class
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/PetClinicApplication.java: line 7

## springboot-annotations-to-quarkus-00002 [rewrite]

- Replace Spring ComponentScan with CDI bean discovery conventions
- Decided target: delete `@SpringBootApplication` + main class
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/util/ApplicationSwaggerConfig.java: line 52

## springboot-cache-to-quarkus-00000 [OPEN DESIGN]

- Replace the SpringBoot cache artifact with Quarkus 'spring-cache' extension
- Decided target: no MAPPINGS join — decide the shape in the plan
- /projects/legacy/pom.xml: line 48

## springboot-di-to-quarkus-00000 [infer]

- Replace the SpringBoot Dependency Injection artifact with Quarkus 'spring-di' extension
- Decided target: native CDI constructor injection (NOT the spring-di extension)
- /projects/legacy/pom.xml: line 44

## springboot-di-to-quarkus-00002 [infer]

- Spring DI infrastructure classes not supported by Quarkus
- Decided target: native CDI constructor injection (NOT the spring-di extension)
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/util/ApplicationSwaggerConfig.java: line 85

## springboot-jpa-to-quarkus-00000 [OPEN DESIGN]

- Replace the SpringBoot Data JPA artifact with Quarkus 'spring-data-jpa' extension
- Decided target: no MAPPINGS join — decide the shape in the plan
- /projects/legacy/pom.xml: line 52

## springboot-metrics-to-quarkus-0100 [rewrite]

- Replace the Micrometer dependency with Quarkus Microprofile 'metrics' extension
- Decided target: Micrometer dependency → `quarkus-smallrye-metrics`
- /projects/legacy/pom.xml: line 40

## springboot-metrics-to-quarkus-0200 [infer]

- Replace the Micrometer code with Microprofile Metrics code
- Decided target: metrics call sites → MP Metrics annotations (design per site)
- /projects/legacy/pom.xml: line 40

## springboot-parent-pom-to-quarkus-00000 [rewrite]

- Replace the Spring Parent POM with Quarkus BOM
- Decided target: Quarkus platform BOM replaces the Spring parent
- /projects/legacy/pom.xml: line 14

## springboot-plugins-to-quarkus-0000 [rewrite]

- Replace the spring-boot-maven-plugin dependency
- Decided target: `quarkus-maven-plugin` (pinned, `${quarkus.platform.group-id}`)
- /projects/legacy/pom.xml: line 163

## springboot-properties-to-quarkus-00000 [rewrite]

- Replace the SpringBoot artifact with Quarkus 'spring-boot-properties' extension
- Decided target: Quarkus keys in application.properties (plain pass-throughs keep working; NOT the spring-boot-properties extension)
- /projects/legacy/pom.xml: line 40

## springboot-web-to-quarkus-00000 [infer]

- Replace the Spring Web artifact with Quarkus 'spring-web' extension
- Decided target: native JAX-RS resources (NOT the spring-web extension)
- /projects/legacy/pom.xml: line 60

## springboot-webmvc-to-quarkus-00000 [OPEN DESIGN]

- Spring MVC is not supported by Quarkus
- Decided target: no MAPPINGS join — decide the shape in the plan
- /projects/legacy/src/main/java/org/springframework/samples/petclinic/util/ApplicationSwaggerConfig.java: line 27

## Non-mandatory findings (decide adopt / defer in roadmap)

| rule | category | effort | sites | description |
|---|---|---|---|---|
| hibernate-00005 | potential | 3 | 1 | Implicit name determination for sequences and tables associated with identifier … |
| persistence-to-quarkus-00010 | optional | 1 | 11 | Replace @PersistenceContext with @Inject |
| springboot-devservices-to-quarkus-00000 | potential | 2 | 1 | Use Quarkus Dev Services as a local development alternative for Spring infrastru… |

M2 must mark each rule in the roadmap under `## Non-mandatory decisions` as `adopt` or `defer (reason)` (K3).

## Summary by class

- recipe: 3 — javax-to-jakarta-dependencies-00001, javax-to-jakarta-dependencies-00003, javax-to-jakarta-import-00001
- rewrite: 17 — javaee-pom-to-quarkus-00010, javaee-pom-to-quarkus-00020, javaee-pom-to-quarkus-00030, javaee-pom-to-quarkus-00040, javaee-pom-to-quarkus-00050, javaee-pom-to-quarkus-00060, removed-javaee-modules-00020, springboot-actuator-to-quarkus-0100, springboot-annotations-to-quarkus-00000, springboot-annotations-to-quarkus-00002, springboot-metrics-to-quarkus-0100, springboot-parent-pom-to-quarkus-00000, springboot-plugins-to-quarkus-0000, springboot-properties-to-quarkus-00000, springboot-properties-to-quarkus-00001, springboot-properties-to-quarkus-00002, springboot-properties-to-quarkus-00003
- infer: 7 — spring-components-00001, spring-components-00002, springboot-di-to-quarkus-00000, springboot-di-to-quarkus-00002, springboot-di-to-quarkus-00003, springboot-metrics-to-quarkus-0200, springboot-web-to-quarkus-00000
- OPEN DESIGN: 7 — localhost-jdbc-00002, springboot-cache-to-quarkus-00000, springboot-jmx-to-quarkus-00001, springboot-jpa-to-quarkus-00000, springboot-security-to-quarkus-00000, springboot-webmvc-to-quarkus-00000, transaction-to-quarkus-00003
- non-mandatory: 3 — hibernate-00005, persistence-to-quarkus-00010, springboot-devservices-to-quarkus-00000

## Preserve-candidate surfaces (confirm against migration.yaml preserve:)

- springboot-properties-to-quarkus-00002: Replace Spring datasource property key/value pairs with Quarkus properties
- springboot-properties-to-quarkus-00003: Replace Spring log level property with Quarkus property
- springboot-properties-to-quarkus-00001: Spring property profiles in separate files must be refactored into Quarkus properties file
- springboot-actuator-to-quarkus-0100: Replace Spring Boot Actuator with Quarkus health, metrics, info and management interface capabilitie
- springboot-properties-to-quarkus-00000: Replace the SpringBoot artifact with Quarkus 'spring-boot-properties' extension

# S01: Platform and BOM conversion

<!-- The brief is the self-contained work order for one modernization
     story. Bar: a competent developer or a fresh session starts the
     story from THIS FILE ALONE. Fill every section; delete none. -->

## Goal & position

Establishes the Quarkus platform foundation before any code transformation. This story converts the Maven POM from Spring Boot to Quarkus, replacing the parent POM, plugins, and core dependencies. It is the first story in the roadmap (dependency-order.md:19-20) and unblocks all subsequent code transformation stories.

## In scope

The exact legacy classes/files this story modernizes. For each, quote
the load-bearing legacy code (the lines being transformed — imports,
annotations, key methods), so the story never starts from a blank
read:

- `pom.xml` — Spring Boot platform configuration
  ```xml
  <parent>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-parent</artifactId>
      <version>2.6.2</version>
      <relativePath/> <!-- lookup parent from Maven repository -->
  </parent>
  ```
  ```xml
  <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-actuator</artifactId>
  </dependency>
  ```
  ```xml
  <plugin>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-maven-plugin</artifactId>
  </plugin>
  ```

## Out of scope

All source code files remain unchanged. This story only transforms the build configuration and dependencies, creating the foundation for subsequent code modernization stories.

## Class roles & target contract (from architecture-profile §7)

N/A - Platform configuration only, no application classes.

## Decided target shapes

The MAPPINGS.md rows that apply (quote the decided target, don't
re-decide). Recipe-executed rules already handled: reference
`migration/recipe-log.md` and `migration/staging/` where applicable.

**POM transformation:**
- Spring Boot parent → Quarkus platform BOM (com.redhat.quarkus.platform)
- Spring Boot plugins → Quarkus Maven plugin
- Spring Boot starter dependencies → Quarkus extensions
- Actuator → SmallRye Health

**Story ordering:** extensions and BOM first, then models, then resources,
then config keys, then tests (`extensions → models → resources → config →
tests`).

## Contracts owned by this story

- **Findings**: the mandatory rule ids this story resolves (from the
  roadmap entry).
  - javaee-pom-to-quarkus-00010 (Adopt Quarkus BOM)
  - javaee-pom-to-quarkus-00020 (Adopt Quarkus Maven plugin)
  - javaee-pom-to-quarkus-00030 (Adopt Maven Compiler plugin)
  - javaee-pom-to-quarkus-00040 (Adopt Maven Surefire plugin)
  - javaee-pom-to-quarkus-00050 (Adopt Maven Failsafe plugin)
  - javaee-pom-to-quarkus-00060 (Add native build profile)
  - springboot-parent-pom-to-quarkus-00000 (Replace Spring Parent POM)
  - springboot-plugins-to-quarkus-0000 (Replace Spring Boot plugin)
  - springboot-properties-to-quarkus-00000 (Replace SpringBoot artifact)
  - springboot-actuator-to-quarkus-0100 (Replace Actuator)
  - springboot-metrics-to-quarkus-0100 (Replace Micrometer)
  - javax-to-jakarta-dependencies-00001 (javax→jakarta dependencies)
  - javax-to-jakarta-dependencies-00003 (jaxb-api migration)
- **seat-budget**: 5 — expected OpenCode seats from roadmap
  `kind × incident count` (O-SEATBUDGET / ARCH A5). Same integer as
  roadmap `- seat-budget: 5`. Supervisor escalates on overrun.
- **Preserve**: N/A - no preserve items in this scope
- **Behavioral pins**: N/A - no application behavior changes
- **Forbidden**: N/A
- **kind**: mixed

## Done-criteria

Checkable, story-scoped:
- builds + `sensors.sh task` green at every commit; milestone green at
  story end
- `mvn clean compile` succeeds with Quarkus BOM
- No Spring Boot parent references remain in pom.xml
- Quarkus extensions replace Spring Boot starters
- springboot-actuator replaced with quarkus-smallrye-health
- deploy story only: factory pipeline green, deployed, acceptance path
  serving (N/A - this is not a deploy story)

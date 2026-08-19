# Canonical Red Hat Quarkus POM structure (T-1)

Structure-only fragments grounded in official RHBQ / quarkus.io Maven
tooling chapters. **Do not paste version literals** — substitute from
`.hermes/pins.json`.

Story `<dependencies>` on the sole `pom.xml` writer carry foundation
Jacoco / Sonar wiring **and** `identity.extensions_apply` (sorted unique
union of every story's `identity.extensions_declared`, DD3
Architect E-20260814T205052Z). Later stories do not write `pom.xml`.
See `../bootstrap-quarkus-project/references/foundation-jacoco-wiring.md`.

## Properties

Required keys: `quarkus.platform.group-id`, `quarkus.platform.artifact-id`,
`quarkus.platform.version` (feed BOM **and** plugin), `compiler-plugin.version`,
`surefire-plugin.version`, `skipITs` (true at top level; flipped false inside
the `native` profile). Java release **once** (property **or** compiler
plugin config — not both).

```xml
<properties>
  <compiler-plugin.version><!-- pins --></compiler-plugin.version>
  <maven.compiler.release><!-- pins, typically 21 --></maven.compiler.release>
  <quarkus.platform.group-id>com.redhat.quarkus.platform</quarkus.platform.group-id>
  <quarkus.platform.artifact-id>quarkus-bom</quarkus.platform.artifact-id>
  <quarkus.platform.version><!-- `.hermes/pins.json` only --></quarkus.platform.version>
  <surefire-plugin.version><!-- pins --></surefire-plugin.version>
  <skipITs>true</skipITs>
  <!-- dual Sonar paths: foundation-jacoco-wiring.md -->
</properties>
```

## dependencyManagement — BOM import

```xml
<dependencyManagement>
  <dependencies>
    <dependency>
      <groupId>${quarkus.platform.group-id}</groupId>
      <artifactId>${quarkus.platform.artifact-id}</artifactId>
      <version>${quarkus.platform.version}</version>
      <type>pom</type>
      <scope>import</scope>
    </dependency>
  </dependencies>
</dependencyManagement>
```

## dependencies

```xml
<dependencies>
  <!-- Foundation Jacoco: foundation-jacoco-wiring.md.
       Story extensions: identity.extensions_apply on the sole pom.xml writer
       (DD3 declare/apply/own). Later stories do not write this file.
       Harness-owned test toolchain (S-010 / test-toolchain.md) is not a
       Quarkus extension — the pom writer MUST still declare: -->
  <dependency>
    <groupId>io.rest-assured</groupId>
    <artifactId>rest-assured</artifactId>
    <scope>test</scope>
  </dependency>
  <dependency>
    <groupId>org.assertj</groupId>
    <artifactId>assertj-core</artifactId>
    <version><!-- BOM may not manage this; pin a release --></version>
    <scope>test</scope>
  </dependency>
</dependencies>
```

## build — plugin executions

`<extensions>true</extensions>` is required so the plugin participates in the
packaging lifecycle. Prefer the explicit three-goal execution (defensive;
official RHBQ shape) over relying on default bindings alone.

```xml
<build>
  <plugins>
    <plugin>
      <groupId>${quarkus.platform.group-id}</groupId>
      <artifactId>quarkus-maven-plugin</artifactId>
      <version>${quarkus.platform.version}</version>
      <extensions>true</extensions>
      <executions>
        <execution>
          <goals>
            <goal>build</goal>
            <goal>generate-code</goal>
            <goal>generate-code-tests</goal>
          </goals>
        </execution>
      </executions>
    </plugin>
    <plugin>
      <artifactId>maven-compiler-plugin</artifactId>
      <version>${compiler-plugin.version}</version>
      <configuration>
        <parameters>true</parameters>
      </configuration>
    </plugin>
    <plugin>
      <artifactId>maven-surefire-plugin</artifactId>
      <version>${surefire-plugin.version}</version>
      <configuration>
        <!-- argLine forward: foundation-jacoco-wiring.md -->
        <systemPropertyVariables>
          <java.util.logging.manager>org.jboss.logmanager.LogManager</java.util.logging.manager>
          <maven.home>${maven.home}</maven.home>
        </systemPropertyVariables>
      </configuration>
    </plugin>
  </plugins>
</build>
```

Plugin GAV is **`com.redhat.quarkus.platform:quarkus-maven-plugin`** (same
stream as the BOM). Confirmed in RHBQ create docs and at
`https://maven.repository.redhat.com/ga/com/redhat/quarkus/platform/quarkus-maven-plugin/`.

## native profile (Maven, not Quarkus `%profile.`)

Activated by property presence (`-Dnative`), not by Quarkus config-profile
syntax. Enables failsafe ITs against the native runner.

```xml
<profiles>
  <profile>
    <id>native</id>
    <activation>
      <property><name>native</name></property>
    </activation>
    <properties>
      <skipITs>false</skipITs>
      <quarkus.native.enabled>true</quarkus.native.enabled>
    </properties>
    <build>
      <plugins>
        <plugin>
          <artifactId>maven-failsafe-plugin</artifactId>
          <version>${surefire-plugin.version}</version>
          <executions>
            <execution>
              <goals>
                <goal>integration-test</goal>
                <goal>verify</goal>
              </goals>
              <configuration>
                <systemPropertyVariables>
                  <native.image.path>${project.build.directory}/${project.build.finalName}-runner</native.image.path>
                  <java.util.logging.manager>org.jboss.logmanager.LogManager</java.util.logging.manager>
                  <maven.home>${maven.home}</maven.home>
                </systemPropertyVariables>
              </configuration>
            </execution>
          </executions>
        </plugin>
      </plugins>
    </build>
  </profile>
</profiles>
```

## Hand-authoring is official

RHBQ documents a dedicated chapter for configuring `pom.xml` without
scaffolding; quarkus.io Maven tooling likewise. DD1 (retire destination
create) follows that path — not a workaround.

# Foundation Jacoco / Sonar wiring (A-3 / H-3)

Build-wiring infrastructure for destination `pom.xml` — **not** a story-owned
extension (DD3). Carry these on every foundation POM; gate:
`scripts/check-pom-jacoco-wiring.py`.

Versions: inherit the Red Hat BOM / surefire pin from
`.hermes/pins.json` — do not paste version literals here.

## 1. Dependency (`quarkus-jacoco`, test scope)

A plain `jacoco-maven-plugin` agent fights Quarkus class transformation — use
the Quarkus extension.

```xml
<dependency>
  <groupId>io.quarkus</groupId>
  <artifactId>quarkus-jacoco</artifactId>
  <scope>test</scope>
</dependency>
```

## 2. Dual Sonar report paths (property)

Both paths are required. One alone → clean compile + silent coverage hole.

```xml
<sonar.coverage.jacoco.xmlReportPaths>target/jacoco-report/jacoco.xml,target/site/jacoco/jacoco.xml</sonar.coverage.jacoco.xmlReportPaths>
```

- `target/jacoco-report/jacoco.xml` — `@QuarkusTest`-driven coverage
- `target/site/jacoco/jacoco.xml` — plain Surefire-driven coverage

## 3. Surefire `argLine` forward

```xml
<plugin>
  <artifactId>maven-surefire-plugin</artifactId>
  <version>${surefire-plugin.version}</version>
  <configuration>
    <argLine>${argLine}</argLine>
  </configuration>
</plugin>
```

(`${argLine}` or `@{argLine}` — both accepted by the gate.)

## Verify

```bash
python3 ../manage-quarkus-extensions/scripts/check-pom-jacoco-wiring.py <root>
```

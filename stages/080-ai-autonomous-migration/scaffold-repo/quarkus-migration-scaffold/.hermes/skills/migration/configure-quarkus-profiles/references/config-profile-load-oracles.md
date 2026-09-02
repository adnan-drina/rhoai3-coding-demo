# `config_profile_load` oracles (four official mechanisms)

Prefer a **conjunction** of validation + origin proof (or `@TestProfile`
boots). Grepping `%profile.` prose is not enough.

## 1. ConfigValidationException / missing required property

A `@ConfigProperty` / `@ConfigMapping` injection without default and without a
value fails initialization (`SRCFG00014` / expansion `SRCFG00011`), surfaced as
`ConfigValidationException`. Oracle: start (dev, test, or packaged) under each
claimed profile; assert exit 0 and no validation failure naming required keys.
`mvn quarkus:build` surfaces many build-time config problems at augmentation.

## 2. `quarkus.config.build-time-mismatch-at-runtime`

```properties
quarkus.config.build-time-mismatch-at-runtime=fail
```

Fails (or warns) when runtime build-time config disagrees with the compile.
Native `@TestProfile` runs always use `fail` — precedent for treating mismatch
as a hard gate.

## 3. `quarkus.config.log.values` + SmallRye DEBUG

```properties
quarkus.config.log.values=true
quarkus.log.category."io.smallrye.config".level=DEBUG
```

Logs each lookup with source origin. Oracle: grep startup for the key and
assert the reported source is the expected profile-scoped entry, not a
fallback default.

## 4. `@TestProfile` / `QuarkusTestProfile`

```java
public class ExampleProfile implements QuarkusTestProfile {
  @Override public Map<String, String> getConfigOverrides() {
    return Map.of("quarkus.datasource.db-kind", "h2");
  }
  @Override public String getConfigProfile() { return "h2"; }
}

@QuarkusTest
@TestProfile(ExampleProfile.class)
public class ExampleDatasourceTest { /* assert against a live boot */ }
```

Quarkus restarts the app when the test profile differs — genuine separate
boots, not mocks. `getConfigOverrides()` **merges** with
`application.properties` (override per key); it is not a clean-room wipe
unless every relevant key is overridden.

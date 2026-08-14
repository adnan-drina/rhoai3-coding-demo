---
name: configure-quarkus-profiles
description: Before authoring or reminting Quarkus application.properties / profile-scoped datasource config — apply SmallRye source ordinals, %profile and QUARKUS_PROFILE rules, build-time vs runtime locks, and executable config_profile_load oracles; use when an M3 config or properties story runs
license: Apache-2.0
compatibility: Linux seat; Quarkus SmallRye Config
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - migration
    - quarkus
    - config
    category: migration
    kind: guidance
---
# Configure Quarkus profiles (RS1)

Guidance only (R-SK.14). Config-story skill: sources, profiles,
datasource shape, and **executable** `config_profile_load` oracles.

Do **not** recreate Spring's all-runtime `application-{profile}.properties`
mental model. Quarkus has a real build-time vs runtime split — check the
lock icon / extension docs per key.

References:

- `references/config-sources.md` — ordinal table
- `references/profiles-build-vs-runtime.md` — `%profile.`, `QUARKUS_PROFILE`
- `references/datasource-shape.md` — Agroal + jdbc + db-kind
- `references/config-profile-load-oracles.md` — four official mechanisms
- `references/spring-property-map.md` — replace Spring keys (no auto-translate)

## When to Use

- M3 stories whose write-set is primarily `application.properties` /
  profile-scoped datasource / logging config.
- Before claiming `config_profile_load` (or related) as an exit check.
- When migrating Spring Boot property keys to Quarkus.
- **Not** for POM structure — `reference-rh-quarkus-pom` /
  `bootstrap-quarkus-project`.
- **Not** for extension add/rm — `manage-quarkus-extensions` (then return
  here for config obligations).
- **Not** for wrong-class HTTP exits on a config story — `derive-story-oracles`.

## Procedure

1. Read `references/config-sources.md` — know which source wins (env >
   classpath properties, etc.).
2. For each key: decide build-time vs runtime
   (`references/profiles-build-vs-runtime.md`). Build-time keys need a rebuild
   (or accept one artifact per target); runtime keys may use `%profile.` /
   `QUARKUS_PROFILE`.
3. Datasource: install Agroal + the matching `quarkus-jdbc-*`, set
   `db-kind` + `jdbc.url` (`references/datasource-shape.md`). `db-kind` is
   typically build-time-fixed — do not expect one jar to swap driver
   families via runtime profile alone.
4. Replace Spring keys — do not leave `spring.datasource.*` hoping Quarkus
   will honor them (`references/spring-property-map.md`). Prefer
   `@ConfigMapping` over ad-hoc `@ConfigProperty` trees where grouping helps.
5. Stamp exits with a **conjunction** from
   `references/config-profile-load-oracles.md` (validation failure + source
   proof, or `@TestProfile` boots) — not greps of profile name prose.
6. Cross-check class-legal names via `derive-story-oracles` /
   `check-surgical-scopes.py`.

## Pitfalls

- Treating Quarkus profiles like Spring's fully runtime-resolved model.
- Asserting HTTP semantics on a properties-only write-set (wrong-class).
- Leaving Spring keys in place "for compatibility" — Quarkus ignores them.
- Profile-switch oracle that only greps `%h2.` presence without a boot /
  `ConfigValidationException` / DEBUG-origin check.
- Assuming Dev Services removes the need for explicit URLs in every profile
  without checking whether URLs are already set (Dev Services activation
  rules).

## Verification

- Under each claimed profile: app/test boot without
  `ConfigValidationException` for required keys.
- DEBUG/`quarkus.config.log.values` (when used) shows expected source origin
  for profile-scoped keys.
- `check-surgical-scopes.py` accepts the body's exits (no foreign HTTP/etc.).

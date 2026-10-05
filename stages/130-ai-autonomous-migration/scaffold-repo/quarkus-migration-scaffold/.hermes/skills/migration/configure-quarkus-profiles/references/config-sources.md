# Config sources (ordinals)

Quarkus and the app share SmallRye Config (MicroProfile Config). The
`quarkus.` prefix is reserved for platform/extension keys — do not use it for
application-specific properties.

Default lookup order (highest ordinal wins):

| Ordinal | Source |
|--------:|--------|
| 400 | System properties |
| 300 | Environment variables |
| 295 | `.env` in the working directory |
| 260 | `application.properties` in `$PWD/config/` |
| 250 | `application.properties` on the classpath (`src/main/resources/…`) |
| 100 | `META-INF/microprofile-config.properties` |

A lookup walks high→low until a match is found. Env overrides classpath
properties; system properties override both.

`src/test/resources/application.properties` and
`src/main/resources/application.properties` are **separate** sources under the
same rule — not a silent merge.

Inject: `@ConfigProperty(name = "…")` or prefer `@ConfigMapping` for grouped
keys.

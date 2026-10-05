# Per-extension obligations (T-3)

Once an extension is on the classpath, official Quarkus/RHBQ docs require
more than the dependency line. **The needing story owns** the extension **and**
these follow-ons (DD3). Adding the artifact alone is not done.

Severity ranks silent vs loud failure — use with `derive-story-oracles` when
picking exit checks.

## Severity summary

| Extension | Obligation if present | Failure if skipped | Severity |
|-----------|----------------------|--------------------|----------|
| `quarkus-elytron-security-jdbc` | Principal query + 1-based index wiring; `enabled=true` | Silent auth no-op | Highest |
| `quarkus-jdbc-*` | `quarkus-agroal` + `db-kind` + `jdbc.url` | Loud `ConfigValidationException` | High (loud) |
| `quarkus-flyway` | Datasource + `migrate-at-start` (default **false**) + `V*__*.sql` | Silent — schema never migrates | High (silent) |
| `quarkus-hibernate-orm` | Datasource; generation strategy; no mix with `persistence.xml` | Exception or wrong default | Medium-high |
| `quarkus-cache` | Correct cache-key arity / annotations | Silent stale or no-cache | Medium (hard to detect) |
| `quarkus-security` | A **concrete** mechanism must be wired | Silent-permissive (unprotected) | Medium |
| `quarkus-smallrye-health` | None mandatory (endpoints auto-expose) | None for base | Low |
| `quarkus-hibernate-validator` | None mandatory; method validation needs flag | Opt-in "looks right, does nothing" | Low |

## Family notes

### `quarkus-flyway`

- Relies on Quarkus datasource config.
- Default migrations dir: `src/main/resources/db/migration`; naming
  `V<version>__<description>.sql` (double underscore).
- `quarkus.flyway.migrate-at-start` defaults **false** — extension alone is
  inert until set (or multi-ds form `quarkus.flyway."<name>".migrate-at-start`).

### `quarkus-jdbc-*` (+ Agroal)

- Driver extension alone is incomplete — install `quarkus-agroal` and set
  `quarkus.datasource.db-kind` + `quarkus.datasource.jdbc.url`.
- `db-kind` is build-time-fixed; do not expect a runtime profile to swap
  driver families.

### `quarkus-hibernate-orm`

- Needs a JDBC datasource.
- `quarkus.hibernate-orm.database.generation` defaults `none` except
  Dev Services may imply `drop-and-create` when no schema manager is present —
  behavior differs between local Dev Services and real profiles.
- `persistence.xml` and `quarkus.hibernate-orm.*` are **alternatives** —
  mixing raises an exception.
- Panache entities attach to **one** persistence unit only.

### `quarkus-hibernate-validator`

- Default `ValidatorFactory` CDI bean — no mandatory config.
- Do **not** use `META-INF/validation.xml` (unsupported).
- Method-level `@Valid` needs
  `quarkus.hibernate-validator.method-validation.enabled=true`.

### `quarkus-elytron-security-jdbc`

- Highest authoring cost: `quarkus.security.jdbc.enabled=true` plus at least
  one principal-query SQL against **this** schema, plus bcrypt mapper /
  1-based column indices when passwords are hashed.
- Defaults leave auth inert (`enabled=false`).

### `quarkus-security` (base)

- Architecture only until a concrete mechanism (Basic, JDBC realm, OIDC, …)
  is configured. Unconfigured ≠ fail-closed — endpoints stay unprotected.

### `quarkus-smallrye-health`

- Exposes `/q/health`, `/q/health/live`, `/q/health/ready` with no custom
  code. Do not conflate aggregate vs liveness vs readiness in exit criteria.
- Other extensions may register readiness checks automatically.

### `quarkus-cache`

- `@CacheResult(cacheName=…)` is enough to create a cache; no mandatory
  properties.
- Key derivation: no `@CacheKey` → all args form the key; wrong arity →
  silent over-cache or no-cache. Compile/boot will not catch this.

## After `ext add`

1. Open the matching row above.
2. Carry required config / SQL / migrations / annotations in **this** story's
   write-set (or typed `dependency_wait` only after destination-inventory
   citation — do not invent OOS owners).
3. Prefer an executable oracle that catches the family's silent failure mode
   (`derive-story-oracles`).

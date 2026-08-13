# Runnable DB + real security (AD-H §16.6 / AR-2.1 / AR-2.2)

**Status:** binding proving-min (tip checkers + live SecurityAuthzIT green)
**Basis:** skill refs `persistence.md` / `security-config.md`

## AR-2.1 — Runnable DB

Default profile MUST:

1. `db-kind` match JDBC URL family (no `h2` + `jdbc:hsqldb:`)
1b. Tip-bank B7 / Operator E-20260813T111808Z: **refuse** destination
 `db-kind=hsqldb`, any `jdbc:hsqldb:` URL, and `quarkus-jdbc-hsqldb` in the
 pom (Quarkus 3.27+ dropped the extension). Prefer `h2` / `postgresql` /
 `mysql`. Enforced by `check-runnable-db-config.py` (not prose alone).
2. Include `quarkus-jdbc-*` + `quarkus-flyway` in `pom.xml`
3. `quarkus.flyway.migrate-at-start=true` with `V*__*.sql` under a Flyway location
4. `hibernate-orm.database.generation=none` (Flyway owns schema)
5. Clean start → `/q/health` → seeded-entity read; second start idempotent

```bash
python3 .hermes/skills/gates/check-release-readiness/scripts/check-runnable-db-config.py .
```

## AR-2.2 — Real security

1. Empty / placeholder `*AuthenticationConfig` / `DisableSecurityConfig` → **REFUSE**
 completion claims (not “migrated”).
2. Enabled mode: anonymous → **401**, wrong role → **403**, allowed → success.
3. `@RolesAllowed` uses **compile-time constant** role names (AR-3.1).

```bash
python3 .hermes/skills/gates/check-release-readiness/scripts/check-empty-security.py .
```

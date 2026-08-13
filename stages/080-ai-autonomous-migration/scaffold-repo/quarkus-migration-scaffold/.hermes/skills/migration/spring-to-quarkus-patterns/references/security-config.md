# Security config map (A-bar — R-HX.13)

## Sources (versioned official)

| Doc | URL | Accessed |
|-----|-----|----------|
| Quarkus 3.27 — Basic authentication | https://quarkus.io/version/3.27/guides/security-basic-authentication-tutorial | 2026-08-11 |
| Quarkus 3.27 — Authorization of web endpoints | https://quarkus.io/version/3.27/guides/security-authorize-web-endpoints-reference | 2026-08-11 |
| Quarkus 3.27 — JDBC identity provider | https://quarkus.io/version/3.27/guides/security-jdbc | 2026-08-11 |

Living map: quarkusio/skills `migrate-spring-to-quarkus` (prefer on overlap).  
Pedagogical locus: Deandrea et al., 2021 — cite only.  
Internal pack (secondary): `source-analysis/external-review/20260810-artifact-review-quarkus-cites.md`.

## Cards (mechanical map)

| id | Spring | Quarkus | status | note |
|----|--------|---------|--------|------|
| sec-http | `WebSecurityConfigurerAdapter` / `SecurityFilterChain` | `quarkus-security` + `quarkus.http.auth.permission.*` / `policy.*` | REDESIGN | No Spring filter chain |
| sec-roles | `@PreAuthorize` / `@Secured` | `@RolesAllowed` **compile-time constant** or Quarkus property expressions | ADOPT | **FORBIDDEN:** CDI fields as annotation constants |
| sec-basic | Spring HTTP Basic | `quarkus.http.auth.basic=true` + IdentityProvider (JDBC/elytron) | ADOPT | Empty `*AuthenticationConfig` ≠ working stack |
| sec-jdbc | `JdbcUserDetailsManager` / custom `UserDetailsService` | `quarkus-elytron-security-jdbc` + `quarkus.security.jdbc.*` | ADOPT | Clear-password / bcrypt mapper per guide |
| sec-disable | profile-based security off | Quarkus `%profile` props / build-time disable | ADOPT | Disabled mode = tested policy, not silent no-op |
| sec-cdi | `@Component` security helpers | `@ApplicationScoped` | ADOPT | Same CDI rules as `di-config.md` |

### Mechanical transform checklist

1. **pom:** `quarkus-security` + (for JDBC store) `quarkus-elytron-security-jdbc`  
2. **props:** `quarkus.http.auth.basic=true`; permission/policy paths; JDBC queries/mapper  
3. **roles:** `public static final String` / enum / `${…}` — never injected fields  
4. **tests:** anonymous → **401**; wrong role → **403**; allowed → **200**  
5. **refuse:** `check-empty-security.py` before `kanban_complete`

## Worked neutral example (not specimen-bound)

Golden tree: `governance/fixtures/security/golden-basic-authz/`

| Piece | Role |
|-------|------|
| `application.properties` | basic + path permissions + JDBC identity (H2) |
| `Roles.java` | compile-time role constants |
| `AdminResource.java` | `@RolesAllowed(Roles.ADMIN)` |
| `SecurityAuthzIT.java` | 401 / 403 / 200 REST Assured |

Copy the pattern; adapt package/paths to the specimen. Do **not** leave javadoc-only shells.

## Anti-pattern (V-negative)

- Empty or javadoc-only `*AuthenticationConfig` / `*SecurityConfig`  
- Specimen-prefixed toggles like `app.security.enable=true` (or JDBC enabled) without elytron JDBC + real props  
- Claiming “Quarkus security” with only a mapping essay  

Fixture: `governance/fixtures/runnable-db-security/bad-placeholder-security/`  
Gate: `python3 .hermes/skills/gates/check-release-readiness/scripts/check-empty-security.py <tree>` → **rc≠0**

## Runtime proof (must land in dest tests)

| Case | Expect |
|------|--------|
| No `Authorization` on protected path | **401** |
| Basic auth, role not in `@RolesAllowed` | **403** |
| Basic auth, allowed role | **200** (or domain success) |

Passwords one-way encoded; absent from responses/logs.

## Binding stop rule (AR-3.1 / AR-2.2)

1. Do **not** claim “Quarkus security” unless IdentityProvider + policy/`@RolesAllowed` + tests land in the diff.  
2. Placeholder / empty security classes → typed **BLOCK** / refuse `kanban_complete`.  
3. Enabled mode **must** prove 401/403/success.  
4. See also `references/security-anti-essay.md` (write-first / anti-placeholder).

## Validate

```bash
python3 .hermes/skills/gates/check-release-readiness/scripts/check-empty-security.py \
  governance/fixtures/runnable-db-security/bad-placeholder-security   # expect FAIL
# Golden IT (when module runnable / copied into product):
# mvn -q -Dtest=SecurityAuthzIT test
```

## Agent text

Prefer Jakarta `@RolesAllowed`. If the specimen needs Basic auth, add a real
IdentityProvider path (or typed BLOCK). Placeholders that compile but authorize
nothing are a **completion defect**.

## @PreAuthorize → Quarkus (W3 seed delta)

Spring `@PreAuthorize` / method-security expressions must map to Quarkus
security (`@RolesAllowed`, policy config, or IdentityProvider) — **do not**
drop authorization when the specimen's default profile has security disabled.
Cross-check empty-search / missing-role cases before claiming parity.
Build-deps: ensure `quarkus-security` (+ JDBC/elytron provider as needed) land
in the destination POM with the security write, not as a follow-up story.

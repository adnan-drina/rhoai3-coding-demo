# Security config map (cards)

## Source

- Living map: quarkusio/skills `migrate-spring-to-quarkus` (prefer on overlap)
- Pedagogical locus: Deandrea et al., 2021 — cite only
- **Primary (artifact review AR-3.1 / AR-2.2):** Research pack
  `source-analysis/external-review/20260810-artifact-review-quarkus-cites.md`
  — RH Quarkus 3.27 Basic authentication + Authorization of web endpoints

## Cards

| id | Spring | Quarkus | status | note |
|----|--------|---------|--------|------|
| sec-http | `WebSecurityConfigurerAdapter` / SecurityFilterChain | `quarkus-security` + HTTP authz config | REDESIGN | No Spring Security filter chain |
| sec-roles | `@PreAuthorize` / `@Secured` / SpEL role beans | `@RolesAllowed` with **compile-time constant** role names **or** Quarkus property expressions | ADOPT | **FORBIDDEN:** CDI instance fields as annotation constants (AR-3.1) |
| sec-basic | Spring HTTP basic | IdentityProvider extension + `quarkus.http.auth.basic=true` | ADOPT | Empty `*AuthenticationConfig` is **not** a working stack |
| sec-disable | profile-based security off | Quarkus profile / build-time disable | ADOPT | Disabled mode = separate tested policy, not silent no-op |
| sec-cdi | `@Component` security helpers | `@ApplicationScoped` | ADOPT | Same CDI rules as `di-config.md` |

## Binding stop rule (AR-3.1 / AR-2.2)

1. Do **not** claim “Quarkus security” unless real authn/authz wiring lands in the
   diff (IdentityProvider + policy / `@RolesAllowed` + tests).
2. **Empty / placeholder** security classes → typed **BLOCK** or refuse
   `kanban_complete` — not honest “migrated.”
3. Enabled mode **must** prove: anonymous protected → **401**; wrong role → **403**;
   allowed role → success. Passwords one-way encoded; absent from responses/logs.
4. Role names for annotations: `public static final String` / enum constants /
   Quarkus config expressions — **never** injected bean fields.

## Agent text

Prefer Jakarta `@RolesAllowed` over Spring annotations. If the specimen needs
Basic auth, add a real IdentityProvider path (or typed BLOCK naming the gap).
Placeholders that compile but authorize nothing are a **completion defect**, not
a progress milestone.

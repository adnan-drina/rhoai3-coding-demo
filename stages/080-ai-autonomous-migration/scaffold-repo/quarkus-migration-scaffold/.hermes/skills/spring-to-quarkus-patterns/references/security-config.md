# Security config map (cards)

## Source

- Living map: quarkusio/skills `migrate-spring-to-quarkus` (prefer on overlap)
- Pedagogical locus: Deandrea et al., 2021 — cite only

## Cards

| id | Spring | Quarkus | status | note |
|----|--------|---------|--------|------|
| sec-http | `WebSecurityConfigurerAdapter` / SecurityFilterChain | `quarkus-security` + HTTP authz config | REDESIGN | No Spring Security filter chain |
| sec-roles | `@PreAuthorize` / `@Secured` | `@RolesAllowed` (Jakarta) / Quarkus policy | ADOPT | Align role names with `Roles` constants |
| sec-basic | Spring HTTP basic | Quarkus basic auth (when enabled) | ADOPT | Config properties, not Spring beans |
| sec-disable | profile-based security off | Quarkus profile / build-time disable | ADOPT | Keep demo disable path explicit |
| sec-cdi | `@Component` security helpers | `@ApplicationScoped` | ADOPT | Same CDI rules as `di-config.md` |

## Agent text

Do **not** claim “Quarkus security” unless real authz/authn wiring lands in the
diff (S-002 lesson). Placeholders / empty configs → typed BLOCK or honest
summary. Prefer Jakarta `@RolesAllowed` over Spring annotations.

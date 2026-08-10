# Extension — Security write-first / anti-essay (AD-011 / R-M3.29)

**Skill:** `spring-to-quarkus-patterns`  
**Layer:** B (L2 reference overlay)  
**Sources:** Architect R-M3.29 `E-20260810T230310Z` · AD-011 R-AD011.2

This file is an **additive** extension. Workers must `skill_view` the base
`spring-to-quarkus-patterns` skill **and** this path when migrating
`security/**` / S-005-class cards (Hermes does not merge overlays).

## Rules

1. **Hard invoke first** — before any destination edit: `skill_view` base skill,
   then `references/security-config.md`, then this extension.
2. **Write-first** — migrate one security file at a time from checkpoint `next`
   (`Roles` → configs, or body order). Stamp after each successful dest write.
3. **Mechanical map** — Spring Security Java config → Quarkus / SmallRye JWT or
   `quarkus-spring-security` equivalents per `security-config.md`. Do not redesign
   the auth product surface in Reasoning.
4. **Anti-essay** — forbid multi-kB Spring-Security-on-Quarkus architecture
   debates. Cite the refs; then edit. First dest write should land within a few
   tool turns after hard-invoke.
5. **Never SOUL** — behavior changes belong here or in a workshop overlay, not
   in `SOUL.md`.

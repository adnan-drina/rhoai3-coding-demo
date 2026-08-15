# Extension — Security write-first / anti-essay (AD-011 / R-M3.29)

**Skill:** `spring-to-quarkus-patterns`  
**Layer:** B (L2 reference overlay)  
**Sources:** Architect R-M3.29 `E-20260810T230310Z` · AD-011 R-AD011.2

This file is an **additive** extension (authoring source under `extensions/`).
Create/init syncs it into `.hermes/skills/migration/spring-to-quarkus-patterns/references/`
(R-M3.32). Workers `skill_view` the in-skill path `references/security-anti-essay.md`
when migrating `security/**` / S-005-class cards.

## Rules

1. **Hard invoke first** — before any destination edit: `skill_view` base skill,
   then `references/security-config.md`, then `references/security-anti-essay.md`.
2. **Write-first** — migrate one security operand at a time from checkpoint `next`
   (Roles → configs → `application.properties` → pom deps, or body order). Stamp
   after each successful dest write.
3. **Mechanical map** — Spring Security Java config → Quarkus
   `quarkus-security` + `quarkus-elytron-security-jdbc` + `quarkus.http.auth*` /
   JDBC userstore props per `security-config.md` / AR-2.2. Do not redesign the
   auth product surface in Reasoning or in javadoc-only shells.
4. **Worked example** — copy pattern from
   `.hermes/skills/harness/dispatch-phase/fixtures/security/golden-basic-authz/` (Roles + resource + props +
   `SecurityAuthzIT` 401/403/200). Official cites live in `security-config.md`.
5. **Anti-essay / anti-placeholder (R-M3.39)** — forbid multi-kB architecture
   debates **and** javadoc-only `*AuthenticationConfig` that claim “declarative
   in properties” without writing those properties + deps. Run
   `check-empty-security.py .` before `kanban_complete`. Negative fixture:
   `.hermes/skills/harness/validate-contracts/fixtures/runnable-db-security/bad-placeholder-security/`.
6. **Never SOUL** — behavior changes belong here or in a workshop overlay, not
   in `SOUL.md`.

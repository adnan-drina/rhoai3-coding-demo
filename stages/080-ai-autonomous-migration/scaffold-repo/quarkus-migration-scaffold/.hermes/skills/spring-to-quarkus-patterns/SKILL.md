---
name: spring-to-quarkus-patterns
description: >
  On-demand Spring→native Quarkus mapping cards for IMPLEMENT (REST, DI/config,
  persistence). Prefer quarkusio/skills Full-path when rows overlap; book fills
  pedagogical gaps only. Not a gate and not a transform admit table.
---

# Spring → Quarkus patterns (IMPLEMENT)

Load for M3 HARVEST/REDESIGN *how* (AD-H §17 pri-5). Does **not** authorize
new behaviour, weaken G-1…G-4, or replace free-primitives / MTA.

## Invariants (conflict with AGENTS → AGENTS wins)

- **Native Quarkus only** — reject `quarkus-spring-*` compatibility extensions.
- Prefer **constructor injection**; default services/repos `@ApplicationScoped`.
  Prefer `@ApplicationScoped` over `@Singleton` when the type must be mockable
  in tests (`@Singleton` is not client-proxyable).
- Schema migrations: **Flyway** (or project-declared equivalent) — do not invent
  ad-hoc DDL on boot.
- Consult order: packet → brief → legacy RO → destination/`AGENTS.md` → this skill.

## References (progressive disclosure)

| File | Use when |
|------|----------|
| `references/rest-annotations.md` | JAX-RS / RESTEasy → `quarkus-rest` annotation map |
| `references/di-config.md` | Scopes, config properties, profiles |
| `references/persistence.md` | Spring Data → Panache repository default |

## Source policy

- Prefer Apache-2.0 `quarkusio/skills` `migrate-spring-to-quarkus` wording for
  overlapping Full-path rows.
- Book citations are **locus only** (Deandrea et al., *Quarkus for Spring
  Developers*, 2021, Table/Ch) — paraphrased cards; **no** verbatim chapter
  paste or `tmp/` extract in this tree.
- Modernize names: `javax`→`jakarta`, RESTEasy Classic → `quarkus-rest` /
  `quarkus-rest-jackson` as used by this scaffold (RH BOM 3.27).

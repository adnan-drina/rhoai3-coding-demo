# REJECT — Quarkus Spring compatibility layers (mechanism)

**Skill:** `spring-to-quarkus-patterns`
**Sources:** Operator E-20260813T162429Z · Architect E-20260813T164142Z · AGENTS "Native Quarkus only"
**Input (cite only):** Red Hat Developer Quarkus–Spring compatibility cheat sheet (PDF; copyrighted) — paraphrase + locus, never paste.

This file is **not** a migration how-to. It exists so a worker who reaches for
`quarkus-spring-*` knows **what the layer actually does** and **why this harness
forbids it**. Native form lives in sibling References.

## Standing invariant

Destination `pom.xml` must not declare `quarkus-spring-*`. Claim accuracy refuses
a completion summary that names "Quarkus" while the diff still carries a compat GAV.

## Mechanism

Official Quarkus Spring-compat material (cheat sheet locus, paraphrased) states
that Quarkus **does not start a Spring Application Context** and **does not run
Spring infrastructure classes**. Spring types/annotations are used to **read
metadata**. The annotations survive on the source; Spring runtime semantics do
**not** execute. That is a **metadata shim**, not Spring. For faithfulness
judgement, a green build under the shim is the failure mode: compile/boot can
pass while behaviour diverges from evidence.

## Per-layer REJECT cards (structural; specimen-free)

| id | Compat surface | What the shim does | Why faithfulness fails |
|----|----------------|--------------------|------------------------|
| rej-di | `quarkus-spring-di` | Maps selected Spring stereotypes into Arc | Lifecycle/proxies/profiles are Arc rules wearing Spring names |
| rej-web | `quarkus-spring-web` | Reads MVC-ish annotations into Quarkus REST | Advice/path/filter semantics are not Spring MVC |
| rej-props | `quarkus-spring-boot-properties` | Accepts some Boot property shapes | Dual config trees hide which source won |
| rej-sec | Spring Security compat | Maps a subset into Quarkus security | Empty config shells pass compile; fail 401/403 proof |
| rej-data | `quarkus-spring-data-jpa` | Subset of Spring Data on Hibernate/Panache | Unsupported APIs fail late; "Spring Data" claim without Spring semantics |
| rej-data-rest | spring-data-rest compat | Auto-exported repository HTTP | REST contract must come from evidence, not auto-export |
| rej-cache | spring-cache compat | Annotation cache names → Quarkus cache | Keys/TTL not proven by annotation presence |
| rej-sched | spring-scheduled compat | `@Scheduled`-style → Quarkus scheduler | Overlap rules are Quarkus scheduler |
| rej-cfg-client | `quarkus-spring-cloud-config-client` | Boot-cloud client shape | External config is platform/Managed Scope here |

### Unsupported-subset trap (Data JPA — cite only)

Cheat sheet Data JPA unsupported catalogue (pp.4–5 locus, paraphrased categories):
Query-by-Example executor methods, QueryDSL, customizing the base repository type,
`Future`-typed returns, certain `@Query` native/named forms. Prefer native cards
in `persistence.md`.

## Authorize / Forbid

| Authorize | Forbid |
|-----------|--------|
| Citing this file when refusing a compat GAV | Adding `quarkus-spring-*` "to unblock" |
| Pointing to sibling refs for native form | Treating the cheat sheet as IMPLEMENT how-to |
| Blocking Done text that requires Spring annotations on destination | Verbatim paste of cheat-sheet prose/code; specimen literals (R-SK.5) |

## Agent text

If the next step is "add `quarkus-spring-*`," stop. Cite this file in the BLOCK /
Needs note; do not essay classpath architecture.

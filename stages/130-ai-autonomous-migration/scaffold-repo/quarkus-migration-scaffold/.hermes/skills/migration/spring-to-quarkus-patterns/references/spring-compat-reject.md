# REJECT — Quarkus Spring compatibility layers (mechanism)

> **Superseded 2026-09-09 (ADR-001, `decisions.yaml`): the destination follows the Spring-compatibility path.** The `quarkus-spring-*` extensions listed in `.hermes/planning/catalogs/compat-mapping.json` are the baseline, not a rejection. Read the mechanism notes below as the list of Spring features the compatibility layer does **not** provide (no Spring `ApplicationContext`; those go native). Any "native only" instruction below is historical.


**Skill:** `spring-to-quarkus-patterns`
**Sources:** Operator E-20260813T162429Z · Architect E-20260813T164142Z · AGENTS "Native Quarkus only"
**Input (cite only):** Red Hat Developer Quarkus–Spring compatibility cheat sheet (PDF; copyrighted) — paraphrase + locus, never paste.

This file is **not** a migration how-to. ADR-001 put the destination on the
Spring-compatibility path; `compat-mapping.json` is the allow-list. Read the
mechanism notes as **what the shim does not provide**. Native form for
features the shim omits lives in sibling References (for persistence,
`references/spring-data-jpa.md` — not a Panache rewrite).

## Standing invariant

Destination `pom.xml` may declare only the `quarkus-spring-*` extensions the
catalog maps. Adding an unmapped compat GAV, or claiming full Spring runtime
semantics from the shim, is still a defect. Claim accuracy refuses a
completion summary that names a technology the diff does not show.

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
| rej-data | `quarkus-spring-data-jpa` **unsupported subset** | Build-time generation of a **subset** of Spring Data | Keep ADR-004; do not use QueryDSL / QBE / `JpaSpecificationExecutor` / native `@Query` / `Future` returns / `@Lock`. Those fail at augment (`UnableToParseMethodException`) or at invoke. Playbook: `spring-data-jpa.md` |
| rej-data-rest | spring-data-rest compat | Auto-exported repository HTTP | REST contract must come from evidence, not auto-export |
| rej-cache | spring-cache compat | Annotation cache names → Quarkus cache | Keys/TTL not proven by annotation presence |
| rej-sched | spring-scheduled compat | `@Scheduled`-style → Quarkus scheduler | Overlap rules are Quarkus scheduler |
| rej-cfg-client | `quarkus-spring-cloud-config-client` | Boot-cloud client shape | External config is platform/Managed Scope here |

### Unsupported-subset trap (Data JPA — cite only)

Official guide + cheat sheet Data JPA unsupported catalogue (paraphrased):
Query-by-Example executor methods, QueryDSL, `JpaSpecificationExecutor`,
customizing the base repository type, `Future`-typed returns, native/named
`@Query`, `@Lock`. Stay on `quarkus-spring-data-jpa` for the supported subset
(`references/spring-data-jpa.md`); do not "fix" those gaps by adding Panache.

## Authorize / Forbid

| Authorize | Forbid |
|-----------|--------|
| Citing this file when refusing an **unmapped** compat GAV or an unsupported Data JPA API | Adding an unmapped `quarkus-spring-*` "to unblock", or rewriting ADR-004 repositories as Panache |
| Pointing to `spring-data-jpa.md` for the supported subset | Treating the cheat sheet as IMPLEMENT how-to |
| Blocking Done text that claims full Spring runtime semantics | Verbatim paste of cheat-sheet prose/code; specimen literals (R-SK.5) |

## Agent text

If the next step is "add an unmapped `quarkus-spring-*`" or "replace Spring Data
with Panache on this specimen," stop. Cite this file and ADR-004; do not essay
classpath architecture.

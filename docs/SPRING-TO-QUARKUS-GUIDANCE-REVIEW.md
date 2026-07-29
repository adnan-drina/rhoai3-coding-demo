# Spring Boot → Quarkus guidance review (analysis only)

Written 2026-07-29.

**Status: analysis complete.** Tier A **Implemented (V6)** in the scaffold
guides/skills — held with other scaffold work until
[`V5-FINDINGS-AND-PREP.md`](V5-FINDINGS-AND-PREP.md) prep is signed off for
harness process changes. Implementation sequencing (when approved):
[`V5-HARNESS-IMPROVEMENT-PLAN.md`](V5-HARNESS-IMPROVEMENT-PLAN.md). Tier B/C
from this review stay deferred; V5 *process* defects are tracked in the
findings catalog (not as this file’s Tier B).

This file is the **umbrella** for the guidance review. Detailed source
notes live in the companion docs listed below; this file consolidates
verdicts, hard constraints, and a proposed enrichment backlog.

## 1. Review scope

| # | Source | Companion doc | Role in review |
|---|---|---|---|
| 1 | [OpenRewrite Spring to Quarkus catalog](https://docs.openrewrite.org/recipes/quarkus/spring) + [SpringBootToQuarkus](https://docs.openrewrite.org/recipes/quarkus/spring/springboottoquarkus) | [OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md](OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md) | Executable mechanical transforms |
| 2 | [snowdrop/springboot-to-quarkus-migration-guide](https://github.com/snowdrop/springboot-to-quarkus-migration-guide) | [SNOWDROP-SPRINGBOOT-TO-QUARKUS-GUIDE.md](SNOWDROP-SPRINGBOOT-TO-QUARKUS-GUIDE.md) | Rule-card schema; M1 preflight ideas |
| 3 | [Markus Eisele walkthrough](https://www.the-main-thread.com/p/spring-to-quarkus-migration-guide) | [MAIN-THREAD-SPRING-TO-QUARKUS.md](MAIN-THREAD-SPRING-TO-QUARKUS.md) | End-to-end tutorial patterns |
| 4 | *Quarkus for Spring Developers* (Red Hat, Deandrea/Oh/Moulliard, 2021) — `tmp/Quarkus-For-Spring-Developers-Red-Hat.pdf` | [QUARKUS-FOR-SPRING-DEVELOPERS.md](QUARKUS-FOR-SPRING-DEVELOPERS.md) | Pattern bible (native Quarkus; 2021) |
| 5 | [quarkusio/skills](https://github.com/quarkusio/skills) `migrate-spring-to-quarkus` | [QUARKUSIO-SKILLS-MIGRATE-SPRING.md](QUARKUSIO-SKILLS-MIGRATE-SPRING.md) | **Best living Full-path annotation/config/dependency maps** (agent skill; WIP) |

**Harness under review (unchanged):**
`stages/080-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/`  
Destination baseline: Red Hat Quarkus **3.27.3.SP1**
(`com.redhat.quarkus.platform:quarkus-bom:3.27.3.SP1-redhat-00002`), Java 21,
`quarkus-rest-jackson`, side-by-side legacy → modernized scaffold.

## 2. Hard constraints (do not relax in any future enrichment)

These are existing harness laws. External guidance that conflicts is
**rejected**, not adopted.

| Constraint | Rationale |
|---|---|
| Native Quarkus only — no `quarkus-spring-*` destination deps | Compat hides the migration; MAPPINGS / Windup joins already encode this |
| Side-by-side scaffold; RH BOM owns the destination pom | Not in-place Spring module → community BOM |
| Delete `@SpringBootApplication` / main (no `Quarkus.run` default) | Quarkus has no required main |
| Constructor injection only | Sonar / REST & persistence skills |
| Flyway + `hibernate-orm.database.generation=validate` for DB apps | Factory boot contract; book omits Flyway — we do not |
| Prefer `quarkus-rest` / `quarkus-rest-jackson` over RESTEasy Classic | Scaffold reality (book-era RESTEasy names must be modernized) |
| Process stays M1–M5 + sensors + factory gate | Books/blogs/recipes do not replace the harness |

## 3. Source verdicts (short)

### 3.1 Red Hat book + quarkusio skills — pattern authority

**Book** matches our **native** thesis; best for narrative REST/DI tables
(2021 names need modernization).  
**quarkusio/skills** is the best *current* Full-path catalog (`quarkus-rest`,
Flyway property map, naming-strategy warning, InjectMock package, richer
annotation coverage). Already partially harvested into MAPPINGS (2026-07).
Reject the skill’s **recommended Spring-compat strategy** and interactive
orchestrator; take **Full** reference columns only.

- Book: [QUARKUS-FOR-SPRING-DEVELOPERS.md](QUARKUS-FOR-SPRING-DEVELOPERS.md)
- Skills: [QUARKUSIO-SKILLS-MIGRATE-SPRING.md](QUARKUSIO-SKILLS-MIGRATE-SPRING.md)

### 3.2 OpenRewrite Spring→Quarkus — curated recipes only

- **Do not** wire the full `SpringBootToQuarkus` composite (bundles Spring
  compat + community BOM + keep-main).
- **Do** (later) consider a harness-owned subset of **source** recipes:
  CDI stereotypes, Web→JAX-RS, `@Value`→`@ConfigProperty`, ConfigMapping,
  validation, transactional, testing, actuator→health, Web→Quarkus REST.
- Prefer named sub-recipes; gate on Boot major (composite wants Boot 3.x).
- Standing ops notes: [OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md](OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md) §7–§9.

### 3.3 Snowdrop guide — schema + preflights only

- Borrow rule-card fields (Goal, Parameters, Effort, Order, Konveyor ref,
  Instructions, BEFORE/AFTER) when writing MAPPINGS/brief cards.
- Candidate M1 preflights: multi-module `<modules>`; optional license note.
- No further upstream tracking planned.
- Detail: [SNOWDROP-SPRINGBOOT-TO-QUARKUS-GUIDE.md](SNOWDROP-SPRINGBOOT-TO-QUARKUS-GUIDE.md).

### 3.4 Main Thread blog — small pattern deltas

- Already aligned on scaffold-first, JAX-RS, `@ConfigMapping`, `@QuarkusTest`.
- Borrow: datasource property BEFORE/AFTER; PanacheRepository over active
  record; `@QuarkusIntegrationTest` wording; extension→model→resource→config→test
  ordering phrase.
- Reject: compat-as-recommended-path, field injection, `drop-and-create`.
- Detail: [MAIN-THREAD-SPRING-TO-QUARKUS.md](MAIN-THREAD-SPRING-TO-QUARKUS.md).

## 4. Consolidated recommendations

Ordered for a future PR series after findings prep sign-off. **Tier A:**
candidate WS-A in the improvement plan — mark **Implemented** here only when
a docs PR lands. **Tier B/C:** deferred. V5 process defects live in
[`V5-FINDINGS-AND-PREP.md`](V5-FINDINGS-AND-PREP.md), not in this Tier B table.

### Tier A — documentation in scaffold guides (highest value)

Enrich **guides agents already read** (not orchestration):

| Proposed target | Proposed content (from review) |
|---|---|
| `.hermes/skills/migration-harness/MAPPINGS.md` | Diff in quarkusio `annotation-map.md` / `config-map.md` / `dependency-map.md` **Full** columns (primary); book Ch 3 REST tables as backup; ExceptionHandler/Advice → `@ServerExceptionMapper`; DI nuances (`@Primary`, `@Conditional*`, cache, StartupEvent); Flyway + naming-strategy + `%prod` datasource notes (keep `validate`); Spring Data → Panache**Repository**; REJECT `quarkus-spring-*`; Snowdrop rule-card shape; OpenRewrite curated recipes as future `recipe:` candidates (not wired) — **Implemented (V6)** |
| `.opencode/skills/quarkus-rest-conventions.md` | Global mapper vs `@RestControllerAdvice`; void=204; cite book tables — **Implemented (V6)** |
| `.opencode/skills/quarkus-persistence-conventions.md` | Spring Data ↔ PanacheRepository example; restate Flyway+validate (book gap) — **Implemented (V6)** |
| `.opencode/skills/project-test-standards.md` | Shared `@QuarkusTest` lifecycle vs SpringBootTest; optional `@QuarkusIntegrationTest` for packaged artifact — **Implemented (V6)** |
| `AGENTS.md` | `@ApplicationScoped` default; never add `quarkus-spring-*` — **Implemented (V6)** |
| `PLANNING.md` / briefs | Optional: extensions→models→resources→config→tests ordering line; rule-card richness in “Decided target shapes” — **Implemented (V6)** (PLANNING + BRIEF-TEMPLATE + SEQUENCING oracles) |

### Tier B — harness process (optional, separate decisions)

| Proposal | Source | Notes |
|---|---|---|
| M1 multi-module detect (warn/fail) | Snowdrop | Useful for BYO; cart is single-module |
| Optional license note in profile/`debt.md` | Snowdrop | Non-blocking |
| Curated OpenRewrite Spring source recipes in `recipe-transform.sh` | OpenRewrite | Only after MAPPINGS list + cart staging dry-run; pin versions; exclude compat/BOM/main |
| Reclassify some Windup joins `infer`→`recipe` | OpenRewrite | Only after fidelity-green staging proof |

### Tier C — out of scope / reject

| Item | Why |
|---|---|
| Full OpenRewrite `SpringBootToQuarkus` composite | Compat + community BOM + main strategy |
| Quarkus Spring compat as incremental destination | Native-only policy |
| Community BOM / “latest Quarkus” | RH 3.27.3.SP1 pin |
| `MigrateToQuarkus_v3_26_0` style upgrade aggregates | Wrong job (Quarkus→Quarkus); scaffold already past 3.26 |
| Panache active record or `drop-and-create` as defaults | Persistence skill / factory |
| Field injection | Sonar |
| Worker-authored K8s/JIB competing with factory | Platform owns ship |
| Replacing M1–M5 with any external guide’s process | Harness owns process |

## 5. Suggested PR sequence

Canonical sequence (includes V5 process work):  
[`V5-HARNESS-IMPROVEMENT-PLAN.md`](V5-HARNESS-IMPROVEMENT-PLAN.md) §4.

Guidance-only slice (this review’s Tier A):

1. **Implemented (V6):** MAPPINGS + OpenCode REST/persistence/test skills + AGENTS + PLANNING/BRIEF/SEQUENCING — docs/skills only; harness scripts unchanged.  
2. (Optional, separate decision) M1 multi-module preflight.  
3. (Optional, later) Curated OpenRewrite staging recipes + inventory joins — after cart dry-run.

## 6. Companion documents

| Document | Contents |
|---|---|
| [QUARKUS-FOR-SPRING-DEVELOPERS.md](QUARKUS-FOR-SPRING-DEVELOPERS.md) | Chapter-by-chapter book analysis |
| [QUARKUSIO-SKILLS-MIGRATE-SPRING.md](QUARKUSIO-SKILLS-MIGRATE-SPRING.md) | quarkusio/skills migrate-spring-to-quarkus review |
| [OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md](OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md) | Recipe adopt/adapt/reject + catalog matrix |
| [MAIN-THREAD-SPRING-TO-QUARKUS.md](MAIN-THREAD-SPRING-TO-QUARKUS.md) | Blog borrows |
| [SNOWDROP-SPRINGBOOT-TO-QUARKUS-GUIDE.md](SNOWDROP-SPRINGBOOT-TO-QUARKUS-GUIDE.md) | Rule cards + M1 preflights |
| [MTA-TO-SPEC-MAPPING.md](MTA-TO-SPEC-MAPPING.md) | Existing findings→spec design |
| [MIGRATION-PROCESS-REDESIGN.md](MIGRATION-PROCESS-REDESIGN.md) | Existing M-process |
| [V5-FINDINGS-AND-PREP.md](V5-FINDINGS-AND-PREP.md) | V5 findings catalog + prep gate (no implement yet) |
| [V5-HARNESS-IMPROVEMENT-PLAN.md](V5-HARNESS-IMPROVEMENT-PLAN.md) | Candidate WS-A / WS-B PR sequence (held) |

## 7. Bottom line

External guidance is rich enough to **enrich agent-facing catalogs and
skills** later. For pattern tables, prefer **quarkusio/skills Full columns**
(current) plus the Red Hat book (depth); OpenRewrite may later expand
mechanical HARVEST; Snowdrop only contributes card shape and preflight
ideas. Do not start scaffold PRs until V5 findings prep is signed off; keep
guide enrichment (this review’s Tier A) separate from harness process fixes.

# Quarkus for Spring Developers — harness bible analysis

Written 2026-07-29. Methodical chapter review of the Red Hat book against
the stage 080 Spring Boot → Quarkus harness. **Analysis only — no scaffold
changes.** Consolidated backlog:
[SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md](SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md).

**Source (local):** `tmp/Quarkus-For-Spring-Developers-Red-Hat.pdf`  
**Text extract (gitignored):** `tmp/quarkus-for-spring-developers.txt`  
**Bibliographic:** Eric Deandrea with Daniel Oh and Charles Moulliard,
*Quarkus for Spring Developers*, Red Hat Developer, **2021** (149 pages).  
Also references the
[Quarkus–Spring cheat sheet](https://developers.redhat.com/cheat-sheets/quarkus-spring-cheat-sheet)
and MTA for analyzing Spring Boot apps.

## 0. How to use this book with our harness

| Principle | Application |
|---|---|
| **Authority** | Prefer this book's *native* Spring↔Quarkus mappings when enriching guides. OpenRewrite/Snowdrop/blog notes are secondary. |
| **Age** | 2021. Translate runtime names: RESTEasy Classic/Reactive → today's **`quarkus-rest`** (scaffold uses `quarkus-rest-jackson`); `javax.*` → `jakarta.*`; pin RH BOM **3.27.3.SP1**, not book-era community versions. |
| **Thesis match** | Book lists Spring API extensions (Table 2.3) but states they are **not the focus** — remainder shows Spring patterns implemented with **native Quarkus**. That matches our MAPPINGS native-only policy. |
| **What the book is not** | Not an autonomous migration process (no M1–M5, no sensors). It is the **destination pattern catalog**. Our harness supplies process + gates. |
| **Flyway gap** | Book notes Flyway/Liquibase exist but **does not teach them**. Our `quarkus-persistence-conventions` (Flyway + `validate`) remains law for DB stories. |

Companion analyses (narrower sources):

- [OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md](OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md) — executable recipes  
- [MAIN-THREAD-SPRING-TO-QUARKUS.md](MAIN-THREAD-SPRING-TO-QUARKUS.md) — short tutorial  
- [SNOWDROP-SPRINGBOOT-TO-QUARKUS-GUIDE.md](SNOWDROP-SPRINGBOOT-TO-QUARKUS-GUIDE.md) — rule-card schema / preflights  

---

## 1. Book structure

| Ch | Title | Pages (approx) | Harness relevance |
|---|---|---|---|
| 1 | Introducing Quarkus | 8–18 | Narrative only (container-first, standards, DX) |
| 2 | Getting Started with Quarkus | 19–44 | **High** — extensions vs starters, config, DI scopes, testing, no main class |
| 3 | RESTful Applications | 45–70 | **Highest** — annotation maps, returns, exception mappers, OpenAPI, SSE |
| 4 | Persistence | 71–97 | **High** for DB apps — Panache active record vs repository; reactive Panache; Flyway noted but not taught |
| 5 | Event-Driven Services | 98–121 | **Medium/BYO** — Vert.x `@ConsumeEvent`, SmallRye Reactive Messaging/Kafka, Knative |
| 6 | Building Applications for the Cloud | 122–146 | **High for M5/ops** — health, env/ConfigMaps, metrics/tracing, K8s manifests; factory already covers much |
| — | Appendix | 147–148 | Blocking vs reactive primer |

---

## 2. Chapter-by-chapter findings

### Chapter 1 — Introducing Quarkus

**Content:** Java/Spring history, microservices challenges, Quarkus pillars
(container first, standards, developer joy, unify reactive/imperative).

**Borrow:** None for agent packets. Useful only if stage README narrative
needs a Red Hat–aligned “why Quarkus” sentence.

**Harness status:** Already covered by stage 080 story; no MAPPINGS change.

---

### Chapter 2 — Getting Started with Quarkus

#### 2.1 Extensions vs Spring starters (Table 2.2) — ADOPT into MAPPINGS

Book maps common Quarkus extensions to Spring Boot starters. Modernize
names when importing (`quarkus-resteasy-*` → `quarkus-rest` / 
`quarkus-rest-jackson` for our scaffold).

| Quarkus (book) | Spring Boot starter | Our scaffold / policy |
|---|---|---|
| `quarkus-resteasy-jackson` / `quarkus-resteasy-reactive-jackson` | `spring-boot-starter-web` / `webflux` | Use **`quarkus-rest-jackson`** |
| `quarkus-hibernate-orm-panache` | `spring-boot-starter-data-jpa` | Optional; EntityManager + Flyway also valid |
| `quarkus-hibernate-validator` | `spring-boot-starter-validation` | ADOPT for `validateInput` |
| `quarkus-oidc` / `quarkus-oidc-client` / `quarkus-smallrye-jwt` | OAuth2 / security starters | DEFER (not cart) |
| `quarkus-cache`, `quarkus-redis-client`, `quarkus-mailer`, `quarkus-quartz`, JMS | matching starters | DEFER / BYO catalog |
| `quarkus-mongodb-panache` | Mongo starters | DEFER |

**Enrichment:** Add an “Extensions ↔ starters” subsection to MAPPINGS,
explicitly naming today's `quarkus-rest*` artifacts.

#### 2.2 Spring API extensions (Table 2.3) — DOCUMENT AS REJECT PATH

Book lists Spring Boot Properties, Cache, Cloud Config, DI, Data JPA,
Data REST, Scheduled, Security, Web extensions — and notes they help
**incremental** migration / MTA suggestions. Also: *“they are not the
focus of this book.”*

**Harness:** Keep REJECT for destination code (same as OpenRewrite
`AddSpringCompatibilityExtensions`). Optionally one MAPPINGS note:
“MTA may suggest these; harness destination is native — do not add
`quarkus-spring-*` dependencies.”

#### 2.3 No main class / project layout (Table 2.4) — ALREADY ALIGNED

Quarkus has no required `@SpringBootApplication` / main. Unified
`application.properties` (profiles via `%profile.key` syntax).

**Harness:** MAPPINGS already deletes main. Profiles table (`dev` /
`test` / `prod`, `%dev.key=value`, `QUARKUS_PROFILE`) is worth adding
to MAPPINGS or AGENTS if agents invent Spring-style
`application-dev.properties` filenames.

#### 2.4 Configuration — ADOPT / STRENGTHEN

Book teaches:

- `@ConfigProperty` (+ `defaultValue`, `Optional<>`)
- Type-safe `@ConfigMapping(prefix = …)` with nested interfaces and
  bean-validation-style constraints on mapping types
- Profile-specific properties: `%dev.`, `%test.`, `%prod.`
- Profile activation: `-Dquarkus.profile=`, `QUARKUS_PROFILE`
  (vs Spring `spring.profiles.active`)

**Harness:** MAPPINGS already has `@Value` → `@ConfigProperty` and
`@ConfigurationProperties` → `@ConfigMapping`. **Borrow:** richer
`@ConfigMapping` examples (nested groups, defaults, validation) into
MAPPINGS or a small snippet in REST/persistence skills; profile syntax
table.

#### 2.5 DI scopes (Table 2.8) — ADOPT nuance

| Quarkus | Spring | Note |
|---|---|---|
| `@ApplicationScoped` | `@Scope("singleton")` | **Default recommendation** — proxied, mockable, live-reload friendly |
| `@Singleton` | `@Scope("singleton")` | Eager, no proxy, **not mockable** — use only with a reason |
| `@RequestScoped` | `@Scope("request")` | |
| `@Dependent` | `@Scope("prototype")` | |
| `@SessionScoped` | `@Scope("session")` | Needs undertow; usually avoid for cloud |

Book rule of thumb: **prefer `@ApplicationScoped` over `@Singleton`**.

**Harness:** MAPPINGS maps `@Service` → `@ApplicationScoped` already.
**Borrow:** explicit “do not use `@Singleton` unless justified” into
MAPPINGS / AGENTS (aligns with testability and our REDESIGN CDI beans).

Constructor injection with `@ConfigProperty` in the constructor is shown
— matches our constructor-injection Sonar rule (book is less strict about
field injection elsewhere; **keep our stricter rule**).

#### 2.6 Testing — ALREADY ALIGNED + SMALL BORROW

- `@QuarkusTest` ≈ `@SpringBootTest`, but Quarkus reuses one app instance
  across test classes (Spring often restarts per class)
- Continuous testing in dev mode
- Native image testing (`@NativeImageTest` in book era)

**Borrow:** one sentence in `project-test-standards` about shared test
application lifecycle (don't assume Spring-style per-class context
reset). Native-image test annotation names may have changed — verify
against Quarkus 3.27 docs before copying literally.

#### 2.7 Cheat sheet pointer — ADOPT as reference link

Book points to Red Hat Quarkus–Spring cheat sheet. Add link under
MAPPINGS “Discovering further recipes” / References — agents should not
load the whole sheet; humans/enrichment pass should.

---

### Chapter 3 — RESTful Applications — PRIMARY MAPPINGS SOURCE

Book uses JAX-RS via RESTEasy (Classic vs Reactive). For 2026 harness,
implement with **`quarkus-rest`** / `quarkus-rest-jackson`.

#### 3.1 HTTP method annotations (Table 3.1) — ADOPT (largely present)

| Quarkus JAX-RS | Spring |
|---|---|
| `@GET` | `@GetMapping` |
| `@POST` | `@PostMapping` |
| `@PUT` | `@PutMapping` |
| `@DELETE` | `@DeleteMapping` |
| `@PATCH` | `@PatchMapping` |
| `@HEAD` / `@OPTIONS` | `@RequestMapping(method = …)` |

#### 3.2 Routing / params (Table 3.2) — ADOPT FULL TABLE INTO MAPPINGS

| Quarkus | Spring | Location |
|---|---|---|
| `@Path` | `@RequestMapping` / path on method annos | class & method |
| `@Produces` / `@Consumes` | `produces` / `consumes` attributes | class & method |
| `@PathParam` | `@PathVariable` | param |
| `@QueryParam` | `@RequestParam` | param |
| `@FormParam` | `@RequestParam` (form) | param |
| `@HeaderParam` | `@RequestHeader` | param |
| `@CookieParam` | `@CookieValue` | param |
| `@MatrixParam` | `@MatrixVariable` | param |
| body: bare parameter | `@RequestBody` | param |
| `@Context` | (Spring injects types without anno) | param |

**Harness:** Extended Spring catalog already has the common rows; **import
the full table** (cookie/matrix/form/context) for completeness.

#### 3.3 Return types (Table 3.3) — ADOPT SELECTIVELY

| Quarkus | Spring | Use in harness |
|---|---|---|
| `Response` | `ResponseEntity<>` / `HttpEntity<>` | ADOPT — OpenRewrite has this too |
| `void` → 204 | `@ResponseStatus(NO_CONTENT)` | ADOPT note |
| entity object → JSON | same | ALREADY |
| `Uni<>` / `Multi<>` | `Mono<>` / `Flux<>` | DEFER unless reactive story |
| SSE `Multi<>` | `SseEmitter` / `Flux<ServerSentEvent>` | DEFER |

#### 3.4 Exception handling — STRENGTHEN REST SKILL + `mapErrors`

Book:

- Local: `@ServerExceptionMapper` on resource (vs Spring `@ExceptionHandler`)
- Global: mapper in its own class (vs `@RestControllerAdvice`)
- Build-time binding in Quarkus vs runtime in Spring
- Native: `@RegisterForReflection` on custom error DTOs (when native)

**Harness:** `quarkus-rest-conventions` already mandates
`@ServerExceptionMapper` + problem+json. **Borrow:**

- Explicit Spring `@RestControllerAdvice` / `@ExceptionHandler` →
  `@ServerExceptionMapper` (global class) in MAPPINGS
- Tie to `targetContract.mapErrors` (503/ExceptionMapper)
- Note reflection registration only if native profile is in scope

#### 3.5 OpenAPI — LIGHT ADOPT

Book covers OpenAPI docs for JAX-RS resources. Our REST skill already
asks for OpenAPI-visible descriptions. Optional: cite SmallRye OpenAPI
extension when a story exposes public APIs.

#### 3.6 Resource class structure — ALREADY ALIGNED

`@Path` on class, method verb annotations, CDI injection of services —
matches `*Resource` conventions. Book examples use field/ctor injection;
**keep constructor-only**.

---

### Chapter 4 — Persistence

#### 4.1 Panache patterns — ADAPT (don't blindly prefer active record)

Book shows:

1. **Panache repository:** `@ApplicationScoped` class implementing
   `PanacheRepository` / `PanacheRepositoryBase`
2. **Panache active record:** entity extends `PanacheEntity` /
   `PanacheEntityBase` with static finders on the entity

Also Spring Data JPA `JpaRepository` ↔ Panache repository method style
(`find("name", name).firstResult()`).

**Harness policy (keep):**

- Flyway owns schema; `quarkus.hibernate-orm.database.generation=validate`
- Constructor-inject `EntityManager` **or** Panache **repository**
- Prefer **repository over active record** for service separation (same
  conclusion as Main Thread notes)
- Explicit `@GeneratedValue` + sequences per persistence skill (book
  examples are looser)

**Borrow into MAPPINGS:** side-by-side Spring Data vs Panache repository
snippet; state active record as allowed but not default.

#### 4.2 `@Transactional` — ADOPT CLARITY

Book: Spring and Quarkus `@Transactional` share the name; use on
mutating service methods. Our persistence skill already requires this —
cite book as confirmation; ensure MAPPINGS maps
`org.springframework.transaction.annotation.Transactional` →
`jakarta.transaction.Transactional` (package change).

#### 4.3 Reactive Panache / R2DBC — DEFER

Chapter half covers Hibernate Reactive + Panache Reactive vs Spring Data
R2DBC. Out of cart / default scaffold scope. Catalog-only for BYO reactive
apps.

#### 4.4 Flyway — HARNESS FILLS THE BOOK'S GAP

Book: Flyway/Liquibase “not discussed… although they can be used.”
**Do not weaken** our Flyway + validate contract because the bible omits
it — treat that as a 2021 scope cut, not a permission to use
`drop-and-create`.

---

### Chapter 5 — Event-Driven Services

| Pattern | Quarkus (book) | Spring | Harness |
|---|---|---|---|
| In-process async | Vert.x `@ConsumeEvent` / event bus | Spring Integration `@ServiceActivator` | ADAPT — MAPPINGS already prefers **CDI `Event`/`@Observes`** for in-process; Vert.x bus is an alternate |
| Kafka / streams | SmallRye `@Incoming` / `@Outgoing`, `mp.messaging.*` | Spring Cloud Stream | DEFER — BYO |
| Knative eventing | Sink/source bindings | — | DEFER |

**Borrow:** When messaging is truly out-of-process, MAPPINGS row for
`@Incoming`/`@Outgoing` + `mp.messaging.*` vs Spring Cloud Stream
(aligns with OpenRewrite Kafka recipes). Keep CDI events as default for
in-app pub/sub.

---

### Chapter 6 — Building Applications for the Cloud

Much of this is **platform/factory** territory our stage already owns
(Tekton, Sonar, Deploy, Routes). Extract only what agents must encode
in app code/config.

#### 6.1 Health — ALREADY + MAPPINGS ROW

- Quarkus: SmallRye Health / MicroProfile `HealthCheck` +
  `@Liveness` / `@Readiness`
- Spring: Actuator `HealthIndicator`

**Harness:** scaffold has `quarkus-smallrye-health`; MAPPINGS maps
actuator → health. **Borrow:** custom `HealthCheck` vs `HealthIndicator`
snippet for REDESIGN health stories; probes must stay on `/q/health`
(acceptance already assumes this).

#### 6.2 Configuration in cluster — STRENGTHEN `preserve:`

Book: env vars, ConfigMaps/Secrets, optional Spring Cloud Config.

**Borrow:** reinforce that env-driven config (`${VAR:default}`,
`quarkus.rest-client.*.url`) is the cloud-native pattern — already our
`preserve:` / demo-env-integration rules. Spring Cloud Config client →
DEFER (OpenRewrite has a recipe; not cart).

#### 6.3 Metrics / tracing — LIGHT ADOPT

Book covers metrics and distributed tracing. Scaffold already pulls
Micrometer Prometheus. MAPPINGS has metrics Windup joins. No major gap;
optional OpenTelemetry note for BYO.

#### 6.4 Container / K8s manifests — PLATFORM, NOT AGENT

JIB, `quarkus-kubernetes` / `quarkus-openshift`, Service Binding — useful
ops knowledge; factory/GitOps own image+deploy. **Do not** have workers
hand-author competing manifests unless a story explicitly owns `k8s/`.

#### 6.5 Remote dev/debug — OUT OF AUTONOMOUS LOOP

Dev Spaces covers remote coding. Skip for harness enrichment.

---

## 3. Master borrow list (priority order)

Implement these into harness guides when enriching (not all at once).

### P0 — put into `MAPPINGS.md` now-candidate

1. Full REST annotation table (Table 3.2) + HTTP verbs (Table 3.1) with
   modern `quarkus-rest` naming note  
2. `@ExceptionHandler` / `@RestControllerAdvice` → `@ServerExceptionMapper`  
3. `ResponseEntity` → JAX-RS `Response`; `void` → 204  
4. DI: prefer `@ApplicationScoped` over `@Singleton` (+ scope table)  
5. Extensions ↔ starters table (modernized artifact IDs)  
6. Spring Data JPA repository → Panache **repository** (not active record default)  
7. `@Transactional` package move (Spring → Jakarta)  
8. Explicit REJECT box for Table 2.3 Spring API extensions  
9. Config profiles: `%profile.key`, `QUARKUS_PROFILE` vs Spring file-based profiles  

### P1 — OpenCode skills

| Skill | Borrow |
|---|---|
| `quarkus-rest-conventions.md` | Advice/global mapper pattern; void=204; cite book tables |
| `quarkus-persistence-conventions.md` | PanacheRepository example vs Spring Data; restate Flyway gap in book |
| `project-test-standards.md` | Shared `@QuarkusTest` app lifecycle vs Spring BootTest restarts |
| `AGENTS.md` | `@ApplicationScoped` default; no `quarkus-spring-*` |

### P2 — process / BYO only

- Kafka `@Incoming`/`@Outgoing` catalog rows  
- Custom HealthCheck examples  
- Reactive Panache / SSE / Knative — only if a legacy app needs them  
- Cheat sheet URL in MAPPINGS references  

### Do not import from this book

| Topic | Reason |
|---|---|
| Destination use of `quarkus-spring-*` | Book itself de-focuses them; harness rejects |
| RESTEasy Classic as target stack | Scaffold is `quarkus-rest` |
| Omitting Flyway / using schema auto-gen | Our factory contract |
| Field injection as equally fine | Sonar + skills |
| Hand-rolled K8s/JIB in worker tasks | Factory/GitOps |
| 2021 API names without modernization | Breaks on 3.27 |

---

## 4. Coverage vs harness today

| Area | Book | Harness today | Gap |
|---|---|---|---|
| Native vs compat | Native focus | Native policy | Document REJECT for compat when MTA suggests it |
| REST maps | Excellent tables | Partial in MAPPINGS + REST skill | Import full tables |
| Exception mapping | Strong | Strong (problem+json) | Add Spring advice → mapper join |
| Config / profiles | Strong | Partial | Profiles + ConfigMapping depth |
| DI scopes | Strong | `@ApplicationScoped` only | Singleton warning + scope table |
| Persistence | Panache-centric; no Flyway chapter | Flyway + validate (+ optional Panache) | Keep Flyway; add PanacheRepository examples |
| Events | Vert.x + Kafka + Knative | CDI events default | Clarify when to escalate to Reactive Messaging |
| Cloud/health | Strong | Health dep + factory | Small HealthCheck mapping |
| Autonomous process | Absent | M1–M5 harness | Book does not replace process |

---

## 5. Suggested enrichment sequence (proposed — not authorized)

See the umbrella review for the gated backlog. When (and only when)
implementation is approved:

1. **MAPPINGS.md** — P0 tables + REJECT Spring extensions + profile syntax +
   transactional package + PanacheRepository preference.  
2. **quarkus-rest-conventions.md** — global `@ServerExceptionMapper` vs
   `@RestControllerAdvice`; void→204.  
3. **quarkus-persistence-conventions.md** — Spring Data ↔ PanacheRepository
   example; “book omits Flyway — we do not.”  
4. **project-test-standards.md** — `@QuarkusTest` lifecycle note.  
5. **AGENTS.md** — one-liner: `@ApplicationScoped` default; never add
   `quarkus-spring-*`.  
6. Optionally link cheat sheet + this doc from MAPPINGS References.

Stop there before pulling Ch5/Ch6 depth unless a DB/messaging BYO app
needs it.

---

## 6. Related harness paths

| Path | Role |
|---|---|
| `.hermes/skills/migration-harness/MAPPINGS.md` | Primary enrichment target |
| `.opencode/skills/quarkus-rest-conventions.md` | REST / errors |
| `.opencode/skills/quarkus-persistence-conventions.md` | Persistence |
| `.opencode/skills/project-test-standards.md` | Tests |
| `AGENTS.md` | Always-on defaults |
| `migration.yaml` `targetContract` | Gates which REDESIGN shapes apply |

---

## 7. One-line verdict

The book is the right **native pattern bible** for our harness: use its
Spring↔Quarkus tables (modernized to Quarkus 3.27 / `quarkus-rest`) to
enrich MAPPINGS and skills; keep our process, Flyway, constructor
injection, RH BOM, and Spring-compat rejection as harness laws the book
never overrides.

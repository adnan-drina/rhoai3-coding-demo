# Process fix — production-grade on the first pass (review draft)

**Status:** proposal for review. Nothing here is applied to the harness yet.
**Origin:** V4 shipped a faithful legacy migration, not a production-grade
service — 5 of 6 S03 defect classes recurred ([V4-RUN-LOG.md §6](V4-RUN-LOG.md)).
The earlier "append an S03 hardening story" idea is withdrawn: the run's
own logs prove fidelity never constrained the services/endpoints (it only
ever flagged the `ShoppingCart` model), so there is nothing to work around
— the defects came from the plan and tests being authored to reproduce
legacy behavior. This draft fixes that at the source.

## 1. The two distinctions the process is missing

**A. Class role — HARVEST vs REDESIGN.**
- **Harvest** classes are data/logic carried over substantially unchanged:
  models, DTOs, value objects, pure utilities. A `Product` stays a
  `Product`. Fidelity applies; characterization tests pin legacy values.
- **Redesign** classes own runtime behavior: services (`@ApplicationScoped`),
  endpoints (`@Path`), REST clients, config. These are *modernized*, not
  copied. Harvest-fidelity already exempts them (the discriminator skips
  `@ApplicationScoped/@Inject/@Path/@RegisterRestClient`), so the class-role
  split is not a new mechanism — it makes explicit a boundary the fidelity
  sensor already draws.

**B. Improvement kind — behavior-PRESERVING vs behavior-CHANGING.**
- **Behavior-preserving** (same observable result, better implementation):
  thread-safe collections, cache-refresh policy, resource/error-path
  handling. Characterization tests still pass. **Default ON for redesign
  classes** — no decision needed, enforced by a wiring check.
- **Behavior-changing** (different observable contract): GET→404 instead of
  create-on-GET, reject invalid input→400, map failures→503. These need an
  **explicit target-contract decision at M1**, and the characterization
  tests are written to the *target*, never to the legacy.

The current process has one default — "preserve legacy behavior faithfully"
— applied to everything. That single default is the bug.

## 2. Concrete changes, per file

### 2.1 ANALYSIS.md (M1) — emit class roles + target contract

Add a profile section (the profile already has 6; this is the 7th, rubric
should require it for any app with `@ApplicationScoped`/`@Path` classes):

> **§7 Class roles & target contract.** Classify every source class as
> HARVEST (data/DTO/utility — carried faithfully) or REDESIGN (service,
> endpoint, REST client, config — modernized). For each REDESIGN class,
> state the target runtime contract, decided from the class's role and the
> platform's idioms (cite MAPPINGS "Production-grade defaults"):
> - **Concurrency:** is the bean a shared singleton with mutable state? →
>   target the thread-safe shape (`ConcurrentHashMap`, `compute()`).
> - **Resource/cache policy:** does it cache or hold external results? →
>   target the refresh/eviction policy (no clear-on-miss; bounded refresh).
> - **API contract (behavior-CHANGING — decide explicitly):** does a read
>   verb mutate state? does it validate inputs? how do downstream failures
>   surface? → decide GET-idempotency, input-validation, and error-mapping
>   as TARGET behavior, and flag each as a deliberate departure from legacy.
> Evidence-or-silence still binds: cite the legacy lines that motivate each
> decision; do not invent contracts the code does not imply.

Rubric gains one check: if any class is `@ApplicationScoped`/`@Path`, §7
must be present and must name a concurrency and an API-contract decision.

### 2.2 SEQUENCING.md (M2) — replace the "Production-grade bar" prose

**Remove** the current "Production-grade bar" paragraph (it asks the deploy
story to bake in hardening as if it were a checklist and does not tell the
planner how). **Replace** with:

> **Class roles drive the brief, not the story split.** A story may contain
> both harvest and redesign classes. What matters is that the brief carries,
> for every REDESIGN class in scope, the target contract from
> architecture-profile §7 as DECIDED design — the concrete shapes
> (`ConcurrentHashMap`+`compute()`, refresh-guarded cache, GET→404,
> validation→400, `ExceptionMapper`→503), with the behavior-changing ones
> marked as deliberate departures from legacy. There is no separate
> hardening story and no "harden later": the story that converts a redesign
> class converts it to its target.

### 2.3 PLANNING.md (M3) — tests to target for redesign classes

Add to the ordering/test-placement rules:

> **Characterization tests pin the TARGET for redesign classes, the LEGACY
> for harvest classes.** A harvest class's tests assert legacy values
> (fidelity). A redesign class's tests assert its architecture-profile §7
> target contract; where the target deliberately differs from legacy
> (GET→404, invalid→400), the test task cites the profile decision in one
> line ("GET returns 404 on missing cart — target contract, profile §7; not
> legacy create-on-GET"). Never write a test that pins a behavior the target
> contract removes — that test would have to be rewritten, which is the
> write-then-rewrite waste this process eliminates.

The infer-task design for a redesign class must state the target shape
(already required by plan-lint's Class-substance check); MAPPINGS
"Production-grade defaults" is the source of the shapes.

### 2.4 EXECUTION.md (M4) — build to target, not to legacy

Add under Phase C:

> **Redesign classes are built to their target contract from the first
> commit.** The plan states the target (thread-safe state, idempotent reads,
> validated inputs, mapped errors); implement it directly — this is not
> "harden later," it is the conversion. The behavior-preserving shapes
> (thread-safety, cache policy, error mapping) are non-negotiable defaults;
> the behavior-changing ones are exactly what the plan/brief decided.

### 2.5 sensors.sh — a wiring check for behavior-preserving quality

The behavior-preserving defaults can be enforced deterministically at the
**task** sensor (cheap, every commit), so they never depend on model
diligence. Add to `wiring_invariants` (heuristic, with a false-positive
guard):

> **Shared-mutable-state check.** A class annotated `@ApplicationScoped` or
> `@Singleton` that declares a non-`final` `Map`/`List`/`Set` field
> initialized with a non-concurrent impl (`new HashMap`/`ArrayList`/`HashSet`)
> AND mutated (`.put`/`.add`/`.remove`) outside a constructor or
> `@PostConstruct` method → RED: "shared mutable state on a CDI singleton;
> use a concurrent collection or confine mutation to init." The
> constructor/@PostConstruct carve-out avoids flagging populate-once-then-
> read caches (effectively immutable). This is the same class as V4 finding
> #1 and S03 T-001; making it a task-sensor invariant closes it in-loop for
> every future run.

(Behavior-changing contract — GET idempotency, validation, error mapping —
is NOT sensor-enforceable without over-fitting; it is enforced by the plan
tasks + target-written tests from §2.3.)

## 3. What this deliberately does NOT change

- **Harvest-fidelity stays exactly as is.** It correctly guards faithful
  harvests of harvest-class code (models/utilities). The class-role split
  aligns with its existing discriminator; no fidelity code changes. (The
  separate #5 normalizer false-positive fix — strip inner-punctuation
  spacing — is unrelated and still stands.)
- **The fabrication default stays in-migration.** It already survives via
  the `forbidden:` tripwires, independent of everything here.
- **No hardening story, no FIDELITY_CHECK=off dance.** Withdrawn.
- **`FIDELITY_CHECK=off` / hardening-story machinery** remains available for
  genuine POST-SHIP findings discovered by a later semantic review (its
  original S03 purpose), but is no longer the path for KNOWN defect classes.

## 4. Why this is written-once, not write-then-rewrite

The waste in the append-a-story model was: convert faithfully → tests pin
legacy → separate story rewrites code AND tests to target. Here the target
is decided at M1, the plan tasks target it, and the tests are written to it
once. The redesign classes were never fidelity-constrained, so there is no
gate to fight. Cost moves from a second story (hours of task+sensor cycles)
to a few sentences in the profile and brief.

## 5. Rollout / validation before trusting it

1. Land after the Phase→M rename settles (this touches ANALYSIS/SEQUENCING/
   PLANNING/EXECUTION/sensors — all in the rename's blast radius).
2. Unit-test the new wiring check in `tests/instruments.sh`: a fixture
   `@ApplicationScoped` class with `new HashMap` mutated in a normal method
   → red; the same with `ConcurrentHashMap` → green; the same with mutation
   only in `@PostConstruct` → green (false-positive guard).
3. Dry-run M1 on the cart legacy: confirm §7 classifies the 4 models as
   harvest and the 5 services/endpoint as redesign, and names the
   concurrency + API-contract decisions.
4. Only then a full run; the acceptance is a shipped service that passes the
   §6 semantic review with zero recurring defect classes — no hardening
   pass.

## 6. Open questions for you

- **Behavior-changing contract scope:** do we want GET→404 and input
  validation as standing defaults for cart-class REST services, or decided
  per-app at M1? (Draft assumes per-app M1 decision, which is safer for
  migrations with external API consumers that depend on legacy quirks.)
- **Wiring-check strictness:** RED (blocks the commit) vs WARN (logged,
  surfaces in retro)? Draft says RED for the concurrency check because it is
  a clear correctness issue with a low false-positive rate given the
  init-carve-out; open to WARN if you want a gentler rollout.

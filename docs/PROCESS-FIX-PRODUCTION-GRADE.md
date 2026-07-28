# Process fix — production-grade on the first pass (review draft)

**Status:** proposal for review (revised once, incorporating a second AI
agent's review — additions marked "added after review"). Nothing applied to
the harness yet.
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

Rubric gains two checks in `profile-rubric.py`: (1) if any class is
`@ApplicationScoped`/`@Path`, §7 must be present and must name a concurrency
and an API-contract decision; (2) **deterministic classification cross-check
(added after review)** — every class the source tree marks
`@ApplicationScoped`/`@Singleton`/`@Path`/`@RegisterRestClient` MUST be
classified REDESIGN in §7. This is mechanically verifiable (same signal the
fidelity discriminator uses), so the class-role split is not left to model
judgment — a service mislabeled "harvest" (which would re-pin it faithful,
reintroducing the whole bug) is caught by the rubric.

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

### 2.3b SEQUENCING.md — narrow the "hardening stories" section (added after review)

The existing "Story classes" / hardening-story prose says fidelity
*preserved* the defect classes and a later story hardens them. Under the new
model that is wrong for KNOWN defect classes (they are targeted in-migration).
**Narrow it** to: hardening stories exist ONLY for defects DISCOVERED
post-ship by a semantic review that M1 could not anticipate — not for the
known concurrency/idempotency/validation classes, which are now redesign-
class targets. `FIDELITY_CHECK=off` + the S03 template stay available for
that narrowed purpose.

### 2.3c MAPPINGS.md — align the assertions wording (added after review)

The "Production-grade defaults" section currently says "existing contract
assertions stay green; only assertions that pin a defect class may change" —
which assumes the harden-later model. Replace with: "**Redesign-class tests
pin the architecture-profile §7 target; harvest-class tests pin legacy
values.** A redesign test never pins a behavior the target contract removes."

### 2.4 EXECUTION.md (M4) — build to target, not to legacy

Add under the M4 (task-execution) phase:

> **Redesign classes are built to their target contract from the first
> commit.** The plan states the target (thread-safe state, idempotent reads,
> validated inputs, mapped errors); implement it directly — this is not
> "harden later," it is the conversion. The behavior-preserving shapes
> (thread-safety, cache policy, error mapping) are non-negotiable defaults;
> the behavior-changing ones are exactly what the plan/brief decided.

### 2.4b Enforcement matrix — what catches each defect class (added after review)

Not everything can be a code sensor; forcing one over-fits. Each behavior-
preserving default is enforced at the CHEAPEST layer that can catch it
without false positives:

| Defect class | Enforcement | Why not a code sensor |
|---|---|---|
| #1 shared mutable state on singleton | **task-sensor wiring check** (§2.5) | clean structural pattern, low FP with init carve-out |
| #2 cache clear/refetch-on-miss | **plan-lint §7-traceability + target test** | "is the cache refresh-guarded" is semantic ordering; a pattern check would over-fit this app |
| #5 dedupe-before-pricing | **plan-lint §7-traceability + target test** | same — call-order semantics, not a matchable pattern |
| #3 GET idempotency, #4 validation/error-map | **profile §7 decision + target test** | behavior-changing; decided, not defaulted |

**plan-lint §7-traceability check (generic, not app-specific):** for each
REDESIGN class in scope, the plan's infer task for it must reference that
class's architecture-profile §7 decisions. This is a coverage/traceability
check (does the plan carry what the profile decided), NOT a code-pattern
match — so it stays generic across apps. It closes the "soft guidance loses"
failure for #2/#5 without a fragile sensor.

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

### 2.6 Touchpoints checklist (added after review — the full blast radius)

The change spans more files than §2.1–2.5 named. Complete list:
- `ANALYSIS.md` — §7 (2.1)
- `SEQUENCING.md` — replace Production-grade bar (2.2) AND narrow hardening
  stories (2.3b)
- `PLANNING.md` — tests-to-target (2.3)
- `BRIEF-TEMPLATE.md` — a "target contract (redesign classes)" field so the
  brief carries §7 forward to M3
- `EXECUTION.md` — build-to-target (2.4)
- `MAPPINGS.md` — assertions wording (2.3c)
- `sensors.sh` — shared-mutable-state wiring check (2.5)
- `plan-lint.py` — §7-traceability check (2.4b)
- `profile-rubric.py` — §7 presence + deterministic classification check (2.1)
- `outer-loop.sh` — the M2 prompt string still says "Production-grade bar";
  update it to the SEQUENCING rewrite (2.2)
- `tests/instruments.sh` — cover the wiring check + the §7-traceability check
- `migration.yaml` / RHDH template — the demo "target contract" stamp (see §6)

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
4. Only then a full run.

**Accept criteria (sharpened after review) — ship the process change when ALL hold:**
- M1 §7 dry-run on the cart legacy classifies the 4 models as harvest and the
  5 services/endpoint as redesign, AND names the concurrency + API-contract
  decisions; the rubric's deterministic cross-check passes.
- `tests/instruments.sh` covers the wiring check (HashMap-mutated → red;
  ConcurrentHashMap → green; mutation only in `@PostConstruct` → green) and
  the §7-traceability check.
- A full run's **semantic code review** (not gates-green — the gates are
  green WITH the defects; a human/AI must read the service) finds **0 of the
  5 behavioral S03 classes recurring** (the 6th, fabrication, is already
  independently clean), with NO hardening story in the roadmap.

Note the accept gate's cost: validating "0/5" requires a full ~7h run plus a
manual semantic review. Budget for one validation cycle before trusting the
change on real migrations.

## 6. Decisions (open questions — resolved after review, pending your final word)

- **Behavior-changing contract scope → PER-APP at M1.** Standing defaults for
  all REST migrations are unsafe (external consumers may depend on legacy
  quirks). **For the cart DEMO specifically:** stamp the decided target
  (GET→404, quantity→400, `ExceptionMapper`→503) into `migration.yaml` (a
  `target-contract:` block) or the RHDH template, so M1 reads the decided
  target instead of a model re-deciding to keep create-on-GET. This is just a
  pre-filled §7 for the demo — same mechanism, pinned value.
- **Wiring-check strictness → RED**, with the init carve-out. Start WARN only
  if the first dry-run shows false-positive noise.

## 6b. Safety gradient (added after review — the guardrail)

- **Behavior-preserving defaults are always-on** (thread-safety, cache,
  error-path) — zero observable-behavior change, zero consumer risk.
- **Behavior-changing contract is conservative and consumer-weighed** —
  adopted only when profile §7 explicitly decides it, never as a silent
  default. A migration must not surprise external callers; when in doubt, the
  faithful contract stays and the change is flagged for a product decision.

# M2 SEQUENCE — the modernization roadmap and its briefs

You are turning the M1 outputs into an ordered, incremental
modernization plan: `migration/roadmap.md` plus one brief per story
under `migration/briefs/`. NO BIG BANG: each story is an increment that
leaves the repository buildable, sensor-green, and closer to done.

## Inputs (read all four before writing anything)

- `migration/architecture-profile.md` — what the app is; domain
  boundaries; contract sources
- `migration/dependency-order.md` — the conversion order the stories
  must respect (dependencies before dependents; circular groups stay
  together)
- `migration/findings-inventory.md` — every mandatory finding with its
  class; recipe-executed rules are ALREADY DONE (`migration/
  recipe-log.md`) — no story owns them. Non-mandatory rules appear in a
  decision table — mark each under `## Non-mandatory decisions` as
  `adopt` or `defer (reason)` (K3); roadmap-lint enforces the marks.
- `migration.yaml` — preserve/forbidden/acceptance contracts

## How to cut stories

1. **Follow the graph, not the file tree.** Story order = dependency
   order: models/utilities before services before surfaces. A story
   never modernizes a class whose project-internal dependencies are
   owned by a LATER story. Circular groups belong to one story.
   Within a story, prefer **extensions → models → resources → config →
   tests** (BOM/deps first, HTTP surface after its dependencies, tests last).
2. **Contracts and characterization tests come first.** The first
   story that touches a component with a behavioral contract
   (architecture-profile §4) pins that contract — port the legacy
   tests / add characterization tests for the flagged gaps — before or
   within the story that changes the code.
3. **Domain seams for monolith-class apps** (profile §6): one story
   per bounded context, contexts ordered by their coupling direction;
   in-place modularization (no service extraction — that is a
   follow-up outside this migration).
4. **Natural sizing, no floor or ceiling by count**: a story is one
   spec-kit cycle a session can hold (≈ the packet-size spirit: a
   story's in-scope class list should fit ~10 files). A trivial app
   may be one story; do not pad.
5. **Deploy milestones**: mark `deploy: true` on stories whose end
   state is worth proving live (at minimum the LAST story; typically
   also the first story that leaves the app serving its API). Others
   stop at the factory quality gate.
6. **Every story changes code or tests.** No ceremonial stories
   (validation-only, commit-only, report-only) — the harness gates do
   the validating.
7. **Package rename is per-path harvest, not one mega-task (S-RN).**
   Do **not** put “rename the entire package tree” in S01 as a single
   rewrite/infer. M1 already wrote `migration/staging/`; each HARVEST
   file becomes its own rewrite task that runs
   `harvest-from-staging.sh <rel-path>` (or an already-complete skip
   when the target file exists). Platform/POM stories stay POM-only —
   leave model/service/REST classes in staging until their owning story
   (S-LC).
8. **`findings: -` is HARVEST-only (S-FND).** Blank findings are
   rejected. Use `-` only for pure model/characterization stories;
   redesign/POM/REST stories must list rule ids.
9. **Model-harvest stories do not pull service tests forward.** A
   story whose scope is `src/main/.../model/**` (or equivalent) must
   not list tasks that require unowned redesign SUTs
   (`*ServiceTest` needing `ShoppingCartService` in `src/main`). Port
   those tests in the service story; use model-level tests or
   test-local doubles only if characterization is required early
   (PLANNING.md). V8 S02 false-green abort.

## One quality model — build redesign classes to their target

There is ONE quality model, not "migrate faithfully then harden later."
Each story carries, from `architecture-profile.md §7`, the class roles and
the target contract:

- **HARVEST classes** (models, DTOs, value objects, pure utilities) are
  carried over faithfully — harvest-fidelity applies, characterization
  tests pin legacy values. A `Product` stays a `Product`.
- **REDESIGN classes** (services, endpoints, REST clients, config) are
  MODERNIZED to their §7 target: thread-safe singleton state, cache
  refresh-guard, read-only GET, validation + error mapping,
  normalize-before-derive (the MAPPINGS "Production-grade defaults"
  shapes). Harvest-fidelity already exempts these (its discriminator skips
  `@ApplicationScoped/@Inject/@Path/@RegisterRestClient`), so building them
  to target never fights a fidelity gate. The story that converts a
  redesign class converts it to its target — there is no separate hardening
  story and no "harden later."

The brief for a story containing redesign classes names their §7 target
shapes as DECIDED design, marking any behavior-CHANGING contract (e.g.
GET→404, invalid input→400) as a deliberate departure from legacy.
plan-lint enforces that each redesign class's task cites its §7 decisions.

**Behavioral oracles:** service stories pin service-level assertions; endpoint
stories pin JAX-RS/RestAssured coverage. Cart `add()` is **additive** — two
`add(cartId, itemId, 2)` → quantity **4** after dedupe. Allowlist
`*ExceptionMapper` / `@IfExists` in `STORY_SCOPE` when the contract needs
them before the owning story.

A defect DISCOVERED after shipping (by a later semantic review or in
production) that M1 did not anticipate re-enters as a normal finding
through the standard loop — it is not a special story class to remember.

## roadmap.md format (machine-parsed — roadmap-lint enforces this)

```markdown
# Modernization roadmap

## S01: <short title>
- scope: <comma-separated TARGET file paths (src/main/java/...) where known; class names only for not-yet-mapped legacy classes — the story-scope sensor enforces path entries only>
- findings: <comma-separated mandatory rule ids this story resolves>
- depends: - | S<NN>[, S<NN>...]
- deploy: true|false
- done: <one-sentence checkable done-criterion>
- rationale: <why this story, why now — cite dependency-order/profile>

## S02: ...
```

Every mandatory finding id from the inventory (except recipe-executed
ones) appears in exactly one story's `findings:`. Every `preserve:`
item is owned by the story whose scope carries its surface (name it in
that brief).

## Briefs (`migration/briefs/S<NN>-<slug>.md`)

One per story, following `BRIEF-TEMPLATE.md` in this directory. The
bar: **a competent developer (or a fresh session) could start the
story from the brief alone** — without re-reading the whole profile.
That means: real code excerpts from the legacy source (the actual
lines being modernized, quoted), the decided MAPPINGS shapes named,
the contract values spelled out (assertion numbers, env var names),
and the done-criteria concrete.

**Quote, never invent.** Every method and annotation you put in an `In
scope` code excerpt is a claim that the LEGACY class has it — open the
real file under `/projects/legacy` and copy what is actually there. Do
NOT write the signature you imagine, the annotation you assume (a POJO
is not `@Entity`; a JAX-RS `@Path` endpoint is not `@GetMapping`), or a
method name that reads well (`createShoppingCart`) when the legacy has a
different one (`getShoppingCart`). The target shape belongs in `Decided
target shapes`, not disguised as a legacy quote. The lint cross-checks
every quoted method/annotation against `/projects/legacy` and rejects any
that is absent (`LINT:fabrication`) — a fabricated brief becomes a
fabricated plan the tests then pin, which no later gate can unwind.

## Output contract

Verify yourself before committing:
`python3 .hermes/harness/roadmap-lint.py migration/roadmap.md migration/findings-inventory.md /projects/legacy`
must exit 0 (the trailing legacy dir enables the fabrication cross-check).
Commit everything in ONE commit, prefix `M2 sequence:`.

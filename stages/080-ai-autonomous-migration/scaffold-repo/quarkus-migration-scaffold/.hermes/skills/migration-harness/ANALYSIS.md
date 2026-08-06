# M1 ANALYZE — the architecture profile

You are writing `migration/architecture-profile.md`: the record of what
the legacy application IS and was BUILT TO DO. Everything downstream —
the roadmap, the briefs, the specs — leans on this document; the
migration must stay as close as possible to the original intent, and
this file is where that intent is captured.

## Ground rules

1. **Evidence or silence.** Every claim cites its source inline:
   `(src/main/java/...:LINE)`, a finding rule id, or a test name.
   No citation → do not write the claim. The rubric
   (`.hermes/harness/profile-rubric.py`) rejects uncited sections.
2. **Read the inputs first — do not re-derive them.** The deterministic
   artifacts already exist; your job is interpretation, not extraction:
   - `migration/model.json` + `migration/profile-decisions.json` (ADR-26/29) —
     authoritative class universe and **typed decision SoT**
     (`model.units[].decision`). Before your seat the harness opens
     `profile-decisions.json` with `role=null` for every unit. You fill
     §§1–6 in the profile **and** persist typed decisions via
     `profile_roles.py upsert` (O-DECISIONWRITEDROP — one unit per call;
     do not rewrite the decisions JSON wholesale). The closer **applies**
     / refreshes the model and **renders** §7 — never harvest role from
     markdown. Coverage = typed decisions whose evidence resolves at the
     cited line. Source `*Mapper.java` interfaces **are** classify;
     `*MapperImpl` / `generated-sources` are build-owned — never decide them
     (O-RUBRICGENASSERT).
   - `migration/mta-findings.json` / `migration/findings-inventory.md`
     — what must change, already classified against MAPPINGS
   - `migration/dependency-order.md` — the import graph: fan-in/out,
     god nodes, conversion order, circular groups (a view of the model)
   - the legacy source under `/projects/legacy` (read-only)
   - the legacy test suite — the behavioral contract lives here
3. **Intent over mechanism.** "PromoService applies a −10.99 shipping
   promotion above a cart threshold (ShoppingCartServiceTest:LINE)"
   captures intent; "PromoService has a method promoteShipping" does
   not.
4. **This is not the plan.** Record what is and what must change —
   never task breakdowns, sequencing, or target designs (M2/M3 own
   those).

## Required sections (rubric-checked)

### 1. Purpose & domain
What the application does, for whom; the core domain concepts (entities
and their meaning, not just class names). 1–2 paragraphs.

### 2. Components & relationships
The components (endpoint/service/model/config groups) and how they
relate — interpret `dependency-order.md` into an architecture
statement: which classes form which component, who depends on whom,
which are the god nodes and what that means for risk. A small ASCII
diagram is welcome; every edge it shows must exist in the import graph.
Cite `dependency-order.md:LINE` and/or at least one `src/main/java/...`
path — bare prose with no citation fails the rubric (O-PROFITECITEMIG).

### 3. Integration surfaces
Every boundary to the outside world: consumed services (with their
configuration mechanism — env vars, properties), exposed APIs (paths,
verbs, payload types), persistence, messaging. Each surface cites the
code AND names the migration.yaml `preserve:` item that covers it — or
flags it as an UNCOVERED preserve candidate.

### 4. Behavioral contract sources
Where the app's expected behavior is pinned: the legacy test classes,
the assertion values that constitute the contract (quote the important
ones — totals, thresholds, formats), and any behavior NOT covered by
tests (flag as contract gaps the specs must close with
characterization tests).

### 5. Modernization surface
Per component: what MUST change (mandatory findings, by rule id), what
SHOULD (optional), what needs examination (potential — including the
platform contract rules: env-driven config, in-memory state, UI
surface). This is a summary keyed to findings-inventory.md, organized
by component instead of by rule.

### 6. Domain boundaries
Candidate seams for incremental modernization: which components form
coherent domains, which are coupled and why (cite the graph edges or
shared state). For a small service this may be one paragraph
("effectively a single bounded context"); for a monolith, name each
candidate bounded context with its classes. State it descriptively —
M2 decides the actual story cuts.

### 7. Class roles & target contract
Classify EVERY unit from the DERIVED FACTS / `model.json` profile-units list
(package-info excluded by the model). **Do not author §7 role bullets** —
persist typed decisions via harness **upsert** (O-DECISIONWRITEDROP).
The harness renders §7 from `model.units[].decision` after close.

**/ O-PROFSEATARCH — harness decide loop (default).** Outer-loop
classifies undecided units via `profile_decide_loop.py` (Qwen/OpenCode
per-unit upsert), not MiniMax N=20 mchat batches. Prose seats fill §§1–6
only; the harness owns the decide happy path. `PROFILE_DECIDE_ENGINE=batch-mchat`
is legacy containment only (does not fix hourly MiniMax quota).

**O-DECISIONWRITEDROP — small writes only.** Do **not** rewrite
`migration/profile-decisions.json` wholesale in one patch (Hermes drops large
tool-calls). Persist **one unit per call** (or ≤3 via `--json-file`):

```bash
python3 .hermes/harness/profile_roles.py upsert --root . --legacy /projects/legacy \
  --fqn 'com.example.Foo' --role HARVEST --rationale 'unit-specific why' \
  --path 'src/…/Foo.java' --line 47 --token '@Entity'
```

The harness updates `model.units[].decision` and refreshes
`profile-decisions.json`. Then run `profile_close.py` + `profile-rubric.py`.

**One typed decision per profile-unit .** Fields:

```json
{
  "legacy_fqn": "…",
  "role": "HARVEST" | "REDESIGN",
  "rationale": "unit-specific why",
  "evidence": { "path": "src/…/X.java", "line": 47, "token": "@Entity" }
}
```

Evidence must **resolve**: `token` occurs on that `path:line` in legacy
(G1 line-level). Grouped bullets, deferral scaffolds, and identical templates
are unrepresentable. PROFILE GREEN = every unit decided with a resolving
anchor. `role=null` means undecided. Coverage reports `authored=` vs
`evidence_miss=` so a filled JSON row that cites the wrong line does **not**
count as credited.

**SELECT projected evidence anchors; do not search.** DERIVED FACTS project a
pre-verified `anchors` list per unit (declaration / annotation / import /
finding lines the harness already verified). Copy `path`+`line`+`token`
from one of those anchors into upsert `--path/--line/--token`. **Do not
invent line numbers.** Upsert/apply refuse evidence outside the projected set
(`F-anchor-membership`). Your job is HARVEST vs REDESIGN +
rationale — not hunting for resolving lines.

**O-PROF1OF79STOP — batch seats.** Outer-loop projects DERIVED FACTS with
`--undecided-only --limit N` (default 20). Fill **only the listed batch** per
seat; do not attempt all profile-units in one prompt. Rate-limit → stop (no
MiniMax a2). Low credited coverage also refuses a2 — fix evidence / continue
batches instead of burning quota.

Classify EVERY source class as one of:
- **HARVEST** — data/DTO/value-object/pure-utility carried over faithfully.
- **REDESIGN** — service, endpoint, REST client, or config that owns
  runtime behavior and is MODERNIZED, not copied.

Every class the source marks `@ApplicationScoped`/`@Singleton`/`@Path`/
`@RegisterRestClient` (or the Spring `@Service`/`@Component`/`@RestController`
equivalents) is REDESIGN — the rubric cross-checks this mechanically, so do
not mislabel a service as harvest. A class the target platform SUBSUMES or
DROPS (e.g. a Jersey/JAX-RS `@Component` config class Quarkus replaces with
auto-discovery, or a Spring boot bootstrap class) is still REDESIGN — give it
the target `removed — <what subsumes it>`. Every annotated class must be
accounted for; "it goes away" is a decision, stated, not an omission.

**Generated build outputs are not class-roles (O-RUBRICGENASSERT).** Do not
assign HARVEST/REDESIGN to `*MapperImpl`, OpenAPI generated types, or any
path under `target/` / `generated-sources`. You may note MapStruct/codegen as
a build concern owned by `build-codegen-*` findings — without a class-role.

Do NOT write "preserve existing behavior" for a REDESIGN class whose contract
CHANGES — state the target and the deliberate departure. "Preserve" language
belongs to HARVEST classes only.

For each REDESIGN class, state the target runtime contract, decided from
its role and the platform's idioms (cite MAPPINGS "Production-grade
defaults"); evidence-or-silence binds — quote the legacy lines that
motivate each decision:
- **Concurrency** — shared singleton with mutable state? → thread-safe
  target (`ConcurrentHashMap`, `compute()`).
- **Resource/cache policy** — caches or holds external results? → refresh/
  eviction policy (no clear-on-miss; bounded refresh).
- **Aggregate/derived math** — computes totals/derived values from a
  collection that is also normalized (deduped, sorted)? → normalize BEFORE
  deriving (e.g. dedupe-before-pricing), so line items and totals agree.
- **API contract (behavior-CHANGING — decide explicitly)** — does a read
  verb mutate state? are inputs validated? how do downstream failures
  surface? State the target in DECISIVE terms (the rubric requires the
  decided token, not abstract "idempotency/validation/error-mapping"):
  - read verb that mutates → "GET returns **404** on missing (never creates)"
  - unvalidated input → "reject with **400** (problem-detail)" / `@Min`/`@Valid`
  - downstream failure → "**503** via a JAX-RS **ExceptionMapper** (never raw 500)"
  Each is a deliberate departure from legacy. Behavior-changing contract is
  conservative and consumer-weighed: adopt it only when the role calls for
  it; when a `migration.yaml` `targetContract:` block is present, it is
  authoritative — for each flag set true, state its decided token in §7
  (`getIdempotent`→404, `validateInput`→400, `mapErrors`→503/ExceptionMapper,
  `threadSafeState`→ConcurrentHashMap, `cacheRefreshGuard`→no-clear-on-miss,
  `normalizeBeforeDerive`→normalize-before-derive). Do not re-litigate it.

## Output contract

Write the file, then verify it yourself:
`python3 .hermes/harness/profile-rubric.py migration/architecture-profile.md`
must exit 0 before you commit. Commit message prefix: `M1 analyze:`.

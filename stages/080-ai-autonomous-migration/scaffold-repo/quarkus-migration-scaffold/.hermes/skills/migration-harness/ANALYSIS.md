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
   - `migration/mta-findings.json` / `migration/findings-inventory.md`
     — what must change, already classified against MAPPINGS
   - `migration/dependency-order.md` — the import graph: fan-in/out,
     god nodes, conversion order, circular groups
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

## Output contract

Write the file, then verify it yourself:
`python3 .hermes/harness/profile-rubric.py migration/architecture-profile.md`
must exit 0 before you commit. Commit message prefix: `M1 analyze:`.

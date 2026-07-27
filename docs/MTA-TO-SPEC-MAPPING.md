# MTA findings → spec-kit input: analysis and mapping

Written 2026-07-27. Analysis only — nothing here is implemented; §6 is a
ranked proposal for discussion. Grounded in: the cart run's real
`mta-findings.json` (konveyor JSON, 20 rules / 35 incidents), our Phase
A/B machinery (`extract_findings.py`, PLANNING.md, `plan-lint.py`), five
runs of evidence, and the MigIQ review.

## 1. The step under analysis

MTA (Windup rule engine) analyzes the legacy app along a **migration
path** (source/target technology pair, e.g. `springboot → quarkus`) and
emits *violations*: per-rule findings with a category
(mandatory/optional/potential), a description, and *incidents* — exact
`file:line` sites with a per-site message. This is the raw material our
Phase B (spec-kit style: `spec.md` / `plan.md` / `tasks.md`) must turn
into a migration specification. The quality of that translation bounds
the quality of everything downstream — a finding that never becomes a
spec statement or a task is a defect we discover at ship time (run #2's
acceptance-path gap was exactly a contract element no artifact carried
into the plan).

## 2. What Windup findings actually contain — and what they cannot

What a finding gives us, per rule:

| Field | Information | Downstream use |
|---|---|---|
| rule id (e.g. `javax-to-jakarta-import-00001`) | stable identity | traceability: plan-lint's mandatory-coverage check, Phase D delta |
| category | mandatory / optional / potential | scope contract: what MUST be in the plan |
| description + incident messages | the *problem class*, often with a hint of the target ("Replace the `javax.annotation` import…") | task titles, packet content |
| incidents (`uri`, `lineNumber`, message) | the *complete site list* | packet grouping, size estimation |
| effort points (when present) | relative cost | task sizing (absent in our current kantra export) |

What findings structurally CANNOT give us — each gap maps to a failure
we have already paid for:

1. **No behavioral contract.** Rules match patterns, not semantics. MTA
   will flag a Feign client's annotations; it will never say "pricing
   must total 2000.0 with a −10.99 shipping promo." The contract lives
   in legacy tests and code reading — this is why assertion tampering
   (run #2, T-027) is invisible to any findings-driven check.
2. **No dependency structure.** Findings are site-local. Nothing in the
   JSON says "convert `ShoppingCart` before `CartEndpoint`" — the
   sequencing red commits of run #2 lived precisely in this gap (now
   partially covered by `dependency-order.md`).
3. **No target design.** "Replace X" is not "here is the decided shape
   of the replacement." That judgment lives in MAPPINGS.md.
4. **Incomplete coverage.** Only what a rule matches is found. The cart
   app's `CATALOG_ENDPOINT` env contract, the acceptance surface, the
   UI question — none have Windup rules. The spec must be authored from
   findings PLUS code reading; findings alone under-specify.
5. **No priority beyond category.** Mandatory-vs-optional is coarse;
   which mandatory item blocks which other work is graph knowledge, not
   rule knowledge.

## 3. Our translation today (honest assessment)

Current chain: `mta-findings.json` → `extract_findings.py` (count
summary + per-rule site listing, keeps the JSON out of model context) →
the Phase B session reads legacy code + the summary → writes
spec/plan/tasks → `plan-lint.py` verifies every **mandatory rule id
appears somewhere in tasks.md** → Phase D re-analysis measures the
findings delta.

Strengths: deterministic traceability floor (lint), closed loop
(delta), context economy (script summarizes; model doesn't ingest raw
JSON). Weaknesses, in evidence:

- **Traceability is string-presence, not semantics.** A task that
  *mentions* `spring-components-00002` passes the lint even if its body
  does nothing about it. Run #2's `RESOLVED-BY-SCAFFOLD` tail (9 tasks
  that no-oped because the pom work was already done) shows plans can
  satisfy the letter cheaply.
- **The findings→design join happens implicitly in the model's head.**
  The session must connect rule → MAPPINGS entry → task class on its
  own each run. When it fails to, we get design-less tasks (revision
  rounds in both cart plans).
- **Preserve/acceptance contracts bypass findings entirely** (they come
  from migration.yaml) — correct, but nothing cross-checks that
  config-related findings (env vars, endpoints, datasources) were
  considered as preserve candidates.
- **Incidents are under-used.** The site lists are the natural packet
  content (≤10 files, grouped by rule), but packets are currently
  authored from the plan text, not generated from incident clusters.

## 4. The mapping (target shape for the translation)

The clean way to think about it: **each spec-kit artifact consumes a
different projection of the findings**, and the projections that are
mechanical should be computed, not re-derived by the model per run.

| Spec-kit artifact | What it needs from MTA | Mechanical or judgment? |
|---|---|---|
| `spec.md` — behavior + integration contract | The **technology inventory**: every mandatory rule as a "legacy uses X" statement; config/integration-class findings surfaced as *preserve candidates* to confirm against migration.yaml | Inventory: mechanical. Behavioral contract: judgment (legacy tests + code reading) — findings only tell it *where to look* |
| `plan.md` — target mapping | The **rule → decided-target join**: for each mandatory rule, the MAPPINGS.md shape and the task class (`rewrite` if a deterministic transform exists, `infer` if design is needed) | Mechanical once MAPPINGS carries rule ids — today the join is implicit; making MAPPINGS rows carry the Windup rule ids they resolve makes it a lookup |
| `tasks.md` — packets | **Incident clusters**: group incidents by rule × file-cluster into packet-sized site lists; order clusters by `dependency-order.md` | Mechanical |
| migration.yaml contracts | Cross-check: findings touching config/env/endpoints proposed as preserve candidates | Mechanical proposal, human/model confirmation |

The unifying idea: Phase A should hand Phase B a **spec input bundle**
— findings inventory with the MAPPINGS join pre-computed, incident
clusters, dependency order, and the legacy test inventory — so the
Phase B session spends its judgment on the two things only it can do:
the behavioral contract and the genuinely open designs. Every run so
far has instead asked the model to re-derive the mechanical projections
and burned revision rounds when it dropped one.

## 5. Where OpenRewrite fits

**Rules detect; recipes transform.** Windup and OpenRewrite are two
halves of one pipeline that our task classes already anticipate:

- A **`rewrite` task** is, by our own definition (PLANNING.md),
  "mechanical: annotation/import/dependency swaps covered by
  OpenRewrite recipes." Today those tasks are still *executed by the
  model*. The correct end state is that a mandatory finding whose rule
  has a known recipe becomes a **scripted step** (like Phase A), not a
  model session: deterministic, fast, and immune to the harvest-
  ordering and format failures that cost us three red commits.
- The join is knowable in advance: `javax-to-jakarta-*` rules ↔
  `org.openrewrite.java.migrate.jakarta.JavaxMigrationToJakarta`
  (already recorded in MAPPINGS.md); Spring Boot version/property
  migrations ↔ `rewrite-spring` recipes; Quarkus version updates ↔
  `rewrite-quarkus` (this is what `quarkus update` runs). Note the
  ecosystem direction: newer MTA/kantra ships a `transform` command
  that runs OpenRewrite recipes directly — the detect→transform join is
  where the toolchain itself is heading, worth verifying against our
  kantra version before building on it.
- **The boundary is exactly our rewrite/infer line.** No recipe exists
  for JMS→CDI-events (a design choice), for the REST-client shape with
  a preserved env contract, for test semantics, or for anything
  MAPPINGS marks as decided-by-judgment. OpenRewrite raises the
  mechanical floor; it does not touch the judgment ceiling — which is
  precisely the Hermes-value division the harness audit committed to:
  scripts for process and mechanics, models for judgment.
- Practical caveat from run evidence: recipes run inside Maven and need
  a resolvable build — the pom-swap ordering problem (T-003/T-008)
  applies to recipe execution too, so recipe steps must sequence
  against the same dependency order as everything else.

Risk of NOT adopting this: every rewrite task remains a model session
that can format-fail, order-fail, or fabricate — we keep paying
judgment-session costs for non-judgment work. Cart run #2 spent ~9
model sessions on tasks whose commits show trivial or no-op mechanical
content.

## 6. Would graphify improve this step?

For the MTA→spec translation specifically: **marginally, and not yet.**

- What graphify would add over what we now have: multi-language
  support (irrelevant — our paths are Java), edge-confidence tags,
  community detection, and a browsable visualization. What it would
  add over `dependency-order.py` for a cart-sized app: nothing the
  runs would notice — the import graph already yields the ordering and
  god-node signals, validated against the real legacy tree.
- Where it could genuinely matter: **the monolith**, where community
  detection could propose packet boundaries (which files belong in one
  task) better than file-path clustering — and packet mis-scoping is a
  real cost driver at that scale. That is a Phase-B-input question,
  same slot as the dependency order, so the integration point is
  already built.
- What neither tool sees (and MTA partially does): runtime coupling —
  JNDI lookups, reflection, config-wired dependencies. Windup has rules
  for several of these. The findings inventory and the structural graph
  are complements; neither subsumes the other.

Verdict: hold graphify; re-evaluate on monolith-rerun evidence if
packetization is where the plan struggles. Adopting it earlier adds a
workspace-image dependency for signal we already have at cart scale.

## 7. Ranked recommendations (proposals, not implemented)

1. **Rule-id ↔ MAPPINGS join** — add the Windup rule ids each
   MAPPINGS.md row resolves to the table. Makes the findings→design
   translation a lookup; enables checking "every mandatory rule joins
   to a decided mapping or is explicitly flagged as open design" at
   plan time. Small, high leverage, no new tools.
2. **Spec input bundle in Phase A** — extend the scripted step to emit
   a findings inventory (per mandatory rule: description, incident
   cluster, joined mapping, task class) plus preserve-candidate
   proposals from config-class findings. Phase B's prompt then asks the
   model only for the behavioral contract and open designs.
3. **Recipe-executed rewrite tasks** — for rules joined to a recipe,
   execute as scripted supervisor steps (verify kantra-version
   `transform` support first; otherwise a direct Maven
   rewrite-maven-plugin invocation), with the task sensor gating each
   as usual. Reserves model budget for infer tasks.
4. **Graphify: watch, don't adopt** — decision point after the
   monolith rerun, on packetization evidence.

Order rationale: 1 and 2 strengthen the translation itself (the step
you named as crucial) with zero new dependencies; 3 changes who
executes work the translation has already classified; 4 is contingent.

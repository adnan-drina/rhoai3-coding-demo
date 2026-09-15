---
name: capture-source-oracles
description: >
  Use to record the expected runtime behaviour of the legacy system from
  the running source system itself, per admitted entry point (HTTP
  responses mechanically; scheduled, messaging, batch, and lifecycle
  entry points from operator-captured observations), and at M4 VERIFY to
  compare the destination against those records with a receipt-bound
  parity verdict. Expected values are never written by a worker or a
  model; a missing capture is INCONCLUSIVE, never a pass.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; network to the source and destination systems
metadata:
  author: rhoai3-harness-team
  version: "1.0.1"
  hermes:
    tags:
    - gates
    - m4
    category: gates
    kind: guidance
    paths:
      reads: ["/projects/modernized/evidence/planning"]
      writes: ["/projects/modernized/verification/source-oracles", "/projects/modernized/verification/parity"]
---
# Source-side oracles and runtime parity (M4)

M4 expected values come from the runnable source system or mechanical
evidence (SAD §8 step 8). This skill owns
`verification/source-oracles/*.json` (captured from the legacy system)
and `verification/parity/*.json` (destination comparison), both
append-only execution evidence bound to the admission receipt digest.
G-1..G-4 domain gates (`check-domain-parity`) and the M4 verdict
composer (`compose-m4-verdict`) are unchanged consumers.

## When to Use

- **Capture** once per planning cycle, against the legacy application
  running from the frozen source (any environment named in
  `decisions.yaml`), before M3 finishes.
- **Compare** on the `M4 VERIFY` card for every `parity:<entry point>`
  assertion the admitted DAG lists, with the destination running.
- **Not** to write an expected value by hand. `UNCAPTURED` oracles make
  the parity assertion INCONCLUSIVE and M4 cannot complete around it.

## Procedure

Reads are captured by request. Writes go through the **scenario corpus**: a
complete recorded request against a known initial state, with the effects that
prove what it did.

```bash
# 0. derive the corpus at M1, from the frozen source's own evidence (the
#    bundle's entry points, the OpenAPI examples, the seed rows, the
#    @CrossOrigin policies). Gaps are recorded, never filled in.
python3 "${HERMES_SKILL_DIR}/scripts/derive-source-scenarios.py" --root /projects/modernized

# 1. capture at M1 — one command, one runtime. It packages the frozen source,
#    starts it, restores the initial state before each scenario that asks for
#    it, replays the derived corpus, then captures the idempotent reads
#    through the same running source (corpus path_vars supply any templated
#    segment) and stops what it started. No admission receipt is needed: M1
#    precedes M2, so the capture binds to the evidence bundle.
python3 "${HERMES_SKILL_DIR}/scripts/capture-source-scenarios.py" --root /projects/modernized

#    then qualify what was captured against each scenario's own contract;
#    the parity receipt counts only qualified captures as coverage. This is
#    the third M1 step of this skill (paved-road-m1 steps.json), and it
#    RECORDS its verdict: only a refusal to judge exits non-zero
python3 "${HERMES_SKILL_DIR}/scripts/qualify-source-captures.py" --root /projects/modernized

#    reads alone, against a source someone else is running:
python3 "${HERMES_SKILL_DIR}/scripts/capture-source-oracles.py" --root /projects/modernized \
  --base-url http://legacy:9966/petclinic --path-var ownerId=1 --any-status \
  --observation 'ep:org.acme.jobs.SyncJob#sync():scheduled=/tmp/legacy-sync.log'

# 2. compare at M4, with the destination up. The scenario comparator restores
#    the declared initial state first and proves the destination is in it.
python3 "${HERMES_SKILL_DIR}/scripts/compare-runtime-parity.py" --root /projects/modernized \
  --dest-url http://localhost:8080/petclinic --entry-point 'ep:…'
python3 "${HERMES_SKILL_DIR}/scripts/compare-scenario-parity.py" --root /projects/modernized \
  --scenario 'sc:create-owner' --dest-url http://localhost:8080/petclinic
python3 "${HERMES_SKILL_DIR}/scripts/compose-parity-receipt.py" --root /projects/modernized
```

| Entry-point kind | Oracle | Mechanism |
|---|---|---|
| HTTP `GET`/`HEAD` | status + canonical JSON body (or text SHA-256) + asserted response headers when captured | requested mechanically; a templated path needs `--path-var` |
| HTTP `POST`/`PUT`/`PATCH`/`DELETE` | a scenario: complete request + initial state + declared effects + asserted headers (`Location`, `Access-Control-*`) | the corpus; a write with no effect declared refuses. The capture is the FIRST response (redirects are never followed) with the raw header values. `Location` is compared after mapping only the declared source origin to the destination's (path, escaping, query and fragment untouched); list-valued CORS headers compare as token sets. Every header the source exposes via `@CrossOrigin(exposedHeaders=…)` — read from M1's structure model, never from text — is asserted too, beside Location and the CORS set: a source that exposes an `errors` header has made it part of its contract, and a 400 whose errors moved elsewhere must not pass. A header the exchange requires — `Location` on a 201/3xx, the permission headers on a cross-origin exchange — against a capture with no `headers` map is INCONCLUSIVE: re-capture. "Required" is about COVERAGE, not value: a recorded null for one of them (no credential permission, say) is a legitimate observation and is compared as recorded |
| HTTP `OPTIONS` preflight | the permission headers the source answered (`Allow-Origin`, `Allow-Credentials`, `Allow-Methods`, `Allow-Headers`, `Max-Age`; `Expose-Headers` is the actual request's, not the preflight's) | a scenario carrying `Origin` + `Access-Control-Request-Method` (+ the request headers the actual call sends), no identity; it declares no effects |
| scheduled, messaging, batch, event, lifecycle | operator-captured observation file (log excerpt, queue dump, table export); normalized line set with timestamps stripped | `--observation <id>=<file>` |

## The scenario corpus

Scenario responses and before/after probes retain body evidence under
`verification/source-oracles/scenarios/bodies/<scenario>/`. Verify the file
against `evidence.retained_sha256`; for complete bodies it also matches
`evidence.raw_body_sha256`. The row's `body_sha256` remains the parity digest:
canonical JSON for JSON, raw bytes otherwise. Recompute that normalization
from the retained bytes and check it against the row before qualifying them.
The 1 MiB cap is explicit: `truncated: true` cannot prove full-list presence
or absence. Retain complete evidence before qualifying that scenario; do not
weaken its predicate. An unreadable exposed-header model refuses capture
before starting the source. `CAPTURED` still requires separate qualification.

### Deriving the corpus

`verification/scenarios/corpus.json` (`rhoai3.scenario-corpus/v1`) is a
**producer output**: `scripts/derive-source-scenarios.py` derives it from
evidence the harness already holds, and nothing in it is authored by a worker
or signed by a person. The concrete URLs come from the evidence bundle's entry
points; the request bodies from the frozen source's OpenAPI document (its own
`example` values, `$ref` and `allOf` resolved, `id` never sent on a create);
the seeded identifiers (`path_vars`, the row an update or delete addresses)
from `src/main/resources/db/<engine>/populateDB.sql`; the cross-origin
exchanges from every `@CrossOrigin` policy, and whether a delete's
references survive it from every JPA relationship, both in M1's structure
model. One scenario per rule per write entry point — `create`,
`create-invalid` (one property violating a declared `pattern` or `minLength`,
verified against the pattern), `update`, `delete` (`delete-referenced` or
`delete-cascading` where a row is referenced) — one `read` per entry point
whose mapping declares no HTTP method, and per policy a
`cors-actual` read and a `cors-preflight`. Each scenario records `derived_from` (which inputs produced
it) and `qualify` (what its capture must show).

**A data read declares `reset_before` too.** The derivation does **not** skip
the reset for a scenario just because it declares no effect: a `GET` of a
collection answers with whatever rows it finds, so its recorded body is only
deterministic if it reads a restored state — `sc:cors-actual-*` is a
collection GET and keeps `reset_before: true`, whatever the order the corpus
is walked in. What such a scenario does not have is a recorded **before**
state: the capture records the state the source started from by probing the
scenario's own effects, so one that declares none can never have one. That is
the comparator's business, not the derivation's — see *What refuses, and why*
below.

A **delete** addresses a row the database will let go. Every schema file
beside the seed (any `*.sql` in the same directory declaring `CREATE TABLE`,
found by content — petclinic's is `initDB.sql`, and every file read is listed
in `_derive.json`) is parsed for `FOREIGN KEY (col) REFERENCES table (col)`,
inline on a column or added by `ALTER TABLE`. The positive delete takes the
lowest seed row of the resource's table that nothing references; when every
row is referenced there is **no** unreferenced positive delete and a typed gap
names the constraint (`every seed row of specialties is referenced
(FK_VET_SPECIALTIES_SPECIALTIES/vet_specialties.specialty_id); no deletable
row derivable`). The table is named by the path variable's own mapping
(`{petTypeId}` → `types`), else the route's segments with the same
singular/plural tolerance; a table that cannot be named is a gap and the row
falls back to the path variable's.

A referenced row is a different question, and **the schema does not answer
it**. A foreign key with no `ON DELETE CASCADE` says the DATABASE will refuse;
it does not say the SOURCE will, because the application may remove the
references itself first. Measured on v9 (2026-09-14): the derived negatives
expected a refusal for owners, pets, types and vets and the frozen source
deleted all four (204); only `specialties` refused. So the other half of the
evidence is the persistence model in M1's structure model, read from the
annotations and their values — never from text. For the lowest referenced row,
each constraint that reaches it is classified:

- the **application** removes it — the delete target's entity declares a
  relationship whose target entity maps to the referencing table with
  `cascade` containing `ALL`/`REMOVE` or `orphanRemoval = true`
  (`Owner.pets @OneToMany(cascade = ALL)`), or the referencing table is the
  join table of a `@ManyToMany` the entity **owns** (it declares the
  `@JoinTable`, or the other side declares `mappedBy` pointing at its field —
  `Vet.specialties @JoinTable(vet_specialties)`);
- the **schema** removes it — the constraint itself declares `ON DELETE
  CASCADE` / `SET NULL`;
- **nothing** removes it — the entity declares neither (`Specialty` is the
  inverse `@ManyToMany` side; `PetType` declares nothing at all, `Pet.type`
  being a `@ManyToOne` on the child).

An entity is mapped to its table by `@Table(name)` when present, else by its
simple name with the same singular/plural tolerance, and that mapping is
recorded as evidence. A relationship's target entity is derived from
`targetEntity`, from the field type when that is itself an entity, from
`mappedBy` (the entity declaring a field of that name typed as this one) and
last from the field name — the structure model records the ERASED field type
(`java.util.Set`), so a collection's element type is never read off the field.

Each answer derives a different scenario, and nothing is derived from the
answer nobody has:

| the reference is removed by | scenario | contract |
|---|---|---|
| the application, or the schema's own `ON DELETE` rule | one positive `sc:delete-cascading-<resource>-<id>` on the lowest referenced row | `expect_status: [200, 204]`, the item reads back `404`, and so does each referencing row a **bound item route** can read (at most three, the cap noted in `derived_from`); with no such route the effect list is the item alone and `derived_from` says the children are unobservable through routes |
| nothing | one negative `sc:delete-referenced-<resource>-<id>` | any `4xx`, and the item still readable (`200`) afterwards |
| not derivable — no structure model, an entity or field that maps to no table, a cascade token this derivation does not know | **neither**; a typed gap (`delete-referenced ep:…: whether the application removes pets.owner_id references is not derivable (…)`) | — |

Both carry the FK evidence **and** the application-removal evidence in
`derived_from`, so the qualification record can quote which annotation on
which field decided it (or `none declared`). The gate needs no new check
kind: a cascading delete's effects are one `after_effect_status` map of
effect id → `404`.

An entry point whose mapping declares **no HTTP method** is not a gap. Spring
MVC reads `@RequestMapping` without `method` as matching EVERY method, so a
GET is a request the evidence supports, and one read scenario `sc:read-<path
slug>` is derived for it: a GET of the concrete path (path variables through
the same `path_vars` rule), `body_absent`, `reset_before: false`, no effects,
`derived_from` naming `structure:<controller>#<member> @RequestMapping without
method → GET (Spring: no method matches every method)`. Its contract is the
source's **own first response** — status, headers and body, redirects never
followed — because neither class is knowable in advance: petclinic's root
mapping answers `302` to `servletContextPath + "/swagger-ui/index.html"`,
another such mapping renders a page. So `qualify` states
`usable_first_response` and nothing else: qualification judges whether the
evidence can be judged at all and RECORDS the status class it observed
(`observed_status_class`), PASS on a usable non-5xx answer, INCONCLUSIVE
otherwise. At M4 the comparator compares that first response, `Location`
included, after mapping only the declared source origin — so a redirect target
that moved is a parity mismatch typed by its diffs. Measured on v9
(2026-09-14): this mapping was a gap, nothing observed it, and the destination
then replaced the SpEL `@Value("#{servletContext.contextPath}")` with
`@Value("")` — a redirect out of the destination's own root path that no
scenario could see. A method-less mapping whose handler declares a
`@RequestBody` parameter derives **no** GET (it consumes a body) and a typed
gap says so, as do a wildcard route and a member M1's structure model does not
record (a servlet mapping is not a request the corpus can derive).

What cannot be derived is a **gap**, recorded in the corpus and the receipt
and never filled in: a required property without an example, a path variable
no seed row supplies, a mapping with neither an HTTP method nor a method-less
`@RequestMapping` to derive one from. The corpus is bound
to the evidence bundle by digest in `verification/scenarios/_derive.json`;
the loader refuses a derived corpus edited after derivation (its digest no
longer matches), one derived against another bundle, or one whose receipt is
not `status: ok`. A hand-authored corpus naming `approved_by` is now the
**exception** (a specimen whose evidence cannot be derived); a placeholder
approver (`TODO`, `<who>`) is refused, and the derivation refuses to overwrite
a hand-authored corpus at its output path.

### Qualifying captures

`CAPTURED` records an observation, including an unexpected one.
`scripts/qualify-source-captures.py` checks every capture against its
scenario's `qualify` block and writes
`verification/source-oracles/scenarios/_qualification.json` with **two
results per scenario**:

- `evidence`: `USABLE` or `UNUSABLE` — can this capture be judged at all?
  It must exist and be `CAPTURED`, be bound to this corpus, this bundle and
  this very request (`request_sha256`), every retained body the contract
  reads must be present, digest-bound (`retained_sha256`, `raw_body_sha256`,
  not `truncated`, `body_sha256` recomputing) and every read-back the
  contract reads must have answered 2xx. Evidence is judged **before**
  intent: with unusable evidence `capability` is INCONCLUSIVE, never FAIL,
  while `known_failures` still records what was observed (a 500 is on the
  record, not hidden).
- `capability`: `PASS | FAIL | INCONCLUSIVE` — did the source demonstrate
  what the scenario intends? `qualify.intent` is `positive` (create, update,
  delete, cors-actual, cors-preflight: the source performed it) or
  `negative` (create-invalid: the source rejected as intended — the status,
  a parsed field error naming the property, and no effect).

The checks: `expect_status`; `usable_first_response` (a read derived from a
method-less mapping: the capture carries a first response at all — the class
is not asserted, it is recorded); `expect_status_class` (`4xx`: the source
refused, and which 4xx is its own choice — a derived `delete-referenced`
states exactly this); `location: absolute-under-base` (absolute, on
the capture's `source.base_url` origin, under its path, compared literally);
`creates_one_entity` with `identity_field` (derived from the collection
GET's OpenAPI response schema — the items' `id`, else the first readOnly
integer; `null` makes the gate INCONCLUSIVE "collection identity not
derivable"): exactly one entity with a NEW identity appears after the
create, it carries every key/value of the request body, every prior entity
is still present unchanged, and the Location's last path segment is that
identity — a duplicate row with an existing id and a Location pointing at
999 FAILs naming each broken condition; `after_contains_body`;
`before_lacks_body` (hand-authored corpora); `after_equals_before` (same
digest and status, both read-backs 2xx and retained);
`errors_header_names_field` (the `errors` header must parse as JSON —
petclinic's BindingErrorsResponse is an array of objects — and carry an
element whose values include the property: not JSON is INCONCLUSIVE "errors
header not parseable", no such element is FAIL); `after_effect_status`;
`cors_allow_origin`, `cors_expose_headers`, `cors_allow_method`,
`cors_allow_headers` (token sets). Each record is bound to the exact capture
it judged (`capture_sha256`, `request_sha256`, `corpus_sha256`,
`evidence_bundle_sha256`).

Evidence is weighed first and intent second, and the two are not the same
question. An UNUSABLE capture — absent, unbound, a retained body that is not
whole or not its digest, a read-back that did not answer 2xx, an `errors`
header that does not parse, a 5xx the contract does not name — is
INCONCLUSIVE, never FAIL, with what was observed in `known_failures`. With
usable evidence the capability is judged over the predicates that could be
judged: **any judged predicate failing is FAIL**, none failing with at least
one unjudgeable (`creates_one_entity` where the document names no
`identity_field`) is INCONCLUSIVE, all judged and passing is PASS. A 400
carrying a well-formed errors header is usable evidence, so an
`expect_status` miss on it is a judged failure — on v9 that mismatch was
reported INCONCLUSIVE because the same create's identity was unanswerable,
and went unrecorded. The unjudgeable predicate stays in `checks` (`ok: null`)
and in `unjudged` either way.

Negative scenarios are derived **one per constrained property**
(`sc:create-invalid-<resource>-<property>`), so a `firstName` rejection is
never mistaken for `telephone` coverage.

The gate is an **M1 step** (`paved-road-m1` `steps.json`, right after
`capture-source-scenarios`), and its verdict is a record, not a refusal: it
exits 0 whenever a bound qualification document was written, PASS, FAIL or
INCONCLUSIVE alike (`OK: qualification FAIL (4 of 19 not qualified) → …`),
and exits 1 only when it cannot judge at all — no corpus, a corpus that is
neither derived nor authored, a provenance whose digests no longer bind, or
not one capture on disk. A FAIL is a fact about the SOURCE, which M4 turns
into a coverage gap and which never becomes a destination card, so failing
the step on it would have been a refusal to record what the source does.
`compose-parity-receipt.py` reads the records: a qualification whose
`capture_sha256` no longer matches the capture on disk is stale
(`requalify after recapture`, INCONCLUSIVE); a scenario qualified
INCONCLUSIVE, or with no record, makes its entry point INCONCLUSIVE
(`capture not qualified: …`) and is listed under `coverage_gaps` with
`kind: inconclusive-qualification` — a capability nobody judged is a
capability nobody demonstrated, and without that entry the M4 coverage
account could not see it; a derived corpus with no qualification at all
is INCONCLUSIVE (`captures not qualified`). A **positive** scenario whose
capability is FAIL is a **source-side fixture failure** (a create the source
answered 400 for): the source did not perform the operation, so parity
is not asked — `compare-scenario-parity.py` writes INCONCLUSIVE `source
fixture failed qualification: …`, the entry point is INCONCLUSIVE, the
scenario is listed under `coverage_gaps` with `kind: fixture-failed`, it
earns no parity credit and never becomes a destination repair card
(`worklist.parity_items` issues obligations only from FAIL verdicts). A
negative scenario whose capability is PASS compares parity normally and is
counted as negative coverage only (`coverage.negative` on the row). The M4
coverage account (`compose-coverage-account.py`) records every receipt
coverage gap as an `uncovered_capabilities` entry and denies replacement
credit to any `replaced_by` entry point carrying a positive one. An
Operator-authored corpus without a qualification file keeps its previous
behaviour.

The operation for a route is found by path (exact, else the longest document
path the route ends with); a path match whose `operationId` names a
different controller member is a typed gap (`conflicting binding: path X ↔
operationId Y ≠ member Z`). When the document's paths do not name the
code's routes (petclinic documents `/owner` while the controller maps
`/api/owners`) an explicit adapter binds by `operationId` equal to the entry
point's method name, same HTTP method, provided exactly one controller
member of that name exists in the bundle or one is singled out by a
compatible request schema (the parameter DTO and the schema share a stem
after `Dto|Fields|Request|Input|Payload`: `OwnerDto` ↔ `OwnerFields`); tags
only narrow, never establish, and a surviving ambiguity is a gap. A name
match is not yet a binding: the operation's **path variables must be exactly
resolvable through the route's** — the same set of names, compared literally
(one variable on each side under a different name still binds, since the
path binder this adapter stands in for matches with the names erased). A
difference is a typed gap and **no scenario at all**, positive or invalid
(`create ep:…addPet: operationId addPet binds POST /owner/{ownerId}/pet
(variables: ownerId) to route /api/pets (variables: none); path-variable sets
differ; not bound`): on v9 that binding handed `POST /api/pets` a
`PetFields` body whose identity the route cannot express, the source answered
400, and the gate could only say INCONCLUSIVE. The discrepancy that DOES bind
is recorded in `derived_from.evidence`
(`openapi-path:/owner≠route:/api/owners; bound by operationId addOwner`).
The derivation receipt also binds every body file's bytes and every
scenario's `request_sha256`; a body edited after derivation is refused.

### The corpus document

Start from `.hermes/planning/scenarios.example.json` only for the
hand-authored exception; it carries the shape and the rules below. An optional `path_vars`
map supplies the values the idempotent reads need for templated paths, from
the source's own seeded data. Each scenario carries the
method, a **concrete** URL (never a route pattern — the route stays in the
inventory and is associated with scenario URLs), the headers, how it
authenticates (**by environment-variable reference**), the body bytes or an
explicit `body_absent: true`, whether the initial state is restored first, the
effects that prove the write, and the permitted normalization.

CORS is covered per policy. `cors_policies` declares each one (`id`, the
`request_headers` its actual calls send); a scenario that sends `Origin` names
its `cors_policy`. Each policy needs an actual cross-origin exchange and a
preflight, and every policy the frozen source declares — each distinct
`@CrossOrigin`, each CORS registry, read from M1's structure model — must be
declared. Missing coverage makes the parity receipt INCONCLUSIVE.

Ownership: the Operator owns intent and environment authorization; the M1
producer owns execution; implementation workers own neither and never see an
expected value.

What refuses, and why:

- A path with `{...}` or `*` in a scenario. A scenario is a request.
- A scenario that neither names a body nor states it has none. An absent body
  (a `DELETE`) is a fact to record, not an omission to infer.
- A write scenario with no declared effect. An identical response does not
  prove the write happened.
- A replay whose reconstructed request digest differs from the one the source
  answered. **This is the defect the corpus exists for**: the comparator used
  to send the recorded method and path with no body, so a `POST` the source
  answered `201` for was replayed empty, answered `400`, and compared `FAIL`
  against a destination that behaved identically.
- A source capture taken against a different corpus digest. Re-capture the
  source rather than comparing across corpora.
- A `204` that deleted nothing. The response matches and the effect does not.
- A destination that is **not in the state the source started from**. Each
  capture records the effect probes *before* the request too, and the
  comparator restores the declared initial state (`reset_before`) and then
  proves it. Without that, a delete against a destination whose row was
  already absent passed on both the response and the effect. A scenario that
  declares `reset_before` and **effects** whose capture recorded no before
  state is INCONCLUSIVE: those probes were asked for, so re-capture the
  source. A scenario that declares `reset_before` and **no effects** is a
  different case and is **not** a refusal: the capture records the before
  state by probing the scenario's own effects, so one that declares none never
  had a before state for anyone to record. It is reset like any other — the
  request may depend on the seeded rows, and a collection read's body is only
  deterministic against a restored state — and then compared on its first
  response: the verdict notes `before_state: none declared`, PASS when the
  response matches, FAIL typed by its diffs when it does not, never
  INCONCLUSIVE for the absence of a state nobody could have recorded.
  Measured on v9's first M4 parity receipt (2026-09-15): `sc:cors-actual-*`
  (a `GET` with `effects: []`) came back INCONCLUSIVE on exactly that absence.
- A declared reset that could not run. The comparison does not happen.
- A required scenario with **no result**, a result bound to another receipt or
  another corpus, or two results for one scenario. The required set comes from
  the corpus, never from which files exist.

## Verification

- Every oracle file carries `receipt_sha256`, the entry point id, and
  `status` in `CAPTURED` / `UNCAPTURED` / `INCONCLUSIVE`.
- `compare-runtime-parity.py` exits 0 only on `PASS`; `FAIL` and
  `INCONCLUSIVE` exit 1 and are named in the parity record, so the K2
  hook refuses `kanban_complete` on that card.
- `compose-parity-receipt.py` writes `verification/parity/receipt.json`
  binding every parity verdict to the receipt digest; it is produced by
  this script (an independent producer), not by the verdict author.
- `scripts/capture-source-oracles.test.py`: HTTP capture and compare
  PASS/FAIL against a local stub server; non-HTTP compare with matching
  and diverging observations; missing oracle → INCONCLUSIVE; a
  destination failure cannot be completed around (exit 1 recorded).

## Scripts

- `scripts/derive-source-scenarios.py` — M1 producer: derive the corpus from
  the bundle, the OpenAPI examples, the seed rows, the seed schema's foreign
  keys, the JPA relationships that decide whether the application removes those
  references itself, and the CORS policies; gaps recorded, bound to the bundle in
  `verification/scenarios/_derive.json` (which also lists every SQL file read)
- `scripts/capture-source-oracles.py` — read capture from the source system
- `scripts/capture-source-scenarios.py` — M1 producer: package and start the
  frozen source, restore state, capture the derived scenarios, clean up
- `scripts/qualify-source-captures.py` — the qualification gate and the third
  M1 step: every capture against its scenario's `qualify` contract, reading the
  retained bodies by digest; PASS / FAIL / INCONCLUSIVE per scenario, all three
  recorded and exiting 0; exit 1 only on a refusal to judge
- `scripts/compare-runtime-parity.py` — destination comparison for reads
- `scripts/compare-scenario-parity.py` — recorded-request replay plus effects
- `scripts/compose-parity-receipt.py` — receipt-bound parity receipt; an entry
  point covered by scenarios passes only when every one of them passes
- `scripts/reset-parity-db.sh` — restore the decided instance to the initial
  state the corpus names (drop and recreate the schema, apply the schema and
  seed assets `decisions.yaml` points at)
- `scripts/_scenarios.py` — the corpus model and the request digest
- `scripts/capture-source-oracles.test.py`, `scripts/scenario-parity.test.py`,
  `scripts/scenario-derivation.test.py` — selftests (the last one: derivation,
  loader binding, qualification and the receipt's use of it)

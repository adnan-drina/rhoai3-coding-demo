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
#    the parity receipt counts only qualified captures as coverage
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
exchanges from every `@CrossOrigin` policy in M1's structure model. One
scenario per rule per write entry point — `create`, `create-invalid` (one
property violating a declared `pattern` or `minLength`, verified against the
pattern), `update`, `delete` — and per policy a `cors-actual` read and a
`cors-preflight`. Each scenario records `derived_from` (which inputs produced
it) and `qualify` (what its capture must show).

What cannot be derived is a **gap**, recorded in the corpus and the receipt
and never filled in: a required property without an example, a path variable
no seed row supplies, an entry point with no HTTP method. The corpus is bound
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
`verification/source-oracles/scenarios/_qualification.json`: `expect_status`;
`location: absolute-under-base` (absolute, on the capture's `source.base_url`
origin, under its path); `after_contains_body` (the request body's key/values
present in an object of the retained read-back afterwards);
`after_adds_one_body` (exactly one more matching object after than before —
a document's example is often a seeded row verbatim, so a derived create
promises "one more", never "absent before"); `before_lacks_body` (kept for a
hand-authored corpus); `after_equals_before` (same digest and status); 
`errors_header_names_field`; `after_effect_status`; `cors_allow_origin`,
`cors_expose_headers`, `cors_allow_method`, `cors_allow_headers` (token sets).
Retained bodies are read only when their file matches `retained_sha256`, the
body is complete (`raw_body_sha256`, not `truncated`) and the row's
`body_sha256` recomputes. A missing capture, a missing or unbound body, a
digest mismatch or a scenario without a contract is INCONCLUSIVE, never a
pass; a check that does not hold is FAIL. The gate exits 0 only when every
scenario the corpus lists is PASS. `compose-parity-receipt.py` reads the
verdicts: a scenario qualified **INCONCLUSIVE** (or with no record) makes its
entry point INCONCLUSIVE (`capture not qualified: …`), and a derived corpus
with no qualification at all is INCONCLUSIVE (`captures not qualified`). A
scenario qualified **FAIL** does *not*: its capture is still faithful parity
evidence (a source that refuses to delete a referenced row has demonstrated a
rejection the destination must reproduce), so the entry point is judged on
parity and the scenario is listed under the receipt's `coverage_gaps`
(`{scenario, entry_point, reason}`) — the intent was not demonstrated, and
that stays on the record. An Operator-authored corpus without a
qualification file keeps its previous behaviour.

The operation for a route is found by path (exact, else the longest document
path the route ends with) or, when the document's paths do not name the
code's routes (petclinic documents `/owner` while the controller maps
`/api/owners`), by `operationId` equal to the entry point's method name; two
controllers sharing a method name are told apart by the operation's tag or
body-schema stem, and an ambiguity that survives is a gap.

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
  already absent passed on both the response and the effect.
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
  the bundle, the OpenAPI examples, the seed and the CORS policies; gaps
  recorded, bound to the bundle in `verification/scenarios/_derive.json`
- `scripts/capture-source-oracles.py` — read capture from the source system
- `scripts/capture-source-scenarios.py` — M1 producer: package and start the
  frozen source, restore state, capture the derived scenarios, clean up
- `scripts/qualify-source-captures.py` — the qualification gate: every capture
  against its scenario's `qualify` contract, reading the retained bodies by
  digest; PASS / FAIL / INCONCLUSIVE per scenario, exit 0 only on all PASS
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

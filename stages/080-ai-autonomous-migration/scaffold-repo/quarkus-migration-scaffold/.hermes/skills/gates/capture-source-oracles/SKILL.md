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
  version: "1.0.0"
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
# 1. capture at M1 — one command, one runtime. It packages the frozen source,
#    starts it, restores the initial state before each scenario that asks for
#    it, replays the approved corpus, then captures the idempotent reads
#    through the same running source (corpus path_vars supply any templated
#    segment) and stops what it started. No admission receipt is needed: M1
#    precedes M2, so the capture binds to the evidence bundle.
python3 "${HERMES_SKILL_DIR}/scripts/capture-source-scenarios.py" --root /projects/modernized

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
| HTTP `POST`/`PUT`/`PATCH`/`DELETE` | a scenario: complete request + initial state + declared effects + asserted headers (`Location`, `Access-Control-*`) | the corpus; a write with no effect declared refuses. The capture is the FIRST response (redirects are never followed) with the raw header values. `Location` is compared after mapping only the declared source origin to the destination's (path, escaping, query and fragment untouched); list-valued CORS headers compare as token sets. A header the exchange requires — `Location` on a 201/3xx, the permission headers on a cross-origin exchange — against a capture with no `headers` map is INCONCLUSIVE: re-capture |
| HTTP `OPTIONS` preflight | the permission headers the source answered | a scenario carrying `Origin` + `Access-Control-Request-Method` (+ the request headers the actual call sends), no identity; it declares no effects |
| scheduled, messaging, batch, event, lifecycle | operator-captured observation file (log excerpt, queue dump, table export); normalized line set with timestamps stripped | `--observation <id>=<file>` |

## The scenario corpus

`verification/scenarios/corpus.json` (`rhoai3.scenario-corpus/v1`) is
**Operator-approved intent** and names its approver. Start from
`.hermes/planning/scenarios.example.json`, which carries the shape and the
rules below. An optional `path_vars`
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

- `scripts/capture-source-oracles.py` — read capture from the source system
- `scripts/capture-source-scenarios.py` — M1 producer: package and start the
  frozen source, restore state, capture the approved scenarios, clean up
- `scripts/compare-runtime-parity.py` — destination comparison for reads
- `scripts/compare-scenario-parity.py` — recorded-request replay plus effects
- `scripts/compose-parity-receipt.py` — receipt-bound parity receipt; an entry
  point covered by scenarios passes only when every one of them passes
- `scripts/reset-parity-db.sh` — restore the decided instance to the initial
  state the corpus names (drop and recreate the schema, apply the schema and
  seed assets `decisions.yaml` points at)
- `scripts/_scenarios.py` — the corpus model and the request digest
- `scripts/capture-source-oracles.test.py`, `scripts/scenario-parity.test.py` — selftests

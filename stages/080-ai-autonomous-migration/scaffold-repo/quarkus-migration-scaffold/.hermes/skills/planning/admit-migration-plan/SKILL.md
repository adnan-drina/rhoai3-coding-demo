---
name: admit-migration-plan
description: >
  Use at M2 PLAN after build-worklist, and after every loop step (advance.py
  calls it), to compose the admission receipt: schema-validate the evidence
  bundle and the work list, re-derive every fail-closed boundary (tool pins
  vs receipts, MTA provenance and canary, activation / pilot seal, required
  decisions, bootstrap receipt, fully known measure), seal bundle + work
  list + bootstrap + decisions.yaml + contracts + pins, and record ADMITTED
  / INCONCLUSIVE / COMPAT_FAIL. K4 mints only from ADMITTED; the first step
  of every M2 card is this skill's assert-planner-activated.py. Never edits
  an artifact; never infers a decision.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - planning
    - m2
    category: planning
    kind: guidance
    paths:
      reads: ["/projects/modernized/evidence/planning", "/projects/modernized/decisions.yaml", "/projects/modernized/.hermes/planning", "/projects/modernized/.hermes/pins.json"]
      writes: ["/projects/modernized/evidence/planning/admission-receipt.json"]
---
# Admit the migration plan (M2 producer of `m2-admission`)

Owns `evidence/planning/admission-receipt.json` (SAD v3 §7). The receipt
digest is the SHA-256 of the canonical receipt without its own
`receipt_digest`. K4 binds every Hermes idempotency key and every K1 card
body to it; K3 proves the live board against it. Admission means "the
loop may run its next step from this exact state".

Two fail-closed boundaries are re-checked here (and again by K4)
on every admission: the **activation gate / pilot seal**
(`pins.planner.activation` is `activated`, or `pilot` with a seal whose
`evidence_bundle_sha256` equals this bundle) and **tool pins** (every
mandatory producer and every used optional producer pinned, receipt and
pin agreeing on version and artifact digest). The receipt records
`activation.mode` and, for a pilot, its `run_id`.

| Status | Meaning | Downstream |
|---|---|---|
| `ADMITTED` | no open BLOCK: tools pinned and matching their receipts, MTA admissible with the canary fired and every incident conserved, activation/pilot seal covers this bundle, decisions present, bootstrap receipt bound to this bundle, measure fully known; a deferred (manual) cluster blocks only once nothing else is left | K4 may mint the head card (or M4 VERIFY on an empty list) |
| `INCONCLUSIVE` | at least one open BLOCK (a failed build is `planning_only`) | nothing mints; resolve via ADR in `decisions.yaml`, rerun the chain |
| `COMPAT_FAIL` | the bundle or the work list fails its schema | planner defect; fix the planner, never the artifact |

## When to Use

- Third step of `paved-road-m2`, immediately after
  `build-worklist`; re-run by `fix-until-green/scripts/advance.py` after every step. Producer of the M2 artifact.
- `scripts/assert-planner-activated.py` is the **first** M2 step: it
  refuses unless `.hermes/pins.json` `planner.activation` is `activated`
  (SAD §12). Until the activation gate passes, M2 is unavailable and the
  card `kanban_block`s here with a named reason.
- `scripts/verify-admission-receipt.py` is what K4, K3, and every M3/M4
  worker run before trusting the receipt: it re-digests all sealed
  inputs on disk. Any drift (an edited artifact, a changed
  `decisions.yaml`, a moved pin) makes the receipt non-authoritative.

## Procedure

```bash
python3 "${HERMES_SKILL_DIR}/scripts/assert-planner-activated.py" --root /projects/modernized   # step 1 of M2
python3 "${HERMES_SKILL_DIR}/scripts/admit-migration-plan.py" --root /projects/modernized        # after the planner
python3 "${HERMES_SKILL_DIR}/scripts/verify-admission-receipt.py" --root /projects/modernized    # consumers
```

`admit-migration-plan.py` exits 0 only on `ADMITTED`; `INCONCLUSIVE`
exits 1 with the BLOCK list on stderr; `COMPAT_FAIL` exits 2. In every
case the receipt file is written — the verdict is evidence, not a crash.

## Verification

- `scripts/admit-migration-plan.test.py` proves: an unblocked specimen
  is ADMITTED; a hand-edited work list is COMPAT_FAIL; every negative from the
  planner test yields INCONCLUSIVE; `verify-admission-receipt.py` refuses
  after `decisions.yaml` or an artifact changes; the receipt digest is
  stable across reruns; the activation gate refuses on the golden
  `pins.json`.

## Scripts

- `scripts/assert-planner-activated.py` — activation gate (SAD §12)
- `scripts/admit-migration-plan.py` — the producer
- `scripts/verify-admission-receipt.py` — consumer-side seal verification
- `scripts/admit-migration-plan.test.py` — selftest

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

```bash
# capture (source system up)
python3 "${HERMES_SKILL_DIR}/scripts/capture-source-oracles.py" --root /projects/modernized \
  --base-url http://legacy:8080 \
  --observation 'ep:org.acme.jobs.SyncJob#sync():scheduled=/tmp/legacy-sync.log'
# compare (destination up)
python3 "${HERMES_SKILL_DIR}/scripts/compare-runtime-parity.py" --root /projects/modernized \
  --dest-url http://localhost:8080 --entry-point 'ep:…'
python3 "${HERMES_SKILL_DIR}/scripts/compose-parity-receipt.py" --root /projects/modernized
```

| Entry-point kind | Oracle | Mechanism |
|---|---|---|
| HTTP `GET`/`HEAD` | status + canonical JSON body (or text SHA-256) | requested mechanically |
| HTTP `POST`/`PUT`/`PATCH`/`DELETE` | `INCONCLUSIVE` unless `--request-file` supplies a recorded request body | non-idempotent; never invented |
| scheduled, messaging, batch, event, lifecycle | operator-captured observation file (log excerpt, queue dump, table export); normalized line set with timestamps stripped | `--observation <id>=<file>` |

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

- `scripts/capture-source-oracles.py` — capture from the source system
- `scripts/compare-runtime-parity.py` — destination comparison, one entry point
- `scripts/compose-parity-receipt.py` — receipt-bound parity receipt
- `scripts/capture-source-oracles.test.py` — selftest

---
name: verify-live-kanban-loop
description: >
  Use at M2 PLAN after k4_mint.py --exec, and any time before dispatching
  a loop card, to prove the native Hermes board equals the loop's
  expected card set: every accepted step's card and the one open head
  card (or M4 VERIFY), each under its receipt-bound key, chained by
  parent, no foreign cards, no missing cards. Matching is by native
  idempotency key or by K4's own mint receipts, never by title or body.
  Writes evidence/receipts/k3/live-board.json. Not claimed control; the
  foreign-card audit is the control of record.
license: Apache-2.0
compatibility: Linux seat; Hermes Kanban CLI (list/show --json); Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - planning
    - m2
    - k3
    category: planning
    kind: guidance
    paths:
      reads: ["/projects/modernized/evidence/planning", "/projects/modernized/verification/loop", "/projects/modernized/evidence/receipts/k4"]
      writes: ["/projects/modernized/evidence/receipts/k3/live-board.json"]
---
# Verify the live Kanban board against the loop (K3 live)

```bash
python3 "${HERMES_SKILL_DIR}/scripts/verify-live-kanban-loop.py" --root /projects/modernized --live --exempt "$HERMES_KANBAN_TASK"
```

Or with a snapshot (`--snapshot FILE`, the JSON of `hermes kanban list
--json` enriched with `show --json`).

1. Verifies the admission receipt seals (`verify-admission-receipt.py`).
2. Expected cards: each accepted step in `verification/loop/steps.json`
   (task id → key from `evidence/receipts/k4/mints.json`) plus the card K4
   would mint now; parents chain step to step.
3. Cards match **only** by native idempotency key or by the mint receipts.
   A matching title or a body carrying the receipt digest proves nothing.
   Exempting this M2 card exempts its ancestors (the M1 it descends from).
4. Anything else on the board is foreign → `MISMATCH`, exit 1.

## Verification

- `.hermes/kernel/k4_mint_selftest.py`: EQUAL after mint; missing,
  foreign, fabricated-keyless cards refuse; keyless boards match through
  the mint receipts; M2 → M1 closure.

## Scripts

- `scripts/verify-live-kanban-loop.py` — comparator (wraps `.hermes/kernel/k3_live.py`)

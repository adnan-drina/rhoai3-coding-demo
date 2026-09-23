---
name: compose-serial-roadmap
description: >
  Use after M2 admission (and whenever a reviewer asks for the serial
  migration roadmap) to derive evidence/planning/serial-roadmap.json from
  the work list and admission receipt. Shows known work, dependencies,
  acceptance checks, and unresolved questions. Marks exactly one admitted
  next card as executable and lists remaining M3 clusters plus M4 VERIFY
  and M5 PREFLIGHT / DEPLOY / VALIDATE as planned milestones that must not
  claim a candidate, receipt, or card id. Parallel M3 execution stays
  deferred. Do not use this as a second plan, an M2 KEEP/audit step, a K4
  mint, or an M5 eligibility gate.
license: Apache-2.0
compatibility: Linux seat; Hermes v0.20.5 Kanban; Python 3.11+
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
      reads: ["/projects/modernized/evidence/planning", "/projects/modernized/evidence/producers", "/projects/modernized/verification/loop"]
      writes: ["/projects/modernized/evidence/planning/serial-roadmap.json"]
---
# Compose the serial roadmap after M2

The work list remains the only plan. Admission writes this derived view
after the receipt so M4 VERIFY and M5 PREFLIGHT / DEPLOY / VALIDATE are
visible after M2 without minting them or inventing a delivery candidate.
Re-run this skill only to refresh the same file. It is not a second plan,
an M2 KEEP/audit step, a K4 mint, or an M5 eligibility gate.

| Class | Meaning |
|---|---|
| `executable` | At most one admitted task: `next_card` when admission is `ADMITTED` (head M3, or M4 VERIFY when the list is empty, runtime-ready, and nothing is deferred) |
| `planned` | Remaining open M3 clusters, then M4 VERIFY if it is not already executable, then M5 PREFLIGHT / DEPLOY / VALIDATE. No `card_id`, `candidate_sha`, or `receipt_sha256` |
| `unresolved` | Admission blocks, deferred/blocked clusters, unlocatable obligations |
| `reconciled` | Decided-repair rows already `applied` or `already-applied` |

`parallel_execution` is always `deferred`. Admission does not seal this
file. K4 still mints exactly one card. M5 still starts only after closed
M4 via `start-m5-delivery.py`.

## Procedure

```bash
python3 "${HERMES_SKILL_DIR}/scripts/compose-serial-roadmap.py" --root /projects/modernized
```

Optional `--print` writes the document to stdout as well. Missing work
list or admission receipt exits 2. This is not a paved-road-m2 KEEP
step and not a release gate.

## Verification

- `.hermes/lib/planner/roadmap.test.py` proves one executable M3, planned
  M4/M5 without candidate/receipt claims, INCONCLUSIVE admission with
  zero executable tasks, empty ready work list executing M4 only, and
  reconciled decided repairs.
- `evidence/planning/serial-roadmap.json` validates against
  `.hermes/planning/schemas/serial-roadmap.schema.json`.

---
name: paved-road-m1
description: >
  Use at M1 ANALYZE as the kind index. Pin only --skill paved-road-m1.
  Follow steps.json in order (skill_view subskills; native kanban_attach.py).
  Happy-path terminator is kanban_request_review, not kanban_complete.
  kanban_block for external/platform (MaaS 500, missing key, GPU). Do not
  pin derive-legacy-boot3, scan-with-mta, and inventory-legacy-surface on
  the card. Do not use for M2 PLAN, M3, or M4.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; Hermes Kanban
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - paved-road
    - m1
    category: paved-road
    kind: guidance
---
# M1 ANALYZE paved-road (index)

This skill is the **M1 procedure index**. Ordered mandated steps live in
`steps.json`. `audit.json` is generated from that file — do not edit it
by hand. Do not copy subskill SKILL.md bodies into this file.

Pin **only** this leaf (`--skill paved-road-m1`). Subskills load via
`skill_view` from the step list.

## When to Use

- This card is **M1 ANALYZE**.
- **Not** M2 PLAN (`paved-road-m2`).
- **Not** dest-init mint (`dispatch-phase`).

## Procedure

1. Read `steps.json`. Follow that listed order (derive → inventory →
   scan → attach). `mta-analyze-legacy.sh` already emits the handoff;
   do not insert emit as its own step.
   - `skill` — `skill_view` that leaf and follow its SKILL.md.
   - `kernel` — run the named argv under `.hermes/kernel/`.
   - `native` — run the named verb (`kanban_attach.py` KEEP listed on the step).
2. KEEP paths on the step must exist under the workspace root.
3. Happy-path terminator: `kanban_request_review` (not `kanban_complete`).
4. `kanban_block` for external/platform (MaaS 500, missing key, GPU).
5. Reviewer runs `scripts/assert-paved-road-audit.py --log <official> --root <ws>`.
   Land-time `scripts/selftest.py` is not dest.

Producer of artifact `m1-analyze` is the `scan-with-mta` step (findings +
attach). Paved-road itself is the index, not a second producer.

## Gotchas

- Silence fails. An unmatched `[exit 1]` on a mandated needle fails.
  A later clean invocation of the *same* needle clears an earlier red.
  Do not last-wins across different needles (dest-14 `bound_gate_red` hole).
- `inventory-legacy-surface` precedes `scan-with-mta`: the latter's one
  entry point runs `emit-findings-handoff.py` internally, which refuses
  (AR-4.1) without `evidence/entry-point-inventory.json`. Re-running the
  inventory after the handoff invalidates its digest.
- Path mention / grep / cat of a SKILL.md is not `skill_view`.
- Do not `kanban daemon --force`. Do not dest-apply dest-14.

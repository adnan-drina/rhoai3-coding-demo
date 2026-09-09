---
name: paved-road-m2
description: >
  Pin only this on the M2 PLAN card. Index for the fix-until-green loop's
  planning step: the activation gate (native), the deterministic
  bootstrap (bootstrap-destination), the plan = tool-computed work list
  plus baseline (build-worklist), admission (admit-migration-plan, the
  producer), one K4 mint (kernel k4_mint.py: the head cluster's card),
  and the live-board comparison (verify-live-kanban-loop). No LLM plans;
  no partition; no capability graph. INCONCLUSIVE admission is a legal
  stop (kanban_block). Never for story implementation.
license: Apache-2.0
compatibility: Linux seat; Hermes v0.20.5 Kanban; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "3.0.0"
  hermes:
    tags:
    - paved-road
    - m2
    category: paved-road
    kind: guidance
---
# Paved road: M2 PLAN (activation gate → bootstrap → work list → admission → one mint → K3)

`steps.json` is the contract; `audit.json` is generated from it
(`python3 .hermes/lib/paved_road.py generate --steps steps.json --out audit.json`).
The reviewer runs `scripts/assert-paved-road-audit.py` over the official
Kanban log; silence, a missing KEEP file, or an unmatched `[exit 1]` refuses.

## Procedure (in order)

1. `python3 .hermes/skills/planning/admit-migration-plan/scripts/assert-planner-activated.py --root /projects/modernized`
   — refuses while `pins.planner.activation` is `not-activated` (or a
   pilot seal does not cover this bundle): `kanban_block` naming the gate.
2. `skill_view bootstrap-destination` → run its script (deterministic
   pom / properties / main-class baseline; KEEP `evidence/producers/bootstrap.json`).
3. `skill_view build-worklist` → run its script (JDK diagnostics, tests,
   MTA rescan → `evidence/planning/worklist.json`; baseline step in
   `verification/loop/steps.json`).
4. `skill_view admit-migration-plan` → run its script (KEEP
   `evidence/planning/admission-receipt.json`). INCONCLUSIVE → `kanban_block`
   (kind `needs_input`) naming the BLOCK classes; a human resolves them via
   `decisions.yaml` + ADR or by pinning a tool. Never hand-edit an artifact.
5. `python3 .hermes/kernel/k4_mint.py --root /projects/modernized --exec --verify-board`
   — mints exactly one card (the head cluster) and refuses with zero
   commands unless the receipt is ADMITTED.
6. `skill_view verify-live-kanban-loop` → run its script (KEEP
   `evidence/receipts/k3/live-board.json`) proves the board equals the
   loop's expected cards.
7. `kanban_request_review` with `reviewer=reviewer` and `created_cards`
   equal to the native `t_*` list from mint, then end the turn (a later
   nudge to finish is already satisfied; never answer it with `kanban_complete`).

After an Operator unblock, re-run the road from step 1. The terminal gate
that says "needle admit-migration-plan last exited non-zero" clears when
that step runs again in order; it is not asking you to run step 4 first.
Step 5 needs no `--exempt` flags: the dest-init cards (M1, this M2) are
registered from `.hermes/AUTOSTART-STATUS` and K3 exempts them itself.

From here the loop propagates itself: each M3 card's `advance.py` mints
the next card after the tools accept its step.

## Self-test

`python3 scripts/selftest.py` (golden only, never on a card): steps.json ↔ audit.json sync, gate first, fixture PASS/REFUSE set, and the paved-road coverage lint.

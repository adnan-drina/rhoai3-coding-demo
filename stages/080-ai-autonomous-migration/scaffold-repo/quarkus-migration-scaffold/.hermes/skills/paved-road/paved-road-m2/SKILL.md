---
name: paved-road-m2
description: >
  Pin only this on the M2 PLAN card. Index for the planning step: the
  activation gate (native), the deterministic bootstrap
  (bootstrap-destination), the plan = tool-computed work list plus baseline
  (build-worklist), admission (admit-migration-plan, the producer), then
  publication through kernel k4_mint.py and the live-board comparison
  (verify-live-kanban-loop). On an outcome-board/v2 run (the default for new
  runs) publication puts the whole known plan on the board as native cards
  under this open card; on a serial-loop/v1 run it mints the one head card.
  No LLM plans. INCONCLUSIVE admission is a legal stop (kanban_block).
  Never for story implementation.
license: Apache-2.0
compatibility: Linux seat; Hermes v0.20.5 Kanban; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "4.0.0"
  hermes:
    tags:
    - paved-road
    - m2
    category: paved-road
    kind: guidance
---
# Paved road: M2 PLAN (activation gate → bootstrap → work list → admission → publish → read back)

`steps.json` is the contract; `audit.json` is generated from it
(`python3 .hermes/lib/paved_road.py generate --steps steps.json --out audit.json`).
The reviewer runs `python3 .hermes/skills/paved-road/paved-road-m2/scripts/assert-paved-road-audit.py --root /projects/modernized "$HERMES_KANBAN_TASK"` over the official Kanban log (`$HERMES_HOME/kanban/logs/<id>.log`). Do not pass `--log` unless that file exists; a workshop path such as `/projects/modernized/kanban/logs/` is not the official log (v9 M2 `t_77e1fdac`). Silence, a missing KEEP file, or an unmatched `[exit 1]` refuses.

The card body names the run's protocol: `Procedure: paved-road-m2 (outcome-board/v2)`
or `(serial-loop/v1)`. The protocol was selected when the run was created;
nothing here changes it. Steps 1–4 and 7 are the same for both.

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
   — publishes the admitted plan (nothing without an ADMITTED receipt):
   - **outcome-board/v2:** every known repair outcome, M4 and the three M5
     stages become native cards under this open card, each with its
     `contract.json`; the plan revision is attached to this card as
     `plan.r1.json`. M3 depends on this card, M4 on every outcome, M5 on M4,
     so nothing runs until this card is done. The command prints the
     `created_cards` list. A crash mid-publication resumes with the same
     command and creates nothing twice.
     When `decisions.yaml` selects `loop.compatibility_objectives: v1` (the
     run's initial commit pins it), a card can be a **compatibility
     objective**: several work-list units that share one concrete repair,
     each selected repository contract, or one request boundary. Its contract
     lists the constituents, each check's stage (`immediate` judged at the
     card; `later` still owed by it, with the earliest point it can be
     measured and M4 as the backstop), each check's verification
     prerequisites and the implementation prerequisites that must finish
     first (check-schedule/v1). Its budget is the summed family of the units
     it joined, so the run's total is unchanged. You neither choose nor
     change the grouping. An `OBJECTIVES_*` or `PLAN_SCHEDULE` admission
     block is a decision for a human, like any other BLOCK class.
   - **serial-loop/v1:** mints exactly one card, the head cluster (or M4
     VERIFY when the list is empty). From then on each accepted M3 step
     mints the next card (`advance.py`); `pipeline.admit` also writes the
     derived `evidence/planning/serial-roadmap.json`, a view and never a gate.
5a. `python3 .hermes/kernel/handoff_facts.py --root /projects/modernized --phase m2 --write`
   (KEEP `evidence/handoff/m2-facts.json`): the handoff's numbers, computed
   from the published plan (the newest `plan.r<N>.json` on this card; the
   frozen `plan-semantics.json` when the protocol publishes no revision) —
   repair outcomes versus milestones, requirement counts, and the unresolved
   verification responsibilities, bound to the admission receipt the plan was
   published under.
6. `skill_view verify-live-kanban-loop` → run its script (KEEP
   `evidence/receipts/k3/live-board.json`):
   - **outcome-board/v2:** the live board equals the published plan revision
     (keys, bodies, dependencies, contracts; the same read-back as
     `python3 .hermes/kernel/native_gate.py --root . readback`).
   - **serial-loop/v1:** the live board equals the loop's expected cards.
7. Hand off for review (below), then end the turn. A later nudge to finish is
   already satisfied; never answer it with `kanban_complete` (K2 refuses it
   for the implementer). On v2, K2 allows the review request and the
   reviewer's completion only while the read-back is empty.

After an Operator unblock, re-run the road from step 1. The terminal gate
that says "needle admit-migration-plan last exited non-zero" clears when
that step runs again in order; it is not asking you to run step 4 first.
Step 5 needs no `--exempt` flags: the dest-init cards (M1, this M2) are
registered from `.hermes/AUTOSTART-STATUS`.

## Review handoff

`kanban_request_review` with `reviewer=reviewer` and:

- `summary` — two or three sentences a person can act on: the admission
  verdict, how many cards were published (v2: outcomes, M4, M5; serial: the
  head card) and any unresolved responsibility or BLOCK class the plan
  carries.
- `metadata` — `created_cards` (the native `t_*` list the publication
  printed; never empty after a publication), `admission`
  (`evidence/planning/admission-receipt.json` and its verdict),
  `plan_revision` (v2: 1), `read_back` (v2: `[]`, or the receipt path),
  `limitations` (what this plan does not cover yet, e.g. coverage gaps
  inherited from M1), and **verbatim** the `facts`, `factual_summary` and
  `unresolved` (the exact unresolved ID set) that step 5a printed.

Take every count from the facts; the narrative explains, never restates. Repair outcomes and milestones are
separate numbers (v23: 30 repair outcomes plus 4 milestones = 34 cards, which
M2 reported as "29 outcomes"). Admission blocks and unresolved rows are
different things: a block refuses the plan; an unresolved row is an admitted
release qualification (`blocks: ship`) that stays open until evidence closes
it, so `unresolved` is never `[]` while the plan keeps one (v23: 7 groups
spanning 12 HTTP entry points).

The reviewer checks these against the attached plan and the board and runs
the audit. Under the reviewer profile the audit compares the current handoff
(the latest implementer run) with the facts recomputed from the published
plan: missing or different facts, or an unresolved ID set with a missing,
extra, duplicate or foreign ID, is a red audit, and the reviewer requests
changes instead of completing.

## Legacy protocol: outcome-board/v1

Retired for new runs; kept only for a run that selected it. Step 5 publishes
the graph under this open M2 with the M5 stages unassigned until the
continuation grants them; the review request is allowed only when the
whole-graph read-back is green.

## Self-test

`python3 scripts/selftest.py` (golden only, never on a card): steps.json ↔ audit.json sync, gate first, fixture PASS/REFUSE set, and the paved-road coverage lint.

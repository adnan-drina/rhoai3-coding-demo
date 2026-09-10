---
name: paved-road-m1
description: >
  Use at M1 ANALYZE as the kind index. Pin only --skill paved-road-m1.
  Follow steps.json in order (skill_view subskills; native
  kanban_attach.py): freeze the original source, capture build evidence,
  JDK-model inventory, optional bytecode enrichment, Spring context probe, MTA
  8.2 scan, then assemble evidence-bundle.json. Happy-path terminator is
  kanban_request_review, not kanban_complete. kanban_block for
  external/platform failures (MaaS 500, missing key, GPU) and for an
  unpinned mandatory tool. Do not pin the producer leaves on the card. Do
  not use for M2 PLAN, M3, or M4.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; Java 21; Maven; Hermes Kanban
metadata:
  author: rhoai3-harness-team
  version: "2.0.0"
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
`skill_view` from the step list. Producer of artifact `m1-analyze` is
`assemble-evidence-bundle` (`evidence/planning/evidence-bundle.json`),
the root of the planner digest chain (SAD §6).

## When to Use

- This card is **M1 ANALYZE**.
- **Not** M2 PLAN (`paved-road-m2`).
- **Not** dest-init mint (`dispatch-phase`).

## Procedure

1. Read `steps.json`. Follow that listed order:
   freeze → build → JDK-model inventory → bytecode (optional) → context probe
   → MTA → assemble → attach.
   - `skill` — `skill_view` that leaf and follow its SKILL.md.
   - `native` — run the named script under `.hermes/kernel/`
     (`kanban_attach.py --task "$HERMES_KANBAN_TASK" --exec`).
2. KEEP paths on the step must exist under the workspace root.
3. A producer that records `status: unpinned` (structure extractor) or a build that
   records `outcome: failure` is **evidence**, not a defect to repair.
   extractor unpinned / JDK mismatch → `kanban_block` (kind `needs_input`, the pin is an
   ADR). Build failure → continue; the ledger makes it planning-only.
4. `bash .hermes/skills/harness/dispatch-phase/scripts/autostart-migration.sh --root /projects/modernized`
   — binds the platform-recorded pilot authorization (dest-init wrote who
   authorized this run from the DevWorkspace its creator started) to the
   bundle you just produced, and mints M2. It decides nothing: an unbound
   seal with no named authorizer, one already bound, one not recorded by the
   platform, or an unfit bundle are all refused, and admission still gates
   the plan. Mints nothing under a not-activated planner; idempotent.
5. Happy-path terminator: `kanban_request_review` (reviewer `reviewer`), then end the turn. A later nudge to finish is already satisfied by the review handoff; do not answer it with `kanban_complete` (K2 refuses it for the implementer) or `kanban_block`.
6. `kanban_block` for external/platform (MaaS 500, missing key, GPU).
7. Reviewer runs `scripts/assert-paved-road-audit.py --log <official> --root <ws>`.
   `--log` must be `kanban/logs/t_*.log` (or a land-time `fixtures/**/official.log`).

## Gotchas

- Silence fails. An unmatched `[exit 1]` on a mandated needle fails.
  A later clean invocation of the *same* needle clears an earlier red.
  Do not last-wins across different needles.
- `inventory-legacy-surface` precedes `scan-with-mta`: the MTA handoff
  refuses (AR-4.1) without `evidence/entry-point-inventory.json`.
- `derive-legacy-boot3` is **not** an M1 step. The baseline is the
  frozen original source; a Boot 3 derivation is an execution-side
  transformation only.
- Path mention / grep / cat of a SKILL.md is not `skill_view`.
- Do not `kanban daemon --force`.

## Self-test

`python3 scripts/selftest.py` (golden only, never on a card): steps.json ↔ audit.json sync, order contract, fixture PASS/REFUSE set, and the paved-road coverage lint.

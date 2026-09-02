---
name: paved-road-m2
description: >
  Use at M2 PLAN as the kind index. Pin only --skill paved-road-m2.
  Follow steps.json in order (skill_view speckit-specify then plan/tasks,
  plan-migration-partition producer, check-spec-readiness, native
  check-partition-coverage.py and assert-m2-speckit-conformance.py,
  k4_convert.py, k4_mint.py). Happy-path terminator is kanban_request_review,
  not kanban_complete. kanban_block for external/platform (MaaS 500, missing
  key, GPU). Do not pin plan-migration-partition and check-spec-readiness
  on the card. Do not use for M1, M3, or M4.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; Hermes Kanban; pinned specify-cli
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - paved-road
    - m2
    category: paved-road
    kind: guidance
---
# M2 PLAN paved-road (index)

This skill is the **M2 procedure index**. Ordered mandated steps live in
`steps.json`. `audit.json` is generated from that file — do not edit it
by hand. Do not copy subskill SKILL.md bodies into this file.

Pin **only** this leaf (`--skill paved-road-m2`). Subskills load via
`skill_view` from the step list. Spec Kit hermes integration installs
`files: {}` — follow Hermes `speckit-specify` then plan/tasks; do not
`specify workflow run speckit`.

## When to Use

- This card is **M2 PLAN**.
- **Not** M1 ANALYZE (`paved-road-m1`).
- **Not** dest-init mint (`dispatch-phase`).

## Procedure

1. Read `steps.json`. For each step in order:
   - `skill` — `skill_view` that leaf and follow its SKILL.md. Do not
     treat a `$` line under that skill's `scripts/` as the skill step.
   - `kernel` — run the named basename under `.hermes/kernel/`.
   - `native` — run the named script basename (M2:
     `check-partition-coverage.py`, `assert-m2-speckit-conformance.py`).
2. KEEP paths on the step must exist (`evidence/partition.json` on the producer).
3. Happy-path terminator: `kanban_request_review` (not `kanban_complete`).
4. `kanban_block` for external/platform (MaaS 500, missing key, GPU).
5. Reviewer runs `scripts/assert-paved-road-audit.py --log <official> --root <ws>`.
   Land-time `scripts/selftest.py` is not dest.

Producer of artifact `m2-partition` is the `plan-migration-partition` step.
Paved-road itself is the index, not a second producer.

## Gotchas

- Silence fails. An unmatched `[exit 1]` on a mandated needle fails.
  A later clean invocation of the *same* needle clears an earlier red.
  Do not last-wins across different needles (dest-14 `bound_gate_red` hole).
  Do not slice the audit to the last `Query: work kanban task` marker
  (that is the reviewer session).
- Skill needles match `skill_view` only. Kernel/native needles are a
  script basename with a path boundary, not a parent directory.
- `workflow-run.json` is forgeable and is not proof.
- Path mention / grep / cat of a SKILL.md is not `skill_view`.
- If a named speckit skill is missing: `kanban_block`. Do not hand-author
  `tasks.md`.
- Do not `kanban daemon --force`. Do not dest-apply dest-14.

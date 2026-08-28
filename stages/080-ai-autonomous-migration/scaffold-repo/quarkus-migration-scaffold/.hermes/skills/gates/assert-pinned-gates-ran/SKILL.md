---
name: assert-pinned-gates-ran
description: >
  Use before writing M4 PROVISIONAL_ACCEPT — refuse unless every gate skill
  pinned on the M4 card has a runner receipt under evidence/receipts/gates/
  with argv, rc, and producer. ran true under evidence/verdicts/, a missing
  receipt, or M4 write_file of the receipt path is not a run. Silence fails.
  Do not idle-exit-0 on missing artifacts. Do not use for domain measurement
  (check-domain-parity) or M4 body/surefire lint (check-release-readiness).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; git not required
metadata:
  author: rhoai3-harness-team
  version: "1.2.0"
  hermes:
    tags:
    - gates
    - m4
    category: gates
    kind: guidance
---
# Pinned gates must have run

Architect `142524ZA`. Operator `162349ZO`: dest-5 M4 minted
`refusals/check-domain-parity.json` with `"ran": false` and this gate
accepted it. Run **before** writing `PROVISIONAL_ACCEPT`.

## When to Use

- M4 is about to write `evidence/verdicts/` with `PROVISIONAL_ACCEPT`.
- A gate is on the M4 card `skills` list (`check-spec-readiness`,
  `check-domain-parity`, `check-release-readiness`, this skill,
  `assert-retrievable-tree`).
- **Not** to invent Owner/Pet, kill-ratio, or DB floors. **Not** idle-pass
  when artifacts are missing.

## Procedure

Pass the M4 card's skills list. Missing list is fail-closed.

```bash
python3 "${HERMES_SKILL_DIR}/../assert-retrievable-tree/scripts/assert-retrievable-tree.py" \
  /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/assert-pinned-gates-ran.py" /projects/modernized \
  --skills "check-spec-readiness,check-domain-parity,check-release-readiness,assert-pinned-gates-ran,assert-retrievable-tree"
```

`--skills-file` or `--card-json` (object with `skills`) are equivalents.
Env `M4_CARD_SKILLS` is OBJECT (Architect `130758ZA` dest-8 override). `--card-id` /
`HERMES_KANBAN_TASK` rejects artifacts that name this M4 task.

For each pinned gate leaf: require a JSON under `evidence/receipts/gates/`
that names it **and** carries `cmd`, `argv`, `rc`, `input_digest`,
`producer` (not `compose-m4-verdict`). `ran: true` under
`evidence/verdicts/` is self-attested and is **not** a run. M4
`write_file` of `evidence/receipts/gates/` is fenced.

This script does not write `PROVISIONAL_ACCEPT`. On pass, if this leaf is
pinned, it writes `evidence/receipts/gates/assert-pinned-gates-ran.json`
so its own pin is evidenced. Pinned-gate runners import
`scripts/script_gate_receipt.py` for that write.

## Pitfalls

- Reading a missing `evidence/verdicts/` tree as skip.
- Treating `"ran": false` plus a reason as evidence the gate ran.
- Minting PASS JSON under `evidence/verdicts/` on the M4 card to green this gate.
- M4 `write_file` of `evidence/receipts/gates/` (fence REFUSE; runners write).
- Running this before `assert-retrievable-tree` when that leaf is also pinned.

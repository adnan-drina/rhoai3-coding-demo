---
name: compose-m4-verdict
description: >
  Use at M4 VERIFY to compose evidence/verdicts/m4-verdict.json from
  measured floor exit codes, including an explicit failed_floors field.
  Use when writing the M4 verdict or creating the M4 card, even if the
  user does not name a schema. Do not record a failed floor as idle.
  Do not use only to lint an already-written verdict
  (check-release-readiness, check-domain-parity).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; Hermes Kanban
metadata:
  author: rhoai3-harness-team
  version: "1.1.0"
  hermes:
    tags:
    - gates
    - m4
    category: gates
    kind: guidance
---
# Compose the M4 verdict (M4 producer)

This skill **owns `evidence/verdicts/m4-verdict.json`**. It **consumes**
`evidence/receipts/gates/` (argv, rc, producer). It does **not** author
those receipts. Pin it on the M4 card (`--skill compose-m4-verdict`).
Checkers lint the verdict file; they do not author receipts. dest-8
invented a shape with no slot for a failed floor and called AR-2.8
`"idle"` (Operator `130951ZO` / `143706ZO`).

Schema: `references/m4-verdict-schema.md`. Keep it in sync with
`scripts/assert-m4-verdict-schema.py` via
`scripts/assert-m4-verdict-schema-sync.py`.

## When to Use

- This card is **M4 VERIFY**.
- `evidence/verdicts/m4-verdict.json` does not exist yet, or floors were
  re-measured.
- **Not** routing/token lint alone (`check-release-readiness`).
- **Not** G-1..G-4 measurement (`check-domain-parity`).

## Pin the M4 card

Create (or remint) M4 with this leaf first:

```bash
hermes kanban create "M4 VERIFY" \
  --assignee implementer \
  --parent "$STAMP_TASK_ID" \
  --skill compose-m4-verdict \
  --skill check-release-readiness \
  --skill check-domain-parity \
  --workspace dir:/projects/modernized \
  --max-retries 1 \
  --max-runtime 2h \
  --idempotency-key m4-verify
```

`k4_mint.py --exec` repeats `--parent` for every M3 story it just created
(not only STAMP). Title is positional (`hermes kanban create "M4 VERIFY"`);
`--title` is not a flag. Do not put a verdict token in the create body.

Do not pin only the two `check-*` leaves.

## Procedure

Root is `/projects/modernized`. Record each floor's **measured** exit
code. Do not re-run a floor to invent `idle`.

1. Pre-verdict (fail-closed; not idle). The runner **runs the pinned
   feeding gates first** (`check-partition-coverage`, `check-product-tests`,
   `check-test-toolchain` with `--write-receipt` into
   `evidence/receipts/gates/`) and only then `assert-pinned-gates-ran`.
   Do not invoke pre-verdict before those gates — dest-14 REFUSEd an empty
   receipts dir even after the floors had run later in the card.

```bash
bash .hermes/skills/gates/check-release-readiness/scripts/run-m4-pre-verdict.sh \
  /projects/modernized
```

2. Completion floors. Write down `rc` for each. `idle: true` is legal
   **only** when that floor's trigger artifact is absent **and** `rc` is
   0. A non-zero `rc` is a **failed floor**, never idle.

```bash
python3 .hermes/skills/gates/check-release-readiness/scripts/check-runnable-db-config.py \
  /projects/modernized
python3 .hermes/skills/gates/check-release-readiness/scripts/check-empty-security.py \
  /projects/modernized
python3 .hermes/skills/gates/check-release-readiness/scripts/check-test-toolchain.py \
  /projects/modernized
python3 .hermes/skills/gates/check-domain-parity/scripts/check-product-tests.py \
  /projects/modernized
```

3. Author `evidence/verdicts/m4-verdict.json` from those rcs. Required
   field **`failed_floors`**: the list of floor names whose `rc != 0`
   (`[]` if none). Do not omit it. Do not put a failed name in a reason
   string as `"idle"`.

   If `failed_floors` is non-empty, `verdict` is `REFUSE` (not
   `PROVISIONAL_ACCEPT`). `ship` stays `false`. M4 never ships.

4. Lint (this skill does not replace these checkers):

```bash
python3 "${HERMES_SKILL_DIR}/scripts/assert-m4-verdict-schema.py" \
  /projects/modernized/evidence/verdicts/m4-verdict.json
python3 .hermes/skills/gates/check-release-readiness/scripts/assert-m4-complete-around-red.py \
  --verdict /projects/modernized/evidence/verdicts/m4-verdict.json \
  --floor-rc "$PRODUCT_TESTS_RC"
python3 .hermes/skills/gates/check-release-readiness/scripts/check-verdict-routing.py \
  /projects/modernized
```

Pass `--floor-rc` as the **measured** AR-2.8 rc. Do not pass 0 because
the reason said idle.

`kanban_complete` only after schema PASS. Non-empty `failed_floors` is
`kanban_block` (or complete with `verdict: REFUSE` if the card's exit
allows it) — never `PROVISIONAL_ACCEPT`. Do not `kanban daemon --force`.
Do not dest-dispatch M5.

## Pitfalls

- Pinning only `check-release-readiness` + `check-domain-parity` (dest-8
  M4). Those skills consume a verdict; they do not own its fields.
- Calling a failed floor `"idle"` because no schema named `failed_floors`.
- Authoring `evidence/receipts/gates/` from M4 `write_file` (fence REFUSE).
- Treating checker idle-exit-0 (artifact absent) as a pass for a floor
  that actually exited 1.

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

M4 VERIFY is minted by `python3 .hermes/kernel/k4_mint.py --root . --exec`
(called by `fix-until-green/scripts/advance.py` after the accepted step
that emptied the work list) from the ADMITTED admission receipt: card
`M4_VERIFY` (kind `close`), parent = the last accepted loop card, skills
from `planner.cards.CARD_SKILLS["close"]` (this leaf first), idempotency
key `k4:M4_VERIFY:<attempt>:<receipt_digest[:16]>`. There is no fixed
`m4-verify` key and no hand `hermes kanban create` for M4: a receipt
re-admitted with a new digest mints a new M4, and K4 mints nothing while
a deferred (manual) cluster is open.
Title is positional; `--title` is not a flag. Do not put a verdict token in
the body.

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

   AR-2.8 (`check-product-tests.py`) measures product tests by **execution**
   and by the capabilities the evidence declares (ADR-015): a source under
   `src/test/java` outside the harness probe package whose class an execution
   record names with the case neither skipped nor failed nor errored, and the
   declared scenario capabilities — the scenarios of
   `verification/scenarios/corpus.json` qualified `PASS` in
   `verification/source-oracles/scenarios/_qualification.json` — covered by a
   cleanly executed case of `evidence/tests/generated-manifest.json` or by a
   retained case that names the scenario. Its rc 2 means evidence that exists
   and cannot be read; record that as a failed floor, never as idle. A named
   capability GAP is not a pass either: copy it into the verdict.

3. Author `evidence/verdicts/m4-verdict.json` from those rcs. Required
   field **`failed_floors`**: the list of floor names whose `rc != 0`
   (`[]` if none). Do not omit it. Do not put a failed name in a reason
   string as `"idle"`.

   If `failed_floors` is non-empty, `verdict` is `REFUSE` (not
   `PROVISIONAL_ACCEPT`). `ship` stays `false`. M4 never ships.

   Template — the measured part is yours, the three bindings are not:

```json
{
  "gate": "M4_VERDICT",
  "phase": "M4",
  "ran": true,
  "verdict": "REFUSE",
  "ship": false,
  "failed_floors": ["check-empty-security", "check-product-tests"],
  "floors": [{"name": "check-empty-security", "rc": 1, "idle": false}],
  "coverage_account": {"retired": 0, "remaining_gaps": 0},
  "card_id": "<issued close card>",
  "receipt_sha256": "<admission receipt it was minted under>",
  "parity_receipt_sha256": "<digest of the parity receipt you judged>",
  "reason": "..."
}
```

3a. Bind the verdict to its card and its evidence. Do this with the tool, not
   from memory — the three values are facts of the tree, and v9's second M4
   card composed an honest REFUSE with no `card_id` at all, which left
   `resume-after-m4.py` with a measurement it could not attribute to a run.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/bind-m4-verdict.py" --root /projects/modernized
```

   It writes `card_id`, `receipt_sha256` and `parity_receipt_sha256` and
   touches nothing a floor measured. If you are writing the JSON by hand,
   these are the commands that print those three values (run from
   `/projects/modernized`); copy what they print:

```bash
python3 -c 'import json;print(json.load(open("verification/loop/issued.json"))["task_id"])'
python3 -c 'import json;print(json.load(open("verification/loop/issued.json"))["receipt_sha256"])'
python3 -c 'import hashlib;print(hashlib.sha256(open("verification/parity/receipt.json","rb").read()).hexdigest())'
```

   The binder also RECORDS the verdict as bound —
   `evidence/verdicts/m4-verdict.bound.json`: the digest of the verdict file,
   a copy of it, the three bindings. From then on the bound verdict is the
   verdict. Do not revise it in place: a bound verdict whose digest no longer
   matches the record was edited after binding (v9's t_caf2ad51 revised a
   bound `PROVISIONAL_ACCEPT` into a `REFUSE` with `card_id ""` by hand), and
   the binder, the lint and `resume-after-m4.py` each refuse it naming the
   fields that differ. A new measurement is a NEW verdict without bindings —
   compose it, bind it; the superseded binding stays on the record with its
   verdict copy, so the audit reads every verdict this card bound, in order.
   Typing the three values by hand leaves no record, and a verdict without
   the record is refused as bound by hand.

   `assert-m4-verdict-schema.py` (step 4) is the gate: it refuses
   `M4_VERDICT_BINDING` when one of the three is missing, names another card,
   names an admission receipt the card was not minted under, names a parity
   receipt digest this tree does not hold, has no binding record, or no
   longer digests to it. `resume-after-m4.py` binds on the same three and
   the same record.

3b. Compose the coverage account. What the accepted ADRs retired must be
   accounted for here, per file, or M4 reports on a destination whose missing
   behaviour nobody named.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/compose-coverage-account.py" \
  /projects/modernized
```

   It reads `decisions.yaml` and `verification/parity/receipt.json`: each
   retired source becomes a row with its ADR, why it was retired, the
   replacement scenarios the decision names (`replaced_by`), the verdict each
   of those scenarios measured, and the remaining gap when there is one. A
   retired **test** source is replaced only beside fresh executed-test
   evidence. Copy `summary.retired` and `summary.remaining_gaps` into the
   verdict's required `coverage_account`. Do not hand-write the account: the
   lint recomputes it and refuses a copy that disagrees. A remaining gap is
   legal (an accepted ADR may knowingly drop coverage) and hiding one is not.

4. Lint (this skill does not replace these checkers):

```bash
python3 "${HERMES_SKILL_DIR}/scripts/assert-m4-verdict-schema.py" \
  /projects/modernized/evidence/verdicts/m4-verdict.json
python3 .hermes/skills/gates/check-release-readiness/scripts/assert-m4-complete-around-red.py \
  --verdict /projects/modernized/evidence/verdicts/m4-verdict.json \
  --floor-rc "$PRODUCT_TESTS_RC"
python3 .hermes/skills/gates/check-release-readiness/scripts/check-verdict-routing.py \
  /projects/modernized
python3 .hermes/skills/gates/check-release-readiness/scripts/assert-coverage-account.py \
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
- Writing `coverage_account` counts by hand, or reporting fewer gaps than
  the account holds. Both refuse.
- Authoring the verdict without its bindings, or typing a `card_id` you
  remember from an earlier card. The binding is read from
  `verification/loop/issued.json` and the parity receipt by
  `bind-m4-verdict.py`; a verdict that names no card is a verdict for no run.
- Reading a retired test's coverage as replaced because an endpoint answers:
  a replacement is a scenario the decision **names** and the parity receipt
  measured as PASS.

# M4 verdict schema (M4 producer reference)

**Authoritative parser is** `scripts/assert-m4-verdict-schema.py`. This
page names the fields a worker must write.
`scripts/assert-m4-verdict-schema-sync.py` fails if a required field
below disappears from either side.

Do **not** invent extra routing tokens here (`check-verdict-routing.py`
owns ship/routing legality). Do **not** treat
`check-release-readiness` as the producer.

## File

Write `evidence/verdicts/m4-verdict.json`. One object.

## Top-level keys

| Key | Rule |
|-----|------|
| `gate` | `M4_VERDICT` |
| `phase` | `M4` |
| `ran` | `true` when floors were measured |
| `verdict` | `PROVISIONAL_ACCEPT` only when `failed_floors` is empty; otherwise `REFUSE` (or another non-ACCEPT token). Never `ACCEPT` at M4. |
| `ship` | `false` at M4 |
| `failed_floors` | **required.** List of floor `name`s whose measured `rc != 0`. `[]` if none failed. This is the failed-floor field dest-8 lacked. |
| `floors` | non-empty array of floor objects (see below) |
| `coverage_account` | **required.** `{retired: int, remaining_gaps: int}`, equal to the summary of `evidence/verdicts/coverage-account.json`. What the accepted ADRs retired, and how much of it nothing yet covers. A gap is legal and must be visible; a verdict that under-reports one refuses (`assert-coverage-account.py`). |
| `card_id` | **required.** The issued M4 close card (`task_id` of `verification/loop/issued.json`, `t_*`). Written by `bind-m4-verdict.py`, never from memory. |
| `receipt_sha256` | **required.** The admission receipt that card was minted under — `receipt_sha256` of the same `verification/loop/issued.json`. |
| `parity_receipt_sha256` | **required.** The SHA-256 of `verification/parity/receipt.json` itself: the parity evidence this verdict judged. |

Optional: `reason` (must not call a failed floor idle).

## The three bindings

The binder records the verdict as bound in `evidence/verdicts/m4-verdict.bound.json`
(`rhoai3.m4-verdict-binding/v1`: `verdict_sha256` of the file as written, a
`verdict` copy, the three bindings, `bound_at`, and `superseded` — every earlier
binding of this card, with its verdict copy). The lint and `resume-after-m4.py`
refuse a verdict with no record, or one whose digest differs from it (edited
after binding); the binder refuses to re-bind such a verdict. A new
composition is a verdict without bindings; binding it supersedes the record.

A verdict is the answer of one card, measured over one tree, judging one
parity receipt. Those three facts are read from artifacts, so a tool writes
them:

```bash
python3 .hermes/skills/gates/compose-m4-verdict/scripts/bind-m4-verdict.py --root .
```

It changes nothing a floor measured. Run it right after authoring the verdict.
If you are writing the JSON by hand, these are the commands that print the
three values — copy what they print, never what you remember:

```bash
python3 -c 'import json;print(json.load(open("verification/loop/issued.json"))["task_id"])'
python3 -c 'import json;print(json.load(open("verification/loop/issued.json"))["receipt_sha256"])'
python3 -c 'import hashlib;print(hashlib.sha256(open("verification/parity/receipt.json","rb").read()).hexdigest())'
```

`M4_VERDICT_BINDING` refuses a verdict that omits one of the three, names
another card, names an admission receipt the card was not minted under, or
names a parity receipt digest this tree does not hold. v9's second M4 card is
the control: it composed an honest `REFUSE` with no `card_id`, nothing refused
it, and `resume-after-m4.py` could not attribute the measurement to a run.

## Each `floors[]` object

| Key | Rule |
|-----|------|
| `name` | floor script stem (`check-product-tests`, `check-runnable-db-config`, …) |
| `rc` | measured exit code (int) |
| `idle` | `true` **only** when the floor did not apply (trigger artifact absent) **and** `rc` is 0. `idle` MUST be `false` when `rc != 0`. |

## Codes this authoring must not trip

`M4_VERDICT_SCHEMA` `FAILED_FLOOR_AS_IDLE` `ACCEPT_WITH_FAILED_FLOOR`

`FAILED_FLOOR_AS_IDLE`: a floor with `rc != 0` recorded `idle: true`, or
its `name` is in `failed_floors` while `idle` is true, or `reason`
contains `idle` for a failed floor.

`ACCEPT_WITH_FAILED_FLOOR`: `verdict` is `PROVISIONAL_ACCEPT` / `ACCEPT`
/ `SCOPED_ACCEPT` while `failed_floors` is non-empty.

`M4_VERDICT_SCHEMA`: missing required key, `failed_floors` not a list,
`floors` empty, `ship` true, `phase` not `M4`, `gate` not `M4_VERDICT`.

`M4_VERDICT_BINDING`: a missing, stale or foreign `card_id`,
`receipt_sha256` or `parity_receipt_sha256` (see *The three bindings*).

## The coverage account

`evidence/verdicts/coverage-account.json` is written by
`scripts/compose-coverage-account.py` from `decisions.yaml` and the parity
receipt: one row per retired source with its ADR, the reason it was retired,
the replacement scenarios the decision names (`replaced_by`), the verdict each
of those scenarios actually measured, and the remaining gap when there is one.
A retired **test** source counts as replaced only beside fresh executed-test
evidence. Do not hand-write this file; the lint recomputes it from the same
inputs and refuses a copy that disagrees.

Each `replacement_measured` row also carries `coverage` — how the parity
receipt covered that entry point: `oracle` (the single-request replay of a
method and a path), `scenario` (a qualified scenario that explicitly binds it,
whose destination replay passed; the ids are in `covered_by_scenarios`), or
empty for neither. `entry_point_coverage` mirrors the receipt's own three-way
count. Coverage is not credit: a replacement claim still needs the entry point
measured PASS, and an entry point no scenario binds stays a gap however many
other scenarios pass (architect ruling, 2026-09-22).

## After authoring

```bash
python3 .hermes/skills/gates/compose-m4-verdict/scripts/compose-coverage-account.py \
  /projects/modernized
python3 .hermes/skills/gates/compose-m4-verdict/scripts/bind-m4-verdict.py --root .
python3 .hermes/skills/gates/compose-m4-verdict/scripts/assert-m4-verdict-schema.py \
  evidence/verdicts/m4-verdict.json
python3 .hermes/skills/gates/check-release-readiness/scripts/assert-coverage-account.py \
  /projects/modernized
```

Routing lint remains `check-verdict-routing.py`. Complete-around-red
remains `assert-m4-complete-around-red.py --floor-rc <measured>`.

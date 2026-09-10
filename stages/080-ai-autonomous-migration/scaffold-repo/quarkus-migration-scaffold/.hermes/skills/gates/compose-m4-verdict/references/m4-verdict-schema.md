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

Optional: `card_id` (`t_*`), `reason` (must not call a failed floor idle).

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

## The coverage account

`evidence/verdicts/coverage-account.json` is written by
`scripts/compose-coverage-account.py` from `decisions.yaml` and the parity
receipt: one row per retired source with its ADR, the reason it was retired,
the replacement scenarios the decision names (`replaced_by`), the verdict each
of those scenarios actually measured, and the remaining gap when there is one.
A retired **test** source counts as replaced only beside fresh executed-test
evidence. Do not hand-write this file; the lint recomputes it from the same
inputs and refuses a copy that disagrees.

## After authoring

```bash
python3 .hermes/skills/gates/compose-m4-verdict/scripts/compose-coverage-account.py \
  /projects/modernized
python3 .hermes/skills/gates/compose-m4-verdict/scripts/assert-m4-verdict-schema.py \
  evidence/verdicts/m4-verdict.json
python3 .hermes/skills/gates/check-release-readiness/scripts/assert-coverage-account.py \
  /projects/modernized
```

Routing lint remains `check-verdict-routing.py`. Complete-around-red
remains `assert-m4-complete-around-red.py --floor-rc <measured>`.

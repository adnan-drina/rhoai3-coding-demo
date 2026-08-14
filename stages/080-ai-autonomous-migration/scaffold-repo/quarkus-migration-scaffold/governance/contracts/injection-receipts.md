# Injection receipts (F2)

**Status:** binding proving-min
**Authority:** Deputy M2 content review F2 / Lead land E-20260814T115900Z
**Lint:** `.hermes/skills/sdd/check-spec-readiness/scripts/injection_receipt.py`

## Rule

Create-path helpers that **mutate** a typed M3 body (`--inject`, `--write`, or
equivalent silent rewrite) **MUST** stamp an injection receipt before returning
success.

The nursing pattern (gate fails → write content → gate passes) remains allowed
at mint time, but it is no longer invisible. Agents that copy silent body rewrite
mid-run have no sanctioned precedent.

## Receipt

| Field | Required | Meaning |
|-------|----------|---------|
| `schema` | yes | `rhoai3.injection-receipt/v1` |
| `ts` | yes | UTC ISO-8601 |
| `script` | yes | basename of the mutating helper |
| `source` | yes | human-readable provenance of the injected content |
| `target` | yes | body path relative to workspace root |
| `fields_written` | yes | list of top-level body keys mutated |
| `story_id` | yes when known | from body identity |
| `summary` | yes | one-line what changed |

Path: `evidence/receipts/injections/<story_id>-<script-stem>.json`
plus `evidence/receipts/injections/latest.json` pointer.

## Wired callers

- `assert-mint-constraints-complete.py --inject`
- `stamp-body-dependencies.py --write`
- `stamp-destination-inventory.py --write`

## Not an excuse for mid-run body rewrite

Receipts cover **create-path** mutations only. Mid-run typed-body rewrite remains
REFUSE under `body-immutability.md` / AR-4.3 digest match.

```bash
python3 .hermes/skills/sdd/check-spec-readiness/scripts/injection_receipt.py \
  --root . --script assert-mint-constraints-complete.py \
  --target evidence/bodies/m3-s-001.json \
  --fields constraints \
  --source "standard_constraints(operand_class=build_config)"
```

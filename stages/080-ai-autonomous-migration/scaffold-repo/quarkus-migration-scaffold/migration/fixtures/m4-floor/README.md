# M4 floor receipt fixtures

```bash
python3 .hermes/skills/gates/validation-release-gates/scripts/check-m4-floor-receipts.py \
  migration/fixtures/m4-floor/known-good   # expect OK
python3 .hermes/skills/gates/validation-release-gates/scripts/check-m4-floor-receipts.py \
  migration/fixtures/m4-floor/known-missing  # expect FAIL
```

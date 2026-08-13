# M4 floor receipt fixtures

```bash
python3 .hermes/skills/gates/check-release-readiness/scripts/check-m4-floor-receipts.py \
  governance/fixtures/m4-floor/known-good   # expect OK
python3 .hermes/skills/gates/check-release-readiness/scripts/check-m4-floor-receipts.py \
  governance/fixtures/m4-floor/known-missing  # expect FAIL
```

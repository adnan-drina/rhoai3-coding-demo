# AR-2.8 product-test fixtures

```bash
# REFUSE — harness probe only
python3 .hermes/skills/gates/check-domain-parity/scripts/check-product-tests.py \
  .hermes/skills/gates/check-domain-parity/fixtures/product-tests/ar28-probe-only

# REFUSE — security IT alone (missing boot/crud/db)
python3 .hermes/skills/gates/check-domain-parity/scripts/check-product-tests.py \
  .hermes/skills/gates/check-domain-parity/fixtures/product-tests/ar28-thin-security

# OK — all four families marked
python3 .hermes/skills/gates/check-domain-parity/scripts/check-product-tests.py \
  .hermes/skills/gates/check-domain-parity/fixtures/product-tests/ar28-good
```

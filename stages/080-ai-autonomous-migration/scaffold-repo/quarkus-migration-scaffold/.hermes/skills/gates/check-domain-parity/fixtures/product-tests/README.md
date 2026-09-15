# AR-2.8 product-test fixtures

The floor is measured, not scanned: a product test counts when a file for it
exists under `src/test/java` and an execution record names that class with the
case neither skipped nor failed; the coverage it demands is the set of scenario
capabilities the tree's own corpus and qualification declare (ADR-015).

Only one tree needs to live on disk — the harness-probe refusal, which is about
paths, not evidence. Every other decision is built from a naming scheme in
`../../scripts/check-product-tests.test.py` and asserted twice, on two specimens
that share nothing but shape; a tree pinned to one specimen's names could not
show that.

```bash
# REFUSE — harness probe package only, no product acceptance (pair AR-3.6)
python3 .hermes/skills/gates/check-domain-parity/scripts/check-product-tests.py \
  .hermes/skills/gates/check-domain-parity/fixtures/product-tests/ar28-probe-only

# the rest
python3 .hermes/skills/gates/check-domain-parity/scripts/check-product-tests.test.py
```

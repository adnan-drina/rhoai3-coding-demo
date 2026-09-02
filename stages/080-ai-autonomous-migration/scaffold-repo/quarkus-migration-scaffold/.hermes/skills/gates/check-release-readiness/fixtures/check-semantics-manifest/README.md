# Fixtures — B8 check-semantics-manifest

Contract: `.hermes/skills/gates/check-release-readiness/references/check-semantics-manifest.md`
Lint: `.hermes/skills/gates/check-release-readiness/scripts/check-semantics-manifest.py`

```bash
# Idle on empty scaffold
python3 .hermes/skills/gates/check-release-readiness/scripts/check-semantics-manifest.py .

# Negative control — narrowed smoke must not keep id endpoint_smoke
python3 .hermes/skills/gates/check-release-readiness/scripts/check-semantics-manifest.py \
  .hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/bad-endpoint-smoke-overpromise
# expect FAIL

python3 .hermes/skills/gates/check-release-readiness/scripts/check-semantics-manifest.py \
  .hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/good-endpoint-smoke-health
# expect OK

python3 .hermes/skills/gates/check-release-readiness/scripts/check-semantics-manifest.py \
  .hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/bad-boot-health-skipped-package
# expect FAIL

python3 .hermes/skills/gates/check-release-readiness/scripts/check-semantics-manifest.py \
  .hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/bad-g4-sample-as-product-closed
# expect FAIL

python3 .hermes/skills/gates/check-release-readiness/scripts/check-semantics-manifest.py \
  .hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/bad-mvn-verify-no-clean
# expect FAIL

python3 .hermes/skills/gates/check-release-readiness/scripts/check-semantics-manifest.py \
  .hermes/skills/gates/check-release-readiness/fixtures/check-semantics-manifest/bad-unit-it-zero-tests
# expect FAIL
```

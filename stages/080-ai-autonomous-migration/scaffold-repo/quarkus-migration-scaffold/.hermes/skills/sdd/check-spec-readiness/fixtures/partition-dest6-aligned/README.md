# dest-6 two-story aligned PASS

Same inventory as dest-6 (`GET /greeting`). AC HTTP tokens match
`endpoints` (`GET /greeting`, not `/api/greeting`). Setup claims
`check-test-toolchain` so us1's implicit `mvn -q test` is not waiting on
a vacuous done parent.

```bash
python3 ../../scripts/assert-partition-invented-routes.py .
python3 ../../scripts/check-partition-coverage.py .
# both exit 0
```

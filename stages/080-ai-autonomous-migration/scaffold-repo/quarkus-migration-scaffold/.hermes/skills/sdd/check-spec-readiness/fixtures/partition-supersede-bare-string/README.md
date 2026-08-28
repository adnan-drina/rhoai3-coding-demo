# TR-2b bare-string REFUSE

Same generic `com.demo` inventory as the named-set PASS fixture.
`supersedes` is a list of dest-path strings (no successor set). Coverage
must refuse with `supersede_incomplete` (empty successors) and report
**all** gaps, not the first.

HTTP stays 1:1 (`GET /api/alpha` → US1).

```bash
python3 ../../scripts/check-partition-coverage.py .
# exit != 0, PARTITION_COVERAGE: INVALID, supersede_incomplete
```

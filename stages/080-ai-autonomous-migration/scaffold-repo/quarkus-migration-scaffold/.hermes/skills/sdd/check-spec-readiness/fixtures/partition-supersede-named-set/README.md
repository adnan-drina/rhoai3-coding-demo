# TR-2b named-set PASS

Generic `com.demo` tree. Not a reconstructed petclinic dest.

`SharedService.java` is declared superseded by named successors
`AlphaService.java` + `BetaService.java`. Those two are in story
`files_writable`. The superseded path is **not** in any write-set.

HTTP stays 1:1 (`GET /api/alpha` → US1).

```bash
python3 ../../scripts/check-partition-coverage.py .
# exit 0, PARTITION_COVERAGE: VALID
```

# dest-5 T020-shaped REFUSE

Polish owns `HealthTest.java` and accepts GET `/q/health` UP. `pom.xml` is
not in this write-set (setup owns it). Coverage must refuse
`acceptance_unsatisfiable:polish:pom.xml` — the acceptance is unsatisfiable
by construction (Lead:partition-must-grant-scope-its-acceptance-needs).

HTTP stays 1:1 (`GET /api/alpha` → US1). Generic `com.demo`.

```bash
python3 ../../scripts/check-partition-coverage.py .
# exit != 0, PARTITION_COVERAGE: INVALID, acceptance_unsatisfiable:polish:pom.xml
```

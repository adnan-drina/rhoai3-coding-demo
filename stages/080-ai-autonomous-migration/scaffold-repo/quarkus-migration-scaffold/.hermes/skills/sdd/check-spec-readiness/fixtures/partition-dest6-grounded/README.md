# dest-6 two-story stale-AC REFUSE

Real dest-6 partition shape: `setup` (empty endpoints, pom/properties)
and `us1_greeting` (`GET /greeting`). Inventory has one HTTP row
`/greeting`. AC still names `GET /api/greeting` after M2 corrected the
`endpoints` field. dest `quarkus.http.root-path=/`, so `/api/greeting`
is not served (Architect `205213ZA`). Coverage must refuse the stale
prose (`stale_ac:us1_greeting:/api/greeting`). Setup's compile-only AC
leaves us1's `mvn -q test` waiting on a done parent
(`implicit_pom_parent_vacuous:us1_greeting:setup`).

```bash
python3 ../../scripts/assert-partition-invented-routes.py .
# exit 1, us1_greeting: /api/greeting
python3 ../../scripts/check-partition-coverage.py .
# exit 1, stale_ac + implicit_pom_parent_vacuous
```

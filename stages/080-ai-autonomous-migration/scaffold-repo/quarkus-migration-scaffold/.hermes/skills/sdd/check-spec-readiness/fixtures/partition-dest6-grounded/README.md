# dest-6 two-story grounded PASS

Real dest-6 partition: `setup` (empty endpoints, pom/properties only) and
`us1_greeting` (`GET /greeting`). Inventory has one HTTP row `/greeting`.
AC `GET /api/greeting` is dest REST prefix + inventory path, not invention.

```bash
python3 ../../scripts/assert-partition-invented-routes.py .
# exit 0, INVENTED_ROUTES: PASS
```

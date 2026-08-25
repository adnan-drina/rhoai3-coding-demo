# dest-5 T020 invented `/q/health` REFUSE

Real dest-5 partition (3 stories, 1 inventory HTTP row `GET /greeting`).
`T020_POLISH` writes `HealthTest.java` and accepts `GET /q/health`.
Constitution VII: that path is not in inventory. Empty `endpoints` on
T020 is not legal scaffolding because the story names an HTTP path.

```bash
python3 ../../scripts/assert-partition-invented-routes.py .
# exit != 0, invented_route:T020_POLISH:/q/health
python3 ../../scripts/check-partition-coverage.py .
# exit != 0, invented_routes
```

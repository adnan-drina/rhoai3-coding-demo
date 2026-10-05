# M4 floor runner (R-HX.9 Phase-2 minimum)

**Status:** binding for Phase-3 dual-arm verify · **not** full AD-010 `release_qualified`
**`ad010_demo`:** false until policy promotes after measured fidelity

## Floor checks (ordered)

0. **pre-verdict** — snapshot surefire/failsafe; parse XML (fail closed if absent or Failures>0); refuse an M4 body that names `Token:`/`ship:`; retrievable tree; pinned gates with `"ran": true` only; G-4 claim consistency; fence detector on **work** logs
1. **boot_health** — package (optional skip, **never clean**) + process up + `GET /q/health` → 200
2. **endpoint_smoke** — curl inventoried or env `M4_SMOKE_PATHS` (default `/q/health`); 200/401/403 OK
3. **g4_hook** — evaluate product `migration/parity.json` if present; else honest **INCONCLUSIVE** (`g4_mode=SAMPLE`)

## Invoke

```bash
bash .hermes/skills/gates/check-release-readiness/scripts/run-m4-floor.sh /path/to/frozen-modernized
python3 .hermes/skills/gates/check-release-readiness/scripts/check-m4-floor-receipts.py \
 /path/to/frozen-modernized/evidence/receipts/m4-floor/<run-id>
```

## Honesty fence

- Floor PASS on boot+smoke ≠ semantic fidelity / full G-4 ACCEPT.
- Tip admission fixtures alone must not mint product ACCEPT.
- Full release machine (typed digests per tool, factory candidate-SHA, Sonar/MTA live) remains Wave-2 / R-HX.9 remainder.

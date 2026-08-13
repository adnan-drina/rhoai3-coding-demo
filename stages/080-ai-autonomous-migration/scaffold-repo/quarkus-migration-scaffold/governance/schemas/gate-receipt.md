# Gate receipt schema — `rhoai3.gate-receipt/v1`

JSON object fields:

| Field | Type | Notes |
|-------|------|-------|
| `schema` | string | literal `rhoai3.gate-receipt/v1` |
| `check` | string | `boot_health` \| `endpoint_smoke` \| `g4_hook` |
| `result` | string | `PASS` \| `FAIL` \| `REFUSE` \| `INCONCLUSIVE` |
| `cmd` | string | command executed |
| `rc` | int | process rc |
| `operand` | string | path/URL |
| `operand_digest` | string | sha256 of operand (may be empty) |
| `note` | string | free text |
| `ts` | string | UTC ISO-8601 |
| `floor` | string | `m4-minimum` for Phase-2 floor |
| `ad010_demo` | bool | always `false` on floor receipts |

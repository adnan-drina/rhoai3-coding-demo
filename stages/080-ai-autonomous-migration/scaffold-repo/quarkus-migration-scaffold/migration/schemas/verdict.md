# Verdict artifact schema (AD-H §18 / §18.0)

**Status:** binding · lints in `validation-release-gates`  
**Home:** `migration/verdicts/*.json` (also preflight when it carries a verdict)

## Fields

| Field | Rule |
|-------|------|
| `phase` | `M3`…`M5` / `factory` |
| `verdict` | `ACCEPT` \| `REFUSE` \| `INCONCLUSIVE` |
| `accept_kind` | Required on ACCEPT: M4 → `provisional`; M5 → `full` |
| `g1_kill_ratio` | Interim: `pending_threshold` only. `PASS` forbidden until threshold pinned (`g1_kill_ratio_threshold_pinned: true`) |
| `g1_kill_ratio_waiver` | Typed Operator waiver — required for M5 `full` ACCEPT while ratio is `pending_threshold` |
| `ship` | Never for `provisional` or `INCONCLUSIVE`. Full M5 ACCEPT only |
| `routing` / `failure_class` | See AD-H §18.3; composition reopen → `reopen_story` or `blocked` |

## Examples

```json
{"phase":"M4","verdict":"ACCEPT","accept_kind":"provisional","g1_kill_ratio":"pending_threshold","ship":false}
```

```json
{"phase":"M5","verdict":"ACCEPT","accept_kind":"full","g1_kill_ratio":"pending_threshold","g1_kill_ratio_waiver":true,"ship":true}
```

```json
{"phase":"M5","verdict":"REFUSE","gate":"g4_runtime_parity","prior_accept_kind":"provisional","routing":"reopen_story"}
```
